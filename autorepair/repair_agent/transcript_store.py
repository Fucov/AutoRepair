from __future__ import annotations

import json
from pathlib import Path

from autorepair.repair_agent.schemas import AgentStep, RepairAgentResult

TRANSCRIPT_DIR = Path(__file__).parent.parent.parent / "transcripts"


def save_repair_transcript(
    job_id: str,
    steps: list[AgentStep],
    result: RepairAgentResult,
) -> str:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "job_id": job_id,
        "result": result.model_dump(),
        "steps": [s.model_dump() for s in steps],
    }

    out_path = TRANSCRIPT_DIR / f"{job_id}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)
