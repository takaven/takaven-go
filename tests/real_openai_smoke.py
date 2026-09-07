"""Manual CI-only real OpenAI smoke using synthetic, non-sensitive evidence."""

import json
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai_service import generate_collisions
from app.config import Settings
from app.database import Base
from app.manual_loop import create_creative_run, create_signal
from app.seed import seed_leasedesk
from app.services import leasedesk


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY") or not os.environ.get("OPENAI_MODEL"):
        raise RuntimeError(
            "OPENAI_API_KEY and explicit OPENAI_MODEL are required for this smoke test."
        )
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url="sqlite://",
        operator_password="synthetic-smoke-password",
        session_secret="synthetic-smoke-secret-with-more-than-32-characters",
        cookie_secure=False,
        openai_api_key=os.environ["OPENAI_API_KEY"],
        openai_model=os.environ["OPENAI_MODEL"],
    )
    with Session(engine) as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        signal = create_signal(
            db,
            product.id,
            {
                "source": "Synthetic operator interview",
                "evidence": "A fictional owner says: show the rent state before I chase a tenant.",
                "audience": "Small-commercial-property owner-operators",
                "tension_pain": "Payment state is hard to see.",
                "why_now": "Synthetic lease review moment.",
                "product_relevance": "LeaseDesk can demonstrate payment-to-arrears state change.",
                "buying_trigger": "A tenant payment needs recording.",
                "half_life": "One week",
            },
        )
        run = create_creative_run(db, product, [signal.id])
        execution = generate_collisions(db, settings, run, "real-openai-synthetic-smoke")
        report = {
            "execution_status": execution.status,
            "model": execution.model,
            "prompt_version": execution.prompt_version,
            "schema_version": execution.schema_version,
            "request_id": execution.request_id,
            "input_snapshot": execution.input_snapshot,
            "structural_validation": execution.result,
            "claim_warnings": [item.claim_warnings for item in run.concepts],
            "concepts": [
                {
                    "tension": item.tension,
                    "creative_mechanic": item.creative_mechanic,
                    "artifact": item.artifact,
                    "product_proof": item.product_proof,
                    "participation": item.participation,
                    "distribution": item.distribution,
                    "commercial_bridge": item.commercial_bridge,
                    "dangerous_assumption": item.dangerous_assumption,
                }
                for item in run.concepts
            ],
        }
    output = Path("work/real-openai-smoke.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
