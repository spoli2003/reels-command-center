from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])

def set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie("rcc_access_token", token, httponly=True, samesite="lax", secure=False, max_age=settings.access_token_minutes * 60, path="/")

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Konto o tym adresie już istnieje")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    set_cookie(response, create_access_token(user.id))
    return user

@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Nieprawidłowy e-mail lub hasło")
    set_cookie(response, create_access_token(user.id)); return user

@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user

@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("rcc_access_token", path="/")
