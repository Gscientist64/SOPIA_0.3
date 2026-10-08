from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.core.security import (
    CurrentUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import Organization, RoleEnum, User
from app.schemas.auth import RefreshRequest, UserCreate, UserLogin, UserOut

router = APIRouter()


def _default_organization(db: Session) -> Organization:
    org = db.query(Organization).order_by(Organization.id).first()
    if org is None:
        org = Organization(name="Default Organization")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account")
    return user


def _token_pair(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id, user.role),
        "token_type": "bearer",
    }


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user.

    The very first account created becomes the SUPER_ADMIN bootstrap account;
    all subsequent self-registrations are plain USERs.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    org = _default_organization(db)
    is_first_user = db.query(User).count() == 0
    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=RoleEnum.SUPER_ADMIN.value if is_first_user else RoleEnum.USER.value,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "message": "User registered successfully",
        "role": user.role,
        "user": UserOut.model_validate(user).model_dump(),
        **_token_pair(user),
    }


@router.post("/login")
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit(20, 60)),
):
    user = _authenticate(db, payload.email, payload.password)
    return _token_pair(user)


@router.post("/token")
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit(20, 60)),
):
    """OAuth2 password-flow endpoint (used by the Swagger 'Authorize' button)."""
    user = _authenticate(db, form_data.username, form_data.password)
    return _token_pair(user)


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = db.query(User).filter(User.id == int(data["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return _token_pair(user)


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser):
    return current_user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: CurrentUser):
    """Stateless JWT logout: the client discards its tokens."""
    return None


