"""
Context-Adaptive Presentation Engine (CAPE) — Proof of Concept
CASV Layer Component 3

Maintains a user context model and assigns interface profiles
based on role and inferred analytical behaviour.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class InterfaceProfile(str, Enum):
    MONITORING   = "monitoring"    # Executive — clean KPI view
    EXPLORATORY  = "exploratory"   # Business user — NLQ + suggestions
    ANALYTICAL   = "analytical"    # Data analyst — full SQL + stats


@dataclass
class UserBehaviourSignal:
    """A single observation of user interaction."""
    action: str        # "sql_query" | "nlq" | "dashboard_view" | "export"
    feature_used: str  # e.g. "sql_lab", "filter", "drill_through"


@dataclass
class UserContext:
    user_id: str
    role: str                          # "executive" | "analyst" | "business"
    team: str
    explicit_profile: Optional[InterfaceProfile] = None
    behaviour_log: list[UserBehaviourSignal] = field(default_factory=list)

    # ── Profile assignment ─────────────────────────────────────────

    def assigned_profile(self) -> InterfaceProfile:
        """
        Returns the active interface profile.
        Explicit user choice always wins; otherwise infer from behaviour.
        """
        if self.explicit_profile:
            return self.explicit_profile
        return self._infer_profile()

    def _infer_profile(self) -> InterfaceProfile:
        if not self.behaviour_log:
            return self._default_from_role()

        actions = [s.action for s in self.behaviour_log[-50:]]
        sql_ratio  = actions.count("sql_query")   / len(actions)
        nlq_ratio  = actions.count("nlq")          / len(actions)
        view_ratio = actions.count("dashboard_view") / len(actions)

        if sql_ratio > 0.4:
            return InterfaceProfile.ANALYTICAL
        if nlq_ratio > 0.3 or (view_ratio > 0.5 and nlq_ratio > 0.1):
            return InterfaceProfile.EXPLORATORY
        if view_ratio > 0.7:
            return InterfaceProfile.MONITORING
        return self._default_from_role()

    def _default_from_role(self) -> InterfaceProfile:
        role_map = {
            "executive":  InterfaceProfile.MONITORING,
            "business":   InterfaceProfile.EXPLORATORY,
            "analyst":    InterfaceProfile.ANALYTICAL,
        }
        return role_map.get(self.role, InterfaceProfile.EXPLORATORY)

    def log_action(self, action: str, feature: str) -> None:
        self.behaviour_log.append(UserBehaviourSignal(action, feature))

    def override_profile(self, profile: InterfaceProfile) -> None:
        """User explicitly selects a different profile."""
        self.explicit_profile = profile


# ── CAPE Engine ────────────────────────────────────────────────────

@dataclass
class DashboardConfig:
    """Rendering configuration returned by CAPE for a given user."""
    profile: InterfaceProfile
    show_sql_editor: bool
    show_nlq_bar: bool
    show_stat_functions: bool
    show_raw_metric_sql: bool
    show_export_button: bool
    chart_suggestion_enabled: bool
    freshness_display: str   # "prominent" | "subtle" | "hidden"
    filter_complexity: str   # "full" | "guided" | "minimal"


class ContextAdaptivePresentationEngine:

    PROFILE_CONFIGS: dict[InterfaceProfile, DashboardConfig] = {
        InterfaceProfile.MONITORING: DashboardConfig(
            profile=InterfaceProfile.MONITORING,
            show_sql_editor=False,
            show_nlq_bar=False,
            show_stat_functions=False,
            show_raw_metric_sql=False,
            show_export_button=False,
            chart_suggestion_enabled=False,
            freshness_display="prominent",
            filter_complexity="minimal",
        ),
        InterfaceProfile.EXPLORATORY: DashboardConfig(
            profile=InterfaceProfile.EXPLORATORY,
            show_sql_editor=False,
            show_nlq_bar=True,
            show_stat_functions=False,
            show_raw_metric_sql=False,
            show_export_button=True,
            chart_suggestion_enabled=True,
            freshness_display="subtle",
            filter_complexity="guided",
        ),
        InterfaceProfile.ANALYTICAL: DashboardConfig(
            profile=InterfaceProfile.ANALYTICAL,
            show_sql_editor=True,
            show_nlq_bar=True,
            show_stat_functions=True,
            show_raw_metric_sql=True,
            show_export_button=True,
            chart_suggestion_enabled=True,
            freshness_display="subtle",
            filter_complexity="full",
        ),
    }

    def get_config(self, user: UserContext) -> DashboardConfig:
        profile = user.assigned_profile()
        return self.PROFILE_CONFIGS[profile]

    def suggest_profile_change(self, user: UserContext) -> Optional[str]:
        """
        If user behaviour diverges from their current profile,
        suggest switching.
        """
        current = user.assigned_profile()
        inferred = user._infer_profile()
        if current != inferred:
            return (
                f"Your recent activity suggests the '{inferred.value}' profile "
                f"may suit you better. Switch? (current: {current.value})"
            )
        return None


# ── Example usage ─────────────────────────────────────────────────

if __name__ == "__main__":
    cape = ContextAdaptivePresentationEngine()

    # Executive user — assigned monitoring by default
    ceo = UserContext(user_id="u001", role="executive", team="leadership")
    cfg = cape.get_config(ceo)
    print(f"CEO profile: {cfg.profile.value} | "
          f"SQL editor: {cfg.show_sql_editor} | "
          f"Freshness: {cfg.freshness_display}")

    # Analyst who has been running SQL
    analyst = UserContext(user_id="u002", role="analyst", team="data")
    for _ in range(20):
        analyst.log_action("sql_query", "sql_lab")
    for _ in range(5):
        analyst.log_action("dashboard_view", "main")

    cfg2 = cape.get_config(analyst)
    print(f"Analyst profile: {cfg2.profile.value} | "
          f"SQL editor: {cfg2.show_sql_editor} | "
          f"Raw metric SQL: {cfg2.show_raw_metric_sql}")

    # Business user who started using NLQ
    biz = UserContext(user_id="u003", role="business", team="sales")
    for _ in range(15):
        biz.log_action("dashboard_view", "sales_dash")
    for _ in range(10):
        biz.log_action("nlq", "ask_data")

    cfg3 = cape.get_config(biz)
    suggestion = cape.suggest_profile_change(biz)
    print(f"Biz profile: {cfg3.profile.value} | "
          f"NLQ: {cfg3.show_nlq_bar} | "
          f"Charts: {cfg3.chart_suggestion_enabled}")
    if suggestion:
        print(f"Suggestion: {suggestion}")
