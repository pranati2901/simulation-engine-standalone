"""Compute and persist simulation runs."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.engine.config import RunConfig
from app.engine.environment import EnvironmentSpec
from app.engine.result import RunResult
from app.engine.run import run as engine_run
from app.engine.scenario import PlaybookStep, Scenario
from app.db.models import Report, Run, Scenario as ScenarioRow
from app.reports.generator import generate_report


def scenario_from_row(row: ScenarioRow) -> Scenario:
    return Scenario.model_validate(row.definition)


def compute(scenario: Scenario, env: EnvironmentSpec, config: RunConfig,
            extra_steps: list[PlaybookStep] | None = None) -> RunResult:
    if extra_steps:
        scenario = scenario.model_copy(deep=True)
        scenario.playbook = sorted(scenario.playbook + extra_steps, key=lambda s: s.at_min)
    return engine_run(scenario, env, config)


def run_payload(run: Run, industry: str) -> dict:
    """Shape a Run row into the dict the report generator consumes."""
    return {
        "scenario_name": run.scenario_name,
        "industry": industry,
        "duration_s": run.duration_s,
        "focus_role": run.focus_role,
        "scores": run.scores,
        "kpis": run.kpis,
        "summary": run.summary,
        "objectives": run.objectives,
        "role_tasks": run.role_tasks,
        "events": run.events,
        "environment": run.environment,
        "final_assets": run.final_assets,
    }


def create_run(
    db: Session,
    *,
    scenario_id: str,
    environment_spec: dict | None = None,
    config: dict | None = None,
    operator: str | None = None,
) -> Run:
    row = db.get(ScenarioRow, scenario_id)
    if row is None:
        raise KeyError(scenario_id)
    scenario = scenario_from_row(row)

    env = (EnvironmentSpec.model_validate(environment_spec)
           if environment_spec else scenario.recommended_topology)
    cfg = (RunConfig.model_validate(config) if config
           else RunConfig(duration_min=scenario.nominal_duration_min))

    result = compute(scenario, env, cfg)

    run = Run(
        scenario_id=scenario_id, scenario_name=scenario.name, operator=operator,
        status="completed", focus_role=result.focus_role, config=cfg.model_dump(mode="json"),
        environment_spec=env.model_dump(mode="json"), duration_s=result.duration_s,
        scores=result.scores, kpis=result.kpis, summary=result.summary,
        objectives=result.model_dump(mode="json")["objectives"],
        workflows=result.workflows, role_tasks=result.role_tasks,
        environment=result.environment, final_assets=result.final_assets,
        events=[e.model_dump(mode="json") for e in result.events],
    )
    db.add(run)
    db.flush()
    db.add(Report(run_id=run.id, content=generate_report(run_payload(run, scenario.industry))))
    db.commit()
    db.refresh(run)
    return run
