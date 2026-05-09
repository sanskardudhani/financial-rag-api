from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import AssignRoleSchema
from app.auth import get_current_user, require_admin, ROLE_PERMISSIONS

router = APIRouter()


created_roles = ["Admin", "Financial Analyst", "Auditor", "Client"]  # This is stored in RAM  its temporary



@router.post("/roles/create")
def create_role(
    role_name: str,
    current_user: User = Depends(require_admin)   # only admin can create roles
):
    if role_name in created_roles:
        raise HTTPException(status_code=400, detail="Role already exists")

    created_roles.append(role_name)

    return {
        "message": f"Role '{role_name}' created",
        "all_roles": created_roles
    }



@router.post("/users/assign-role")
def assign_role(
    data: AssignRoleSchema,
    db: Session        = Depends(get_db),
    current_user: User = Depends(require_admin)   # only admin can assign roles
):
    if data.role not in created_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Available roles: {created_roles}"
        )

    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = data.role
    db.commit()

    return {"message": f"Role '{data.role}' assigned to {data.email}"}


@router.get("/users/{user_id}/roles")
def get_user_role(
    user_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id":  user_id,
        "username": user.username,
        "role":     user.role
    }


@router.get("/users/{user_id}/permissions")
def get_user_permissions(
    user_id: int,
    db: Session        = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = ROLE_PERMISSIONS.get(user.role, [])

    return {
        "user_id":     user_id,
        "username":    user.username,
        "role":        user.role,
        "permissions": permissions
    }