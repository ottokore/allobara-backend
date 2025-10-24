"""
Schémas Pydantic pour les abonnements
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, validator, Field
from enum import Enum

# =========================================
# ENUMS POUR VALIDATION
# =========================================

class SubscriptionPlanEnum(str, Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    BIANNUAL = "biannual"
    ANNUAL = "annual"

class PaymentMethodEnum(str, Enum):
    WAVE = "wave"
    MTN = "mtn"
    ORANGE = "orange"
    MOOV = "moov"

# =========================================
# SCHÉMAS DE REQUÊTE
# =========================================

class SubscriptionCreateRequest(BaseModel):
    """
    Demande de création d'abonnement
    """
    plan: SubscriptionPlanEnum = Field(..., description="Plan d'abonnement choisi")
    payment_method: PaymentMethodEnum = Field(default=PaymentMethodEnum.WAVE, description="Méthode de paiement")
    referral_code: Optional[str] = Field(None, max_length=10, description="Code de parrainage")
    
    @validator('referral_code')
    def validate_referral_code(cls, v):
        if v and not v.startswith('ALL'):
            raise ValueError('Code de parrainage invalide')
        return v

class SubscriptionRenewRequest(BaseModel):
    """
    Demande de renouvellement d'abonnement
    """
    new_plan: Optional[SubscriptionPlanEnum] = Field(None, description="Nouveau plan (optionnel)")
    payment_method: PaymentMethodEnum = Field(default=PaymentMethodEnum.WAVE)

class PaymentInitiationRequest(BaseModel):
    """
    Initiation d'un paiement
    """
    subscription_id: int = Field(..., description="ID de l'abonnement")
    phone_number: str = Field(..., description="Numéro Wave pour le paiement")
    
    @validator('phone_number')
    def validate_wave_phone(cls, v):
        # Validation basique du numéro Wave
        import re
        cleaned = re.sub(r'[^\d+]', '', v)
        if not cleaned.startswith('+225') and not cleaned.startswith('225'):
            if cleaned.startswith('0'):
                cleaned = '+225' + cleaned[1:]
            else:
                cleaned = '+225' + cleaned
        return cleaned

class SubscriptionCancelRequest(BaseModel):
    """
    Demande d'annulation d'abonnement
    """
    reason: Optional[str] = Field(None, max_length=500, description="Raison de l'annulation")
    immediate: bool = Field(False, description="Annulation immédiate ou à la fin de la période")

# =========================================
# SCHÉMAS DE RÉPONSE
# =========================================

class SubscriptionPlanResponse(BaseModel):
    """
    Détails d'un plan d'abonnement
    """
    id: str
    name: str
    duration_months: int
    price: int
    original_price: int
    description: str
    features: List[str]
    savings: int
    is_popular: bool = False
    is_best_value: bool = False

class SubscriptionStatusResponse(BaseModel):
    """
    Statut complet de l'abonnement utilisateur
    """
    has_subscription: bool
    subscription_id: Optional[int] = None
    plan: Optional[str] = None
    plan_display: Optional[str] = None
    status: Optional[str] = None
    status_display: Optional[str] = None
    is_active: bool = False
    is_trial: bool = False
    price: Optional[float] = None
    formatted_price: Optional[str] = None
    days_remaining: Optional[int] = None
    hours_remaining: Optional[int] = None
    is_expiring_soon: bool = False
    is_expiring_today: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    progress_percentage: Optional[int] = None
    auto_renewal: bool = False
    can_renew: bool = False
    payment_status: Optional[str] = None
    savings_vs_monthly: Optional[float] = None

class PaymentResponse(BaseModel):
    """
    Réponse après initiation de paiement
    """
    success: bool
    message: str
    payment_id: Optional[str] = None
    payment_url: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "FCFA"
    expires_in: int = 1800  # 30 minutes

class SubscriptionHistoryItem(BaseModel):
    """
    Élément d'historique d'abonnement
    """
    id: int
    plan: str
    plan_display: str
    status: str
    price: float
    formatted_price: str
    start_date: datetime
    end_date: datetime
    payment_date: Optional[datetime]
    payment_method: Optional[str]
    is_from_referral: bool
    discount_amount: float

class SubscriptionAnalyticsResponse(BaseModel):
    """
    Analytics détaillés de l'abonnement
    """
    subscription: SubscriptionStatusResponse
    analytics: dict
    recommendations: List[str]

# =========================================
# SCHÉMAS PARRAINAGE
# =========================================

class ReferralStatsResponse(BaseModel):
    """
    Statistiques de parrainage
    """
    referral_code: str
    total_invitations: int
    paid_referrals: int
    bonus_months_earned: int
    potential_next_bonus: int

class ReferralInviteRequest(BaseModel):
    """
    Invitation de parrainage
    """
    phone_numbers: List[str] = Field(..., max_items=10, description="Numéros à inviter")
    personal_message: Optional[str] = Field(None, max_length=200, description="Message personnel")

# =========================================
# SCHÉMAS ADMIN
# =========================================

class AdminSubscriptionResponse(BaseModel):
    """
    Réponse abonnement pour l'admin
    """
    id: int
    user_id: int
    user_name: str
    user_phone: str
    plan: str
    status: str
    price: float
    start_date: datetime
    end_date: datetime
    days_remaining: int
    payment_status: str
    payment_method: Optional[str]
    is_from_referral: bool
    created_at: datetime

class SubscriptionStatsResponse(BaseModel):
    """
    Statistiques globales des abonnements
    """
    total_subscriptions: int
    active_subscriptions: int
    trial_subscriptions: int
    expired_subscriptions: int
    
    # Par plan
    monthly_count: int
    quarterly_count: int
    biannual_count: int
    annual_count: int
    
    # Revenus
    total_revenue: float
    monthly_revenue: float
    quarterly_revenue: float
    biannual_revenue: float
    annual_revenue: float
    
    # Métriques
    average_subscription_duration: float
    churn_rate: float
    conversion_rate: float

class AdminSubscriptionAction(BaseModel):
    """
    Action admin sur un abonnement
    """
    action: str = Field(..., description="suspend, activate, extend, cancel")
    reason: Optional[str] = Field(None, max_length=500)
    duration_days: Optional[int] = Field(None, ge=1, le=365, description="Pour extension")

# =========================================
# SCHÉMAS DE NOTIFICATION
# =========================================

class SubscriptionNotificationRequest(BaseModel):
    """
    Demande d'envoi de notification d'abonnement
    """
    user_ids: List[int] = Field(..., max_items=100)
    message_type: str = Field(..., description="expiry_warning, payment_reminder, welcome")
    custom_message: Optional[str] = Field(None, max_length=500)

class ExpiryCheckResponse(BaseModel):
    """
    Résultat de la vérification des expirations
    """
    success: bool
    expiring_warnings_sent: int
    expired_today: int
    message: str
    processed_subscriptions: List[int] = []

# =========================================
# SCHÉMAS VALIDATION PAIEMENT
# =========================================

class PaymentWebhookData(BaseModel):
    """
    Données reçues du webhook de paiement
    """
    transaction_id: str
    status: str
    amount: float
    currency: str = "FCFA"
    subscription_id: Optional[int] = None
    phone_number: Optional[str] = None
    provider_reference: Optional[str] = None
    timestamp: datetime

class PaymentVerificationResponse(BaseModel):
    """
    Réponse de vérification de paiement
    """
    success: bool
    message: str
    transaction_verified: bool
    subscription_activated: bool
    user_notified: bool