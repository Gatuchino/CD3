"""
DocuBot — Router de autenticación JWT local.
Endpoints: POST /auth/login, POST /auth/register (solo admins).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.db.models import User, Tenant
from app.core.security import (
    hash_password, verify_password, create_access_token, get_current_user, CurrentUser
)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: str = "viewer"
    tenant_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    email: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Autenticación con email y contraseña. Retorna JWT."""
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas.",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo.")

    token = create_access_token({
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "role": user.role,
    })
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Registrar nuevo usuario. Solo accesible por admin_tenant o superadmin."""
    if current_user.role not in ("admin_tenant", "superadmin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso.")

    # Verificar que el tenant existe
    tenant = await db.get(Tenant, body.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado.")

    # Verificar email único
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email ya registrado.")

    user = User(
        tenant_id=body.tenant_id,
        name=body.name,
        email=body.email,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()

    token = create_access_token({
        "sub": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "role": user.role,
    })
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        role=user.role,
    )


@router.get("/me")
async def me(current_user: CurrentUser = Depends(get_current_user)):
    """Retorna info del usuario autenticado."""
    return {
        "user_id": current_user.user_id,
        "tenant_id": current_user.tenant_id,
        "email": current_user.email,
        "role": current_user.role,
    }
