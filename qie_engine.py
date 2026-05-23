"""
Query Intelligence Engine (QIE) — Proof of Concept
CASV Layer Component 2

Intercepts incoming SQL queries, analyses their cost,
surfaces plain-language feedback, and attaches post-execution
metadata (freshness, rows scanned, cache status).
"""

import re
import time
import hashlib
from dataclasses import dataclass, field
from typing import Optional


# ── Data structures ────────────────────────────────────────────────

@dataclass
class QueryEstimate:
    rows_to_scan: int
    estimated_seconds: float
    cache_hit: bool
    partition_used: bool
    suggestions: list[str] = field(default_factory=list)

    def plain_language_warning(self) -> Optional[str]:
        if self.estimated_seconds < 5:
            return None
        msg = (
            f"This query will scan approximately "
            f"{self.rows_to_scan / 1_000_000:.1f}M rows "
            f"and is estimated to take ~{self.estimated_seconds:.0f}s."
        )
        if self.suggestions:
            msg += " Suggestions: " + "; ".join(self.suggestions) + "."
        return msg


@dataclass
class QueryResult:
    rows: list[dict]
    execution_seconds: float
    rows_scanned: int
    cache_hit: bool
    data_freshness_minutes: int
    confidence: str  # "high" | "medium" | "low"


# ── QIE Engine ─────────────────────────────────────────────────────

class QueryIntelligenceEngine:
    """
    Intercepts queries before and after execution.
    Provides cost estimates, optimization suggestions,
    and post-execution metadata.
    """

    def __init__(self, connection, osl_registry=None):
        self.connection = connection
        self.osl = osl_registry          # OSL metric registry
        self._cache: dict = {}
        self._query_history: list = []

    # ── Pre-execution ──────────────────────────────────────────────

    def estimate(self, sql: str) -> QueryEstimate:
        """
        Analyse the query before running it.
        Returns a cost estimate with plain-language suggestions.
        """
        rows = self._estimate_row_count(sql)
        seconds = self._estimate_seconds(rows)
        partition = self._has_partition_filter(sql)
        suggestions = self._generate_suggestions(sql, rows, partition)

        return QueryEstimate(
            rows_to_scan=rows,
            estimated_seconds=seconds,
            cache_hit=self._is_cached(sql),
            partition_used=partition,
            suggestions=suggestions,
        )

    # ── Execution ──────────────────────────────────────────────────

    def execute(self, sql: str, freshness_required: bool = False) -> QueryResult:
        """
        Execute the query, attach post-execution metadata,
        and store in history for admin analytics.
        """
        cache_key = hashlib.md5(sql.encode()).hexdigest()

        if not freshness_required and cache_key in self._cache:
            cached = self._cache[cache_key]
            result = QueryResult(**cached, cache_hit=True)
            self._log(sql, result)
            return result

        start = time.time()
        raw_rows = self.connection.execute(sql)
        elapsed = time.time() - start

        # Attach OSL freshness metadata if metric is recognized
        freshness, confidence = self._resolve_freshness(sql)

        result = QueryResult(
            rows=raw_rows,
            execution_seconds=round(elapsed, 2),
            rows_scanned=len(raw_rows),   # simplified; real impl uses EXPLAIN
            cache_hit=False,
            data_freshness_minutes=freshness,
            confidence=confidence,
        )

        self._cache[cache_key] = {
            "rows": raw_rows,
            "execution_seconds": elapsed,
            "rows_scanned": result.rows_scanned,
            "data_freshness_minutes": freshness,
            "confidence": confidence,
        }
        self._log(sql, result)
        return result

    # ── Admin analytics ────────────────────────────────────────────

    def slow_queries(self, threshold_seconds: float = 10.0) -> list[dict]:
        """Return queries that consistently exceed the latency threshold."""
        return [
            q for q in self._query_history
            if q["execution_seconds"] > threshold_seconds
        ]

    def materialization_candidates(self) -> list[str]:
        """
        Identify queries called frequently with high row scans.
        These are candidates for pre-materialization.
        """
        from collections import Counter
        counts = Counter(q["sql"] for q in self._query_history)
        return [
            sql for sql, count in counts.items()
            if count >= 5 and any(
                q["sql"] == sql and q["rows_scanned"] > 10_000_000
                for q in self._query_history
            )
        ]

    # ── Internal helpers ───────────────────────────────────────────

    def _estimate_row_count(self, sql: str) -> int:
        # Simplified heuristic; real impl runs EXPLAIN
        if "WHERE" not in sql.upper():
            return 2_400_000_000   # full scan
        if re.search(r"date\s*[><=]", sql, re.IGNORECASE):
            return 12_000_000      # date-filtered
        return 500_000_000

    def _estimate_seconds(self, rows: int) -> float:
        return round(rows / 65_000_000, 1)   # ~65M rows/sec baseline

    def _has_partition_filter(self, sql: str) -> bool:
        return bool(re.search(
            r"(date|settled_at|created_at)\s*(>=|>|=|BETWEEN)",
            sql, re.IGNORECASE
        ))

    def _generate_suggestions(
        self, sql: str, rows: int, partition: bool
    ) -> list[str]:
        tips = []
        if not partition and rows > 100_000_000:
            tips.append(
                "Add a date filter (e.g. WHERE settled_at >= '2026-01-01') "
                "to reduce scan by ~97%"
            )
        if "SELECT *" in sql.upper():
            tips.append("Replace SELECT * with explicit columns to reduce I/O")
        if "ORDER BY" in sql.upper() and "LIMIT" not in sql.upper():
            tips.append("Add LIMIT to avoid sorting the full result set")
        return tips

    def _is_cached(self, sql: str) -> bool:
        return hashlib.md5(sql.encode()).hexdigest() in self._cache

    def _resolve_freshness(self, sql: str) -> tuple[int, str]:
        """Look up freshness from OSL registry based on referenced table."""
        if self.osl is None:
            return 5, "high"
        for metric in self.osl.metrics:
            if metric["source_table"] in sql:
                return metric.get("freshness_minutes", 5), metric.get("confidence", "high")
        return 5, "high"

    def _log(self, sql: str, result: QueryResult) -> None:
        self._query_history.append({
            "sql": sql,
            "execution_seconds": result.execution_seconds,
            "rows_scanned": result.rows_scanned,
            "cache_hit": result.cache_hit,
        })


# ── Example usage ─────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulated connection and OSL registry
    class MockConnection:
        def execute(self, sql): return [{"merchant_id": "MRC-001", "revenue": 2847221}]

    class MockOSL:
        metrics = [{"source_table": "payments", "freshness_minutes": 3, "confidence": "high"}]

    qie = QueryIntelligenceEngine(MockConnection(), MockOSL())

    sql = "SELECT merchant_id, SUM(amount_eur) FROM transactions GROUP BY 1"

    estimate = qie.estimate(sql)
    warning = estimate.plain_language_warning()
    if warning:
        print(f"⚠  {warning}")

    result = qie.execute(sql)
    print(f"✓  Executed in {result.execution_seconds}s | "
          f"Freshness: {result.data_freshness_minutes} min | "
          f"Confidence: {result.confidence}")
