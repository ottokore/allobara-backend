"""
Modèle des abonnements AlloBara
Gestion des plans, paiements et période d'essai gratuite
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum

from app.db.database import Base
from app.core.config import settings

# =========================================
# ENUMS
# =========================================

class SubscriptionPlan(str, enum.Enum):
    """Plans d'abonnement disponibles avec nouveaux prix"""
    MONTHLY = "monthly"        # 1 mois - 2500 FCFA
    QUARTERLY = "quarterly"    # 3 mois - 5500 FCFA
    BIANNUAL = "semiannual"     # 6 mois - 9500 FCFA
    ANNUAL = "annual"         # 12 mois - 16500 FCFA

class SubscriptionStatus(str, enum.Enum):
    """Statuts d'abonnement"""
    PENDING = "pending"       # En attente de paiement
    ACTIVE = "active"         # Actif et payé
    EXPIRED = "expired"       # Expiré
    SUSPENDED = "suspended"   # Suspendu par admin
    TRIAL = "trial"          # Période d'essai gratuite
    CANCELLED = "cancelled"   # Annulé par l'utilisateur

class PaymentStatus(str, enum.Enum):
    """Statut des paiements"""
    PENDING = "pending"       # En attente
    SUCCESS = "success"       # Réussi
    FAILED = "failed"         # Échoué
    CANCELLED = "cancelled"   # Annulé
    REFUNDED = "refunded"     # Remboursé

# =========================================
# MODÈLE ABONNEMENT
# =========================================

class Subscription(Base):
    """
    Modèle des abonnements utilisateurs AlloBara
    Relation 1:1 avec User
    """
    __tablename__ = "subscriptions"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # =====================================
    # PLAN ET STATUT
    # =====================================
    plan = Column(SQLEnum(SubscriptionPlan), nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    previous_status = Column(SQLEnum(SubscriptionStatus), nullable=True)  # Statut précédent
    
    # =====================================
    # PRICING ET PAIEMENT
    # =====================================
    price = Column(Float, nullable=False)                    # Prix payé
    original_price = Column(Float, nullable=True)            # Prix avant réduction
    discount_amount = Column(Float, default=0.0)             # Montant de la réduction
    discount_code = Column(String(50), nullable=True)        # Code promo utilisé
    
    payment_method = Column(String(20), nullable=True)       # "wave", "mtn", "orange"
    payment_reference = Column(String(100), nullable=True)   # Référence transaction
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    payment_provider_response = Column(Text, nullable=True)   # Réponse du provider
    
    # =====================================
    # DATES IMPORTANTES
    # =====================================
    start_date = Column(DateTime, default=func.now(), nullable=False)
    end_date = Column(DateTime, nullable=False)
    trial_start_date = Column(DateTime, nullable=True)        # Début période d'essai
    trial_end_date = Column(DateTime, nullable=True)          # Fin période d'essai
    
    # Dates de paiement
    payment_date = Column(DateTime, nullable=True)            # Date du paiement
    next_billing_date = Column(DateTime, nullable=True)       # Prochaine échéance
    
    # =====================================
    # RENOUVELLEMENT
    # =====================================
    auto_renewal = Column(Boolean, default=False)            # Renouvellement automatique
    renewal_attempts = Column(Integer, default=0)            # Tentatives de renouvellement
    max_renewal_attempts = Column(Integer, default=3)        # Max tentatives
    
    # Notifications d'expiration
    expiry_notification_sent = Column(Boolean, default=False)
    expiry_warning_sent = Column(Boolean, default=False)     # Avertissement 7 jours avant
    
    # =====================================
    # PARRAINAGE ET PROMOTIONS
    # =====================================
    is_from_referral = Column(Boolean, default=False)        # Vient d'un parrainage
    referral_discount = Column(Float, default=0.0)           # Réduction parrainage
    is_promotional = Column(Boolean, default=False)          # Abonnement promotionnel
    
    # =====================================
    # HISTORIQUE ET MÉTA
    # =====================================
    subscription_number = Column(String(20), unique=True, nullable=True)  # SUB2024001
    notes = Column(Text, nullable=True)                       # Notes admin
    
    # Tracking
    ip_address = Column(String(45), nullable=True)           # IP lors de la souscription
    user_agent = Column(String(500), nullable=True)          # User agent
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    activated_at = Column(DateTime, nullable=True)            # Date d'activation
    cancelled_at = Column(DateTime, nullable=True)           # Date d'annulation
    
    # =====================================
    # RELATIONS
    # =====================================
    user = relationship("User", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")  # 🔧 FIX: Relation ajoutée
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<Subscription(user_id={self.user_id}, plan={self.plan.value}, status={self.status.value})>"
    
    def __str__(self):
        return f"Abonnement {self.plan.value} - {self.status.value}"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def is_active(self) -> bool:
        """Vérifier si l'abonnement est actif"""
        now = datetime.utcnow()
        active_statuses = [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]
        return (
            self.status in active_statuses and
            self.end_date and
            self.end_date > now
        )
    
    @property
    def is_trial(self) -> bool:
        """Vérifier si c'est une période d'essai"""
        return self.status == SubscriptionStatus.TRIAL
    
    @property
    def is_expired(self) -> bool:
        """Vérifier si l'abonnement est expiré"""
        if not self.end_date:
            return False
        return datetime.utcnow() > self.end_date
    
    @property
    def days_remaining(self) -> int:
        """Nombre de jours restants"""
        if not self.end_date:
            return 0
        delta = self.end_date - datetime.utcnow()
        return max(0, delta.days)
    
    @property
    def hours_remaining(self) -> int:
        """Nombre d'heures restantes"""
        if not self.end_date:
            return 0
        delta = self.end_date - datetime.utcnow()
        return max(0, int(delta.total_seconds() // 3600))
    
    @property
    def is_expiring_soon(self) -> bool:
        """Vérifier si expire dans les 7 prochains jours"""
        return 0 < self.days_remaining <= 7
    
    @property
    def is_expiring_today(self) -> bool:
        """Vérifier si expire aujourd'hui"""
        return self.days_remaining == 0 and not self.is_expired
    
    @property
    def plan_display_name(self) -> str:
        """Nom d'affichage du plan"""
        plan_names = {
            SubscriptionPlan.MONTHLY: "Mensuel",
            SubscriptionPlan.QUARTERLY: "Trimestriel", 
            SubscriptionPlan.BIANNUAL: "Semestriel",
            SubscriptionPlan.ANNUAL: "Annuel"
        }
        return plan_names.get(self.plan, self.plan.value)
    
    @property
    def status_display_name(self) -> str:
        """Nom d'affichage du statut"""
        status_names = {
            SubscriptionStatus.PENDING: "En attente",
            SubscriptionStatus.ACTIVE: "Actif",
            SubscriptionStatus.EXPIRED: "Expiré",
            SubscriptionStatus.SUSPENDED: "Suspendu",
            SubscriptionStatus.TRIAL: "Période d'essai",
            SubscriptionStatus.CANCELLED: "Annulé"
        }
        return status_names.get(self.status, self.status.value)
    
    @property
    def formatted_price(self) -> str:
        """Prix formaté en FCFA"""
        return f"{int(self.price):,} FCFA".replace(",", " ")
    
    @property
    def plan_duration_months(self) -> int:
        """Durée du plan en mois"""
        durations = {
            SubscriptionPlan.MONTHLY: 1,
            SubscriptionPlan.QUARTERLY: 3,
            SubscriptionPlan.BIANNUAL: 6,
            SubscriptionPlan.ANNUAL: 12
        }
        return durations.get(self.plan, 1)
    
    @property
    def savings_vs_monthly(self) -> float:
        """Économies par rapport au plan mensuel"""
        if self.plan == SubscriptionPlan.MONTHLY:
            return 0.0
        
        monthly_price = settings.PRICE_MONTHLY
        equivalent_monthly_cost = monthly_price * self.plan_duration_months
        return equivalent_monthly_cost - self.price
    
    @property
    def progress_percentage(self) -> int:
        """Pourcentage de progression de l'abonnement"""
        if not self.start_date or not self.end_date:
            return 0
        
        now = datetime.utcnow()
        total_duration = self.end_date - self.start_date
        elapsed_duration = now - self.start_date
        
        if elapsed_duration.total_seconds() <= 0:
            return 0
        if elapsed_duration >= total_duration:
            return 100
            
        return int((elapsed_duration.total_seconds() / total_duration.total_seconds()) * 100)
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @classmethod
    def get_plan_price(cls, plan: SubscriptionPlan) -> int:
        """Obtenir le prix d'un plan"""
        return settings.SUBSCRIPTION_PRICES.get(plan.value, 0)
    
    @classmethod
    def create_trial_subscription(cls, user_id: int):
        """Créer un abonnement d'essai"""
        trial_end = datetime.utcnow() + timedelta(days=settings.FREE_TRIAL_DAYS)
        
        return cls(
            user_id=user_id,
            plan=SubscriptionPlan.MONTHLY,  # Plan par défaut pour l'essai
            status=SubscriptionStatus.TRIAL,
            price=0.0,
            start_date=datetime.utcnow(),
            end_date=trial_end,
            trial_start_date=datetime.utcnow(),
            trial_end_date=trial_end,
            payment_status=PaymentStatus.SUCCESS  # Essai = "payé"
        )
    
    def activate(self, payment_reference: str = None):
        """Activer l'abonnement"""
        self.status = SubscriptionStatus.ACTIVE
        self.activated_at = datetime.utcnow()
        self.payment_status = PaymentStatus.SUCCESS
        if payment_reference:
            self.payment_reference = payment_reference
    
    def suspend(self, reason: str = None):
        """Suspendre l'abonnement"""
        self.previous_status = self.status
        self.status = SubscriptionStatus.SUSPENDED
        if reason:
            self.notes = f"Suspendu: {reason}"
    
    def unsuspend(self):
        """Réactiver un abonnement suspendu"""
        if self.previous_status:
            self.status = self.previous_status
        else:
            self.status = SubscriptionStatus.ACTIVE
        self.previous_status = None
    
    def cancel(self):
        """Annuler l'abonnement"""
        self.status = SubscriptionStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.auto_renewal = False
    
    def renew(self, new_plan: SubscriptionPlan = None):
        """Renouveler l'abonnement"""
        if new_plan:
            self.plan = new_plan
            self.price = self.get_plan_price(new_plan)
        
        # Calculer la nouvelle date de fin
        duration_months = self.plan_duration_months
        self.start_date = datetime.utcnow()
        self.end_date = self.start_date + timedelta(days=duration_months * 30)
        
        self.status = SubscriptionStatus.ACTIVE
        self.payment_status = PaymentStatus.PENDING
        self.renewal_attempts = 0
        self.expiry_notification_sent = False
        self.expiry_warning_sent = False
    
    def mark_expiry_warning_sent(self):
        """Marquer que l'avertissement d'expiration a été envoyé"""
        self.expiry_warning_sent = True
    
    def mark_expiry_notification_sent(self):
        """Marquer que la notification d'expiration a été envoyée"""
        self.expiry_notification_sent = True
    
    def should_send_expiry_warning(self) -> bool:
        """Vérifier s'il faut envoyer l'avertissement d'expiration"""
        return (
            self.is_expiring_soon and
            not self.expiry_warning_sent and
            self.status == SubscriptionStatus.ACTIVE
        )
    
    def should_send_expiry_notification(self) -> bool:
        """Vérifier s'il faut envoyer la notification d'expiration"""
        return (
            self.is_expired and
            not self.expiry_notification_sent
        )
    
    def can_renew(self) -> bool:
        """Vérifier si l'abonnement peut être renouvelé"""
        return (
            self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.EXPIRED] and
            self.renewal_attempts < self.max_renewal_attempts
        )
    
    def get_renewal_url(self) -> str:
        """Obtenir l'URL de renouvellement"""
        return f"/subscriptions/{self.id}/renew"
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan": self.plan.value,
            "plan_display": self.plan_display_name,
            "status": self.status.value,
            "status_display": self.status_display_name,
            "price": self.price,
            "formatted_price": self.formatted_price,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "days_remaining": self.days_remaining,
            "is_active": self.is_active,
            "is_trial": self.is_trial,
            "is_expiring_soon": self.is_expiring_soon,
            "progress_percentage": self.progress_percentage,
            "auto_renewal": self.auto_renewal,
            "payment_status": self.payment_status.value if self.payment_status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
