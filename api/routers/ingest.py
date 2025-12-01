from fastapi import APIRouter, HTTPException
from agents.intake_agent import process_raw_input, HealthInput, IntakeValidationError
import logging

router = APIRouter()
logger = logging.getLogger("api.ingest")

# Ingest endpoint
@router.post("/ingest", response_model=HealthInput)
def ingest(payload: dict):
    try:
        return process_raw_input(**payload)
    except IntakeValidationError as e:
        logger.warning(str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected ingest error")
        raise HTTPException(status_code=500, detail="Internal server error")
