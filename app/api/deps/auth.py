"""
Dépendances d'authentification FastAPI
Middleware pour vérifier les tokens et permissions
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.auth import AuthService
from app.models.user import User, UserRole
from app.core.security import verify_token, verify_admin_token

# Configuration du Bearer Token
security = HTTPBearer()

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """
    Obtenir une instance du service d'authentification
    """
    return AuthService(db)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """
    Récupérer l'utilisateur actuel depuis le token JWT
    """
    token = credentials.credentials
    user = auth_service.get_current_user(token)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.is_blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Votre compte a été bloqué. Contactez l'administration.",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé",
        )
    
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Récupérer un utilisateur actif (avec abonnement valide)
    """
    if not current_user.has_active_subscription:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Abonnement expiré. Veuillez renouveler votre abonnement.",
        )
    
    return current_user

def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """
    Récupérer l'utilisateur admin actuel
    """
    token = credentials.credentials
    admin_user = auth_service.get_admin_user(token)
    
    if admin_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token admin invalide ou droits insuffisants",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not admin_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte admin désactivé",
        )
    
    return admin_user

def get_current_super_admin(
    admin_user: User = Depends(get_current_admin_user)
) -> User:
    """
    Récupérer un super admin (droits maximum)
    """
    if admin_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Droits super admin requis",
        )
    
    return admin_user

def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    auth_service: AuthService = Depends(get_auth_service)
) -> Optional[User]:
    """
    Récupérer l'utilisateur actuel (optionnel - pour les endpoints publics)
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        user = auth_service.get_current_user(token)
        return user if user and user.is_active and not user.is_blocked else None
    except:
        return None

def require_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Exiger un utilisateur vérifié
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Profil non vérifié. Contactez l'administration.",
        )
    
    return current_user

def require_complete_profile(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Exiger un profil complet
    """
    if not current_user.is_profile_complete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Veuillez compléter votre profil avant d'accéder à cette fonctionnalité.",
        )
    
    return current_user

def require_subscription(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Exiger un abonnement actif (pour certaines fonctionnalités premium)
    """
    if not current_user.has_active_subscription:
        subscription_status = "expiré"
        if current_user.subscription:
            if current_user.subscription.status == "trial":
                subscription_status = "période d'essai expirée"
        
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Abonnement {subscription_status}. Veuillez renouveler pour accéder à cette fonctionnalité.",
        )
    
    return current_user

class AdminPermission:
    """
    Vérificateur de permissions admin
    """
    def __init__(self, permission: str):
        self.permission = permission
    
    def __call__(self, admin_user: User = Depends(get_current_admin_user)) -> User:
        # Pour l'instant, tous les admins ont toutes les permissions
        # Plus tard, on pourra implémenter un système de permissions granulaires
        return admin_user

# Instances des permissions admin
require_dashboard_access = AdminPermission("dashboard")
require_user_management = AdminPermission("users")
require_financial_access = AdminPermission("finances")
require_moderation_access = AdminPermission("moderation")

def get_request_info(request) -> dict:
    """
    Extraire les informations de la requête pour l'audit
    """
    return {
        "ip_address": request.client.host if hasattr(request, 'client') else None,
        "user_agent": request.headers.get("user-agent", "") if hasattr(request, 'headers') else "",
        "method": request.method if hasattr(request, 'method') else "",
        "url": str(request.url) if hasattr(request, 'url') else ""
    }