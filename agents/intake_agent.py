import logging
from uuid import uuid4
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ValidationError
from enum import Enum

# Logger
logger = logging.getLogger("intake")
logging.basicConfig(level=logging.INFO)

# Controlled exception
class IntakeValidationError(Exception):
    pass

# Enums for strict validation
class InputSource(str, Enum):
    web = "web"
    sms = "sms"
    voice = "voice"
    api = "api"
    email = "email"


class InputType(str, Enum):
    chat = "chat"
    intake = "intake"
    survey = "survey"
    referral = "referral"

# Pydantic Schema (canonical contract)
class HealthInput(BaseModel):
    input_id: str = Field(..., description="Trace ID for this input")
    user_id: str = Field(..., description="User identifier")
    raw_text: str = Field(..., min_length=10, max_length=5000)
    source: InputSource
    input_type: InputType
    timestamp: str
    contains_phi: bool
    consent_granted: bool

# Lightweight PHI heuristic detection
# First-pass PHI heuristic gate. NOT a medical-grade classifier.
def _detect_phi(text: str) -> bool:
    phi_keywords = [
        "name", "dob", "date of birth", "ssn", "id number",
        "address", "phone", "email", "patient"
    ]
    lowered = text.lower()
    return any(k in lowered for k in phi_keywords)

# Main Intake Processor
# Normalize unstructured healthcare input into canonical HealthInput schema.
def process_raw_input(
    raw_text: str,
    source: InputSource = InputSource.web,
    input_type: InputType = InputType.chat,
    consent_granted: bool = False,
    user_id: Optional[str] = None
) -> HealthInput:

    # 1. Basic raw validation
    if not raw_text or not raw_text.strip():
        logger.warning("Rejected empty raw_text input.")
        raise IntakeValidationError("raw_text cannot be empty.")

    raw_text = raw_text.strip()

    if len(raw_text) < 10:
        raise IntakeValidationError("raw_text is too short to be meaningful.")

    if len(raw_text) > 5000:
        raise IntakeValidationError("raw_text exceeds maximum length (5000 chars).")

    # 2. Trace + metadata
    input_id = str(uuid4())
    if not user_id:
        user_id = str(uuid4())

    timestamp = datetime.utcnow().isoformat()

    # 3. PHI detection
    contains_phi = _detect_phi(raw_text)

    # 4. HIPAA Consent Gate
    if contains_phi and not consent_granted:
        logger.warning(
            f"PHI detected but consent_granted=False | input_id={input_id}"
        )
        raise IntakeValidationError(
            "PHI detected but patient consent has not been granted."
        )
    
    # 5. Build Pydantic object (final contract)
    try:
        health_input = HealthInput(
            input_id=input_id,
            user_id=user_id,
            raw_text=raw_text,
            source=source,
            input_type=input_type,
            timestamp=timestamp,
            contains_phi=contains_phi,
            consent_granted=consent_granted
        )
    except ValidationError as e:
        logger.error(f"Pydantic validation failed: {e}")
        raise IntakeValidationError("HealthInput schema validation failed.")

    logger.info(
    f"Intake accepted | input_id={input_id} | "
    f"source={source} | type={input_type} | phi={contains_phi}"
    )

    return health_input

# Class wrapper used by the pipeline
# Wrapper class so HealthcarePipeline can call: self.intake.run(raw_text, meta)
class IntakeAgent:
    def run(self, raw_text: str, meta: dict) -> HealthInput:
        return process_raw_input(
            raw_text=raw_text,
            source=meta.get("source", InputSource.web),
            input_type=meta.get("input_type", InputType.chat),
            consent_granted=meta.get("consent", False),
            user_id=meta.get("user_id"),
        )