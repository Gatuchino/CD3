"""
DocuBot — Middleware de autenticación Azure AD B2C.
Valida JWT tokens y extrae tenant_id, user_id y rol.
"""
import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import lru_cache
from app.core.config import settings
from app.core.demo_mode import IS_DEMO

bearer_scheme = HTTPBearer()


@lru_cache()
def get_b2c_jwks() -> dict:
    """Obtiene las claves públicas JWKS de Azure AD B2C."""
    tenant = settings.AZURE_AD_B2C_TENANT
    policy = settings.AZURE_AD_B2C_POLICY
    url = (
        f"https://{tenant}.b2clogin.com/"
        f"{tenant}.onmicrosoft.com/{policy}/discovery/v2.0/keys"
    )
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


class CurrentUser:
    def __init__(
        self,
        user_id: str,
        tenant_id: str,
        email: str,
        role: str,
        azure_subject: str,
    ):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email
        self.role = role
        self.azure_subject = azure_subject


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
        # ── Demo mode bypass ──────────────────────────────────────────
    if IS_DEMO:
        from app.db.models import UserRole
        return CurrentUser(
            user_id="demo-user-001",
            tenant_id="demo-tenant",
            email="demo@aurenza.cl",
            name="Usuario Demo",
            roles=["admin_tenant"],
        )
    # ──────────────────────────────────────────────────────────────
"""
    Valida el JWT de Azure AD B2C y retorna el usuario autenticado.
    El token debe contener: sub, extension_TenantId, email, extension_Role.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        jwks = get_b2c_jwks()
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.AZURE_AD_B2C_CLIENT_ID,
            options={"verify_exp": True},
        )

        azure_subject: str = payload.get("sub")
        email: str = payload.get("emails", [None])[0] or payload.get("email")
        tenant_id: str = payload.get("extension_TenantId")
        role: str = payload.get("extension_Role", "viewer")
        user_id: str = payload.get("extension_UserId")

        if not azure_subject or not tenant_id:
            raise credentials_exception

        return CurrentUser(
            user_id=user_id or azure_subject,
            tenant_id=tenant_id,
            email=email or "",
            role=role,
            azure_subject=azure_subject,
        )

    except JWTError:
        raise credentials_exception


def require_roles(*allowed_roles: str):
    """Dependencia de FastAPI para restringir acceso por rol."""
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
