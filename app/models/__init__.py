"""
Modèles de données AlloBara
Import centralisé de tous les modèles SQLAlchemy
"""

from .user import User, UserRole, Gender, DocumentType
from .subscription import Subscription, SubscriptionPlan, SubscriptionStatus, PaymentStatus
from .portfolio import PortfolioItem, PortfolioType, PortfolioStatus, CompressionStatus
from .review import Review, ReviewStatus, ReviewSource
from .favorite import Favorite  # 🆕 NOUVEAU - Système de favoris
from .daily_stats import DailyStats
from .admin import AdminDailyStats, AdminWallet, WithdrawalRequest
from .audit import AuditLog, AuditAction, AuditLevel
from .notification import Notification, NotificationType, NotificationChannel, NotificationStatus

# 🆕 NOUVEAUX MODÈLES - Système Anti-Fraude & CinetPay
from .system_settings import SystemSettings, SettingType
from .device_fingerprint import DeviceFingerprint, user_devices
from .fraud_log import FraudLog, FraudType, FraudSeverity, FraudAction
from .payment import Payment, PaymentProvider, PaymentMethod
from .payment import PaymentStatus as PaymentStatusEnum

# Export de tous les modèles
__all__ = [
    # Modèles principaux
    "User", "UserRole", "Gender", "DocumentType",
    "Subscription", "SubscriptionPlan", "SubscriptionStatus", "PaymentStatus",
    "PortfolioItem", "PortfolioType", "PortfolioStatus", "CompressionStatus",
    "Review", "ReviewStatus", "ReviewSource",
    "Favorite",  # 🆕 Système de favoris
    
    # Statistiques
    "DailyStats",
    "AdminDailyStats",
    
    # Modèles système
    "AuditLog", "AuditAction", "AuditLevel",
    "Notification", "NotificationType", "NotificationChannel", "NotificationStatus",
    
    # 🆕 Nouveaux modèles
    "SystemSettings", "SettingType",
    "DeviceFingerprint", "user_devices",
    "FraudLog", "FraudType", "FraudSeverity", "FraudAction",
    "Payment", "PaymentProvider", "PaymentMethod", "PaymentStatusEnum"
]