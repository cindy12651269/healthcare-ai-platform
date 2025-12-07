from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from agents.pipeline import HealthcarePipeline
from agents.intake_agent import IntakeValidationError
from agents.structuring_agent import StructuringError
from api.deps import get_pipeline

router = APIRouter()
logger = logging.getLogger("api.ingest")

# Request Schema
class IngestRequest(BaseModel):
    text: str
    source: Optional[str] = "web"
    input_type: Optional[str] = "chat"
    consent_granted: Optional[bool] = False
    user_id: Optional[str] = None

# Response Schema: use plain dict fields because pipeline returns dicts.
class IngestResponse(BaseModel):
    success: bool
    intake: Optional[Dict[str, Any]]
    structured: Optional[Dict[str, Any]]
    report: Optional[Dict[str, Any]]
    errors: List[Dict[str, Any]]

# Main Endpoint
@router.post("/ingest")
def ingest(
    payload: IngestRequest,
    pipeline: HealthcarePipeline = Depends(get_pipeline),
):
    logger.info("Received ingest request")

    try:
        trace = pipeline.run(
            raw_text=payload.text,
            meta={
                "source": payload.source,
                "input_type": payload.input_type,
                "consent_granted": payload.consent_granted,
                "user_id": payload.user_id,
            },
        )

        return trace   

    except IntakeValidationError as e:
        logger.warning(f"Intake error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except StructuringError as e:
        logger.error(f"Structuring failed: {e}")
        raise HTTPException(status_code=422, detail=f"LLM structuring error: {e}")

    except Exception as e:
        logger.exception("Unexpected pipeline error")
        raise HTTPException(status_code=500, detail="Internal server error")
