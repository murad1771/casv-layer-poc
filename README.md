# CASV Layer — Proof of Concept

Context-Adaptive Semantic Visualization Layer  
Master Thesis Appendix — Murad Rajabov, Rīgas Ziemeļvalstu Augstskola, 2026

## Structure

| File | Component | Purpose |
|------|-----------|---------|
| `metrics.yaml` | Open Semantic Layer (OSL) | Portable metric definitions in YAML |
| `qie_engine.py` | Query Intelligence Engine (QIE) | Pre/post-execution cost analysis |
| `cape_profiles.py` | Context-Adaptive Presentation Engine (CAPE) | User profile assignment + rendering config |

## How to run

```bash
pip install pyyaml
python qie_engine.py    # demonstrates QIE estimate + execute
python cape_profiles.py  # demonstrates CAPE profile assignment
```

## OSL metric format

Each metric in `metrics.yaml` defines:
- `sql` — the canonical calculation, executed identically by all connected tools
- `owner` — the team responsible for the definition
- `freshness_sla` — how recently the underlying data must be updated
- `confidence` — data quality signal surfaced to CAPE for display

## Extending

To add a new metric: add an entry to `metrics.yaml`, open a PR,
and after review and merge all connected tools will automatically
use the new definition on their next query.

To add a new tool connector: implement the OSL API client for that
tool's native connector framework (DAX custom connector for Power BI,
Python dataset for Superset, LookML extension for Looker).
