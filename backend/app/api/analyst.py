"""AI analyst — plain-language Q&A and briefings, grounded in a REAL run's numbers.

Additive: reuses the engine's Anthropic key (same as authoring). The model only NARRATES
the deterministic engine output it is handed — it never invents the numbers.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.settings import settings

router = APIRouter(prefix="/analyst", tags=["analyst"])

SYSTEM = (
    "You are an operations decision analyst inside a simulation platform. You are handed the "
    "structured RESULT of a deterministic simulation. Follow these rules strictly:\n"
    "- Use ONLY facts and numbers that literally appear in the RUN DATA. Never invent, estimate, "
    "round differently, or infer a number that is not present — including loads, percentages, "
    "counts, times, or costs.\n"
    "- Do NOT speculate about root causes, constraints, or 'why' beyond what the data states.\n"
    "- If the user asks for something the RUN DATA does not contain, say it is not in the "
    "simulation rather than guessing.\n"
    "- Write for a CFO/COO: 2–4 tight sentences, concrete, no markdown headings. Ground the "
    "recommendation in the data's recommended_action when present."
)

PLAN_SYSTEM = (
    "You map a natural-language operations question to exactly ONE asset and ONE fault from the "
    "provided CATALOG. Return ONLY compact JSON, no prose: "
    '{"assetId":"<id or null>","faultId":"<id or null>","confidence":<0..1>}. '
    "Pick the closest match. If nothing plausibly matches, use nulls with confidence 0."
)


class AskRequest(BaseModel):
    context: str
    question: str


class PlanRequest(BaseModel):
    question: str
    assets: list[dict] = []


@router.post("/ask")
async def ask(req: AskRequest):
    if not settings.anthropic_api_key:
        return {"ok": False, "answer": "The AI analyst needs an Anthropic API key on the engine (ANTHROPIC_API_KEY)."}
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=settings.authoring_model,
            max_tokens=700,
            system=SYSTEM,
            messages=[{"role": "user", "content": f"RUN DATA:\n{req.context}\n\nQUESTION: {req.question}"}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return {"ok": True, "answer": text}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "answer": f"AI analyst unavailable: {exc}"}


@router.post("/plan")
async def plan(req: PlanRequest):
    """NL question → {assetId, faultId, confidence} against the asset catalog. The engine, not
    the model, then computes the outcome — this only routes the question to an asset+fault."""
    if not settings.anthropic_api_key:
        return {"assetId": None, "faultId": None, "confidence": 0.0, "fallback": True}
    try:
        import json
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        catalog = "\n".join(f"- {a.get('id')} ({a.get('name')}): faults {a.get('faults')}" for a in req.assets)
        resp = await client.messages.create(
            model=settings.authoring_model, max_tokens=120, system=PLAN_SYSTEM,
            messages=[{"role": "user", "content": f"CATALOG:\n{catalog}\n\nQUESTION: {req.question}\n\nJSON:"}],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "").strip()
        lo, hi = text.find("{"), text.rfind("}")
        data = json.loads(text[lo:hi + 1]) if lo >= 0 and hi > lo else {}
        return {"assetId": data.get("assetId"), "faultId": data.get("faultId"), "confidence": data.get("confidence", 0.5)}
    except Exception as exc:  # noqa: BLE001
        return {"assetId": None, "faultId": None, "confidence": 0.0, "error": str(exc)}
