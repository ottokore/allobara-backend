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
    user = relationship("User", backref="payments")
    subscription = relationship("Subscription", backref="payments")
    
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