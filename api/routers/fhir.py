"""
FHIR R4 export of one intake (Issue #42). Read-only and clinic-scoped like the #30
records API: staff/admin membership of `{clinic_id}` required; another clinic's intake
reads as 404. Export-only, nothing is transmitted. The QuestionnaireResponse carries the
raw intake text, so the response is PHI-bearing (docs/security_data_handling.md).
"""
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.auth import Principal
from api.routers.records import _audit, _get_owned, staff_or_admin
from db.models import Clinic, ReviewEvent
from db.session import get_db
from interoperability.fhir_export import build_bundle

router = APIRouter()


@router.get("/clinics/{clinic_id}/intakes/{intake_id}/fhir")
def export_intake_fhir(
    clinic_id: str,
    intake_id: str,
    principal: Principal = Depends(staff_or_admin),
    db: Session = Depends(get_db),
):
    started = time.perf_counter()
    record = _get_owned(db, clinic_id, intake_id)
    clinic = db.get(Clinic, clinic_id)
    events = (
        db.query(ReviewEvent)
        .filter(ReviewEvent.intake_id == record.id, ReviewEvent.clinic_id == clinic_id)
        .order_by(ReviewEvent.created_at, ReviewEvent.id).all()
    )
    bundle = build_bundle(record, clinic.name if clinic else None, events)

    # Ids only: never the intake text or Bundle content
    _audit(principal, "intake.fhir_export", clinic_id, started, resource_id=record.id)
    return JSONResponse(bundle, media_type="application/fhir+json")
