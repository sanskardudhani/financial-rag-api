from jose import jwt, JWTError
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
import app.models as models
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "changeme")  # Like secret stamp/signature. Only server knows it.
ALGORITHM  = "HS256"

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")   # Creates password hashing system/machine
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")          # token extractor system
 

# --- Password helpers ---

def hash_password(password: str) -> str:                #Input:  123456       Output: $2b$12$ajshdj...          Stored in DB.
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:   # verify plain and hashed are same or not if same return True or return False
    return pwd_context.verify(plain, hashed)            # During login: checks if entered password matches stored hash


# --- Token helpers ---

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# --- Verify token and return user ---
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])                 # Backend checks: token valid?  signature correct?  expired?  tampered?
        email   = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:                                                                    # Handles expired token  fake token   corrupted token
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# --- Role to Permission map ---

ROLE_PERMISSIONS = {
    "Admin":             ["upload", "edit", "delete", "view", "manage_roles"],
    "Financial Analyst": ["upload", "edit", "view"],
    "Auditor":           ["view"],
    "Client":            ["view"],
}


def require_permission(permission: str):
    """
    Use this to protect a route by permission level.
    Example:  current_user = Depends(require_permission("delete"))
    """
    def checker(current_user: models.User = Depends(get_current_user)):
        allowed = ROLE_PERMISSIONS.get(current_user.role, [])       # Gets permissions list for role take role from db like admin and store all list inside Admin
        if permission not in allowed:   
            raise HTTPException(
                status_code=403,
                detail=f"Your role '{current_user.role}' does not have '{permission}' permission"
            )
        return current_user
    return checker


def require_admin(current_user: models.User = Depends(get_current_user)):
    """Only Admin can access this route."""
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can perform this action"
        )
    return current_user