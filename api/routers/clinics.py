"""
Staff-facing clinic endpoints (Issue #28): the caller's identity and minimal
clinic-admin management of staff membership. Every clinic-scoped route checks
the caller's own membership of the `{clinic_id}` in the path (api.auth).
"""
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from api.auth import Principal, get_current_principal, require_clinic_role
from db.models import ClinicMembership, User
from db.session import get_db

router = APIRouter()

staff_or_admin = require_clinic_role("clinic_staff", "clinic_admin")
admin_only = require_clinic_role("clinic_admin")


class MembershipOut(BaseModel):
    clinic_id: str
    role: str


class MeOut(BaseModel):
    user_id: str
    email: str
    memberships: List[MembershipOut]


class MemberOut(BaseModel):
    user_id: str
    email: str
    role: str


class MemberRoleIn(BaseModel):
    # Only the role is accepted; the clinic always comes from the authorized path
    model_config = ConfigDict(extra="forbid")
    role: Literal["clinic_staff", "clinic_admin"]


@router.get("/staff/me", response_model=MeOut)
def me(principal: Principal = Depends(get_current_principal)):
    return MeOut(
        user_id=principal.user_id,
        email=principal.email,
        memberships=[MembershipOut(clinic_id=c, role=r) for c, r in sorted(principal.roles.items())],
    )


@router.get("/clinics/{clinic_id}/members", response_model=List[MemberOut])
def list_members(clinic_id: str, _: Principal = Depends(staff_or_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(ClinicMembership, User)
        .join(User, User.id == ClinicMembership.user_id)
        .filter(ClinicMembership.clinic_id == clinic_id)
        .order_by(User.email)
    )
    return [MemberOut(user_id=u.id, email=u.email, role=m.role) for m, u in rows]


def _not_self(principal: Principal, user_id: str) -> None:
    # Prevents an admin from demoting or removing themselves and locking the clinic out
    if principal.user_id == user_id:
        raise HTTPException(status_code=409, detail="Admins cannot change their own membership")


@router.put("/clinics/{clinic_id}/members/{user_id}", response_model=MemberOut)
def set_member_role(
    clinic_id: str,
    user_id: str,
    body: MemberRoleIn,
    principal: Principal = Depends(admin_only),
    db: Session = Depends(get_db),
):
    _not_self(principal, user_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    membership = db.get(ClinicMembership, (user_id, clinic_id))
    if membership is None:
        membership = ClinicMembership(user_id=user_id, clinic_id=clinic_id, role=body.role)
        db.add(membership)
    else:
        membership.role = body.role
    db.flush()
    return MemberOut(user_id=user.id, email=user.email, role=membership.role)


@router.delete("/clinics/{clinic_id}/members/{user_id}", status_code=204)
def remove_member(
    clinic_id: str,
    user_id: str,
    principal: Principal = Depends(admin_only),
    db: Session = Depends(get_db),
):
    _not_self(principal, user_id)
    membership = db.get(ClinicMembership, (user_id, clinic_id))
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(membership)
    db.flush()
    return Response(status_code=204)
