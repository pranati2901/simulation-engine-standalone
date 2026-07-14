"""Layer 9 — Reports.

Generic report generator: turns a RunResult into a structured report, letting each
domain plugin contribute extra sections (DomainPlugin.report_sections) instead of
hardcoding cyber-specific report content the way GoalCert's reports/generator.py does.
"""
from __future__ import annotations

from ..engine.result import RunResult
from ..plugins.registry import get_plugin


def generate(run_result: RunResult, domain: str) -> dict:
    sections = [
        {"title": "Summary", "content": run_result.summary},
        {"title": "KPIs", "content": run_result.kpis},
        {"title": "Objectives", "content": run_result.objectives},
        {"title": "Scores", "content": run_result.scores},
    ]
    plugin = get_plugin(domain)
    if plugin is not None:
        sections.extend(plugin.report_sections(run_result))
    return {"scenario_id": run_result.scenario_id, "sections": sections}
