from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm    
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import RegisterSchema               
from app.auth import hash_password, verify_password, create_token

router = APIRouter()


@router.post("/auth/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):

    # check if email already used
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # check if username already used
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = User(
        username=data.username,
        email=data.email,
        password=hash_password(data.password)
    )
    db.add(new_user)
    db.commit()

    return {"message": "User registered successfully"}


@router.post("/auth/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    # OAuth2 uses "username" field
    # here i have treated   username as email
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Wrong password")

    token = create_token({"sub": user.email})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role
    }