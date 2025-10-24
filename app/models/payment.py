"""
Modèle Payment AlloBara
Gestion des transactions de paiement avec CinetPay
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class PaymentProvider(str, enum.Enum):
    """Fournisseurs de paiement"""
    CINETPAY = "cinetpay"
    MANUAL = "manual"

class PaymentMethod(str, enum.Enum):
    """Moyens de paiement"""
    ORANGE_MONEY = "ORANGE_MONEY"
    MTN_MONEY = "MTN_MONEY"
    MOOV_MONEY = "MOOV_MONEY"
    WAVE = "WAVE"

class PaymentStatus(str, enum.Enum):
    """Statuts de paiement"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

# =========================================
# MODÈLE PAYMENT
# =========================================

class Payment(Base):
    """
    Transactions de paiement AlloBara
    Gère les paiements CinetPay pour les abonnements
    """
    __tablename__ = "payments"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # IDs CinetPay
    cinetpay_transaction_id = Column(String(100), unique=True, index=True, nullable=True)
    cinetpay_payment_token = Column(String(255), nullable=True)
    cinetpay_payment_url = Column(Text, nullable=True)
    
    # =====================================
    # RÉFÉRENCES
    # =====================================
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    
    # =====================================
    # INFORMATIONS DE PAIEMENT
    # =====================================
    provider = Column(SQLEnum(PaymentProvider), default=PaymentProvider.CINETPAY, nullable=False)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=True)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="XOF", nullable=False)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    description = Column(Text, nullable=True)
    
    # =====================================
    # INFORMATIONS CLIENT
    # =====================================
    customer_phone = Column(String(20), nullable=False)
    customer_name = Column(String(100), nullable=True)
    
    # =====================================
    # RÉPONSES PROVIDER
    # =====================================
    provider_response = Column(JSON, nullable=True)
    provider_error_message = Column(Text, nullable=True)
    
    # Webhook
    webhook_received = Column(Boolean, default=False, nullable=False)
    webhook_data = Column(JSON, nullable=True)
    webhook_received_at = Column(DateTime, nullable=True)
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # =====================================
    # RELATIONS
    # =====================================
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @classmethod
    def generate_transaction_id(cls) -> str:
        """Générer un ID de transaction unique"""
        import random
        import string
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ALB{timestamp}{random_str}"
    
    @classmethod
    def create_payment(cls, db, user_id: int, amount: float, **kwargs):
        """Créer un nouveau paiement"""
        payment = cls(
            transaction_id=cls.generate_transaction_id(),
            user_id=user_id,
            amount=amount,
            expires_at=datetime.utcnow() + timedelta(minutes=30),
            **kwargs
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        return payment
    
    @classmethod
    def get_by_transaction_id(cls, db, transaction_id: str):
        """Récupérer un paiement par son transaction_id"""
        return db.query(cls).filter(cls.transaction_id == transaction_id).first()
    
    def mark_as_success(self, cinetpay_transaction_id: str = None):
        """Marquer le paiement comme réussi"""
        self.status = PaymentStatus.SUCCESS
        self.completed_at = datetime.utcnow()
        
        if cinetpay_transaction_id:
            self.cinetpay_transaction_id = cinetpay_transaction_id
    
    def mark_as_failed(self, error_message: str = None):
        """Marquer le paiement comme échoué"""
        self.status = PaymentStatus.FAILED
        
        if error_message:
            self.provider_error_message = error_message
    
    def set_cinetpay_data(self, payment_token: str, payment_url: str):
        """Définir les données CinetPay"""
        self.cinetpay_payment_token = payment_token
        self.cinetpay_payment_url = payment_url
    
    def update_from_webhook(self, webhook_data: dict):
        """Mettre à jour depuis les données webhook"""
        self.webhook_received = True
        self.webhook_data = webhook_data
        self.webhook_received_at = datetime.utcnow()
    
    @property
    def is_expired(self) -> bool:
        """Vérifier si le lien de paiement a expiré"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def formatted_amount(self) -> str:
        """Montant formaté"""
        return f"{int(self.amount):,} {self.currency}".replace(",", " ")
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire"""
        return {
            "id": self.id,
            "transaction_id": self.transaction_id,
            "cinetpay_transaction_id": self.cinetpay_transaction_id,
            "user_id": self.user_id,
            "subscription_id": self.subscription_id,
            "provider": self.provider.value if self.provider else None,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value if self.status else None,
            "description": self.description,
            "customer_phone": self.customer_phone,
            "customer_name": self.customer_name,
            "formatted_amount": self.formatted_amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired,
            "webhook_received": self.webhook_received,
            "webhook_received_at": self.webhook_received_at.isoformat() if self.webhook_received_at else None,
        }
