# app/db/base.py

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# Schéma de nommage des contraintes pour PostgreSQL
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

# Métadonnées avec convention de nommage
metadata = MetaData(naming_convention=naming_convention)

# Base pour tous les modèles SQLAlchemy
Base = declarative_base(metadata=metadata)

# Import de tous les modèles pour Alembic
from app.models.user import User
from app.models.subscription import Subscription
from app.models.portfolio import PortfolioItem
from app.models.review import Review
from app.models.admin import AdminWallet, WithdrawalRequest, DailyStats
from app.models.audit import AuditLog, AuditAction
from app.models.notification import Notification, NotificationType

# Liste de tous les modèles (utile pour les migrations)
__all__ = [
    "Base", 
    "User", 
    "Subscription", 
    "PortfolioItem", 
    "Review",
    "AdminWallet",
    "WithdrawalRequest", 
    "DailyStats",
    "AuditLog",
    "AuditAction",
    "Notification",
    "NotificationType"
]