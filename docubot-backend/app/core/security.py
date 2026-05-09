"""
DocuBot — Autenticación JWT local (reemplaza Azure AD B2C).
Genera y valida tokens HS256 firmados con JWT_SECRET_KEY.
"""
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from app.core.demo_mode import IS_DEMO

bearer_scheme = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class CurrentUser:
    def __init__(self, user_id: str, tenant_id: str, email: str, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    """Valida el JWT y retorna el usuario autenticado."""
    # Demo mode bypass
    if IS_DEMO:
        return CurrentUser(
            user_id="demo-user-001",
            tenant_id="demo-tenant-001",
            email="demo@aurenza.cl",
            role="admin_tenant",
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        email: str = payload.get("email", "")
        role: str = payload.get("role", "viewer")

        if not user_id or not tenant_id:
            raise credentials_exception

        return CurrentUser(user_id=user_id, tenant_id=tenant_id, email=email, role=role)

    except JWTError:
        raise credentials_exception


def require_roles(*allowed_roles: str):
    """Dependencia FastAPI para restringir acceso por rol."""
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol '{current_user.role}' no tiene acceso a este recurso.",
            )
        return current_user
    return role_checker
