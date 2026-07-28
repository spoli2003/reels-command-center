from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from jwt import InvalidTokenError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

def get_current_user(rcc_access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not rcc_access_token:
        raise HTTPException(401, "Brak aktywnej sesji")
    try:
        user_id = decode_access_token(rcc_access_token)
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, "Sesja wygasła lub jest nieprawidłowa")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Użytkownik jest nieaktywny")
    return user
