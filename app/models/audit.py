# =====================================================
# app/models/audit.py - Système d'audit et logs
# =====================================================

"""
Modèles d'audit AlloBara
Traçabilité des actions admin et utilisateurs
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.sql import func
from datetime import datetime
import enum
import json

from app.db.database import Base

# =========================================
# ENUMS AUDIT
# =========================================

class AuditAction(str, enum.Enum):
    """Types d'actions auditées"""
    # Actions utilisateur
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    
    # Actions abonnement
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_ACTIVATED = "subscription_activated"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    
    # Actions portfolio
    PORTFOLIO_ADDED = "portfolio_added"
    PORTFOLIO_UPDATED = "portfolio_updated"
    PORTFOLIO_DELETED = "portfolio_deleted"
    
    # Actions paiement
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_COMPLETED = "payment_completed"
    PAYMENT_FAILED = "payment_failed"
    
    # Actions admin
    ADMIN_LOGIN = "admin_login"
    ADMIN_USER_BLOCKED = "admin_user_blocked"
    ADMIN_USER_UNBLOCKED = "admin_user_unblocked"
    ADMIN_WITHDRAWAL = "admin_withdrawal"
    ADMIN_REVIEW_MODERATED = "admin_review_moderated"
    
    # Actions système
    SYSTEM_BACKUP = "system_backup"
    SYSTEM_MAINTENANCE = "system_maintenance"

class AuditLevel(str, enum.Enum):
    """Niveau d'importance de l'audit"""
    INFO = "info"          # Information générale
    WARNING = "warning"    # Avertissement
    ERROR = "error"        # Erreur
    CRITICAL = "critical"  # Critique

# =========================================
# MODÈLE AUDIT LOG
# =========================================

class AuditLog(Base):
    """
    Journal d'audit des actions
    Traçabilité complète du système
    """
    __tablename__ = "audit_logs"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    
    # =====================================
    # ACTION ET CONTEXTE
    # =====================================
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    level = Column(SQLEnum(AuditLevel), default=AuditLevel.INFO, nullable=False)
    
    # Qui a fait l'action
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_phone = Column(String(20), nullable=True)     # Backup si user supprimé
    user_role = Column(String(20), nullable=True)      # Role au moment de l'action
    
    # =====================================
    # DÉTAILS DE L'ACTION
    # =====================================
    resource_type = Column(String(50), nullable=True)   # "user", "subscription", etc.
    resource_id = Column(Integer, nullable=True)        # ID de la ressource concernée
    
    description = Column(String(500), nullable=False)   # Description lisible
    details = Column(JSON, nullable=True)               # Détails techniques JSON
    
    # Données avant/après (pour les modifications)
    old_values = Column(JSON, nullable=True)            # Valeurs avant modification
    new_values = Column(JSON, nullable=True)            # Valeurs après modification
    
    # =====================================
    # MÉTADONNÉES TECHNIQUES
    # =====================================
    ip_address = Column(String(45), nullable=True)      # Adresse IP
    user_agent = Column(String(500), nullable=True)     # User agent
    endpoint = Column(String(200), nullable=True)       # Endpoint API utilisé
    method = Column(String(10), nullable=True)          # GET, POST, PUT, DELETE
    
    # Session et sécurité
    session_id = Column(String(100), nullable=True)     # ID de session
    request_id = Column(String(50), nullable=True)      # ID unique de requête
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<AuditLog(action={self.action.value}, user_id={self.user_id})>"
    
    def __str__(self):
        return f"{self.action.value} - {self.description}"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def formatted_date(self) -> str:
        """Date formatée"""
        return self.created_at.strftime("%d/%m/%Y %H:%M:%S")
    
    @property
    def is_admin_action(self) -> bool:
        """Vérifier si c'est une action admin"""
        return self.action.value.startswith("admin_")
    
    @property
    def is_system_action(self) -> bool:
        """Vérifier si c'est une action système"""
        return self.action.value.startswith("system_")
    
    @property
    def has_changes(self) -> bool:
        """Vérifier s'il y a des changements enregistrés"""
        return self.old_values is not None or self.new_values is not None
    
    @property
    def level_color(self) -> str:
        """Couleur selon le niveau"""
        colors = {
            AuditLevel.INFO: "blue",
            AuditLevel.WARNING: "orange", 
            AuditLevel.ERROR: "red",
            AuditLevel.CRITICAL: "purple"
        }
        return colors.get(self.level, "gray")
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @classmethod
    def create_log(cls, action: AuditAction, description: str, 
                   user_id: int = None, resource_type: str = None, 
                   resource_id: int = None, **kwargs):
        """Créer un log d'audit"""
        log = cls(
            action=action,
            description=description,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id
        )
        
        # Ajouter les métadonnées optionnelles
        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)
        
        return log
    
    def add_change_tracking(self, old_values: dict, new_values: dict):
        """Ajouter le suivi des changements"""
        self.old_values = old_values
        self.new_values = new_values
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire"""
        return {
            "id": self.id,
            "action": self.action.value,
            "level": self.level.value,
            "description": self.description,
            "user_id": self.user_id,
            "user_phone": self.user_phone,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "formatted_date": self.formatted_date,
            "has_changes": self.has_changes,
            "level_color": self.level_color
        }