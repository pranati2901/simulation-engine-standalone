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
    "You are an operations decision analyst inside a simulation platform. Answer briefly and "
    "concretely for a business decision-maker (CFO/COO), using ONLY the run data provided. "
    "Cite the actual numbers you are given; never invent figures. No markdown headings. "
    "Keep it to 2–4 tight sentences unless asked for more."
)


class AskRequest(BaseModel):
    context: str
    question: str


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
