"""
Modèles admin AlloBara
Wallet, retraits, statistiques et gestion financière
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Date, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime, date
import enum

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class WithdrawalStatus(str, enum.Enum):
    """Statut des demandes de retrait"""
    PENDING = "pending"       # En attente de traitement
    PROCESSING = "processing" # En cours de traitement
    COMPLETED = "completed"   # Terminé avec succès
    FAILED = "failed"        # Échec du retrait
    CANCELLED = "cancelled"   # Annulé par l'admin

class TransactionType(str, enum.Enum):
    """Types de transactions"""
    SUBSCRIPTION = "subscription"     # Paiement d'abonnement
    WITHDRAWAL = "withdrawal"         # Retrait d'argent
    REFUND = "refund"                # Remboursement
    COMMISSION = "commission"         # Commission AlloBara
    BONUS = "bonus"                  # Bonus/promotion

class PaymentProvider(str, enum.Enum):
    """Providers de paiement"""
    WAVE = "wave"
    MTN = "mtn" 
    ORANGE = "orange"
    MOOV = "moov"
    BANK = "bank"

# =========================================
# WALLET ADMIN
# =========================================

class AdminWallet(Base):
    """
    Portefeuille administrateur AlloBara
    Centralise tous les revenus des abonnements
    """
    __tablename__ = "admin_wallet"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Soldes
    balance = Column(Integer, default=0, nullable=False)
    total_received = Column(Integer, default=0)
    total_withdrawn = Column(Integer, default=0)
    pending_withdrawals = Column(Integer, default=0)
    
    # Statistiques
    total_transactions = Column(Integer, default=0)
    last_transaction_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def available_balance(self) -> int:
        """Solde disponible (balance - pending_withdrawals)"""
        return self.balance - self.pending_withdrawals
    
    @property
    def formatted_balance(self) -> str:
        """Solde formaté en FCFA"""
        return f"{self.balance:,} FCFA".replace(",", " ")
    
    @property
    def formatted_available(self) -> str:
        """Solde disponible formaté"""
        return f"{self.available_balance:,} FCFA".replace(",", " ")
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "balance": self.balance,
            "formatted_balance": self.formatted_balance,
            "available_balance": self.available_balance,
            "formatted_available": self.formatted_available,
            "total_received": self.total_received,
            "total_withdrawn": self.total_withdrawn,
            "pending_withdrawals": self.pending_withdrawals,
            "total_transactions": self.total_transactions,
            "last_transaction_at": self.last_transaction_at.isoformat() if self.last_transaction_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# =========================================
# DEMANDES DE RETRAIT
# =========================================

class WithdrawalRequest(Base):
    """
    Demandes de retrait des prestataires
    """
    __tablename__ = "withdrawal_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    # Montant
    amount = Column(Integer, nullable=False)
    commission = Column(Integer, default=0)
    net_amount = Column(Integer, nullable=False)
    
    # Coordonnées bancaires
    payment_method = Column(SQLEnum(PaymentProvider), nullable=False)
    phone_number = Column(String(20), nullable=True)
    bank_name = Column(String(100), nullable=True)
    account_number = Column(String(50), nullable=True)
    account_name = Column(String(100), nullable=True)
    
    # Statut
    status = Column(SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    
    # Informations de traitement
    processed_by = Column(Integer, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    transaction_id = Column(String(100), unique=True, nullable=True)
    failure_reason = Column(Text, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def formatted_amount(self) -> str:
        """Montant formaté"""
        return f"{self.amount:,} FCFA".replace(",", " ")
    
    @property
    def formatted_commission(self) -> str:
        """Commission formatée"""
        return f"{self.commission:,} FCFA".replace(",", " ")
    
    @property
    def formatted_net_amount(self) -> str:
        """Montant net formaté"""
        return f"{self.net_amount:,} FCFA".replace(",", " ")
    
    @property
    def status_display(self) -> str:
        """Affichage du statut"""
        status_map = {
            WithdrawalStatus.PENDING: "En attente",
            WithdrawalStatus.PROCESSING: "En cours",
            WithdrawalStatus.COMPLETED: "Terminé",
            WithdrawalStatus.FAILED: "Échoué",
            WithdrawalStatus.CANCELLED: "Annulé"
        }
        return status_map.get(self.status, str(self.status))
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "amount": self.amount,
            "formatted_amount": self.formatted_amount,
            "commission": self.commission,
            "formatted_commission": self.formatted_commission,
            "net_amount": self.net_amount,
            "formatted_net_amount": self.formatted_net_amount,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "phone_number": self.phone_number,
            "bank_name": self.bank_name,
            "account_number": self.account_number,
            "account_name": self.account_name,
            "status": self.status.value if self.status else None,
            "status_display": self.status_display,
            "processed_by": self.processed_by,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "transaction_id": self.transaction_id,
            "failure_reason": self.failure_reason,
            "notes": self.notes,
            "admin_notes": self.admin_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# =========================================
# HISTORIQUE WALLET
# =========================================

class WalletTransaction(Base):
    """
    Historique de toutes les transactions du wallet admin
    """
    __tablename__ = "wallet_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, nullable=False, index=True)
    
    # Transaction
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Integer, nullable=False)
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    
    # Références
    reference_id = Column(Integer, nullable=True)
    reference_type = Column(String(50), nullable=True)
    user_id = Column(Integer, nullable=True, index=True)
    
    # Description
    description = Column(Text, nullable=True)
    metadata = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    @property
    def formatted_amount(self) -> str:
        """Montant formaté"""
        return f"{self.amount:,} FCFA".replace(",", " ")
    
    @property
    def formatted_balance_before(self) -> str:
        """Solde avant formaté"""
        return f"{self.balance_before:,} FCFA".replace(",", " ")
    
    @property
    def formatted_balance_after(self) -> str:
        """Solde après formaté"""
        return f"{self.balance_after:,} FCFA".replace(",", " ")
    
    @property
    def transaction_type_display(self) -> str:
        """Affichage du type"""
        type_map = {
            TransactionType.SUBSCRIPTION: "Abonnement",
            TransactionType.WITHDRAWAL: "Retrait",
            TransactionType.REFUND: "Remboursement",
            TransactionType.COMMISSION: "Commission",
            TransactionType.BONUS: "Bonus"
        }
        return type_map.get(self.transaction_type, str(self.transaction_type))
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire"""
        return {
            "id": self.id,
            "wallet_id": self.wallet_id,
            "transaction_type": self.transaction_type.value if self.transaction_type else None,
            "transaction_type_display": self.transaction_type_display,
            "amount": self.amount,
            "formatted_amount": self.formatted_amount,
            "balance_before": self.balance_before,
            "formatted_balance_before": self.formatted_balance_before,
            "balance_after": self.balance_after,
            "formatted_balance_after": self.formatted_balance_after,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "user_id": self.user_id,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


# =========================================
# STATISTIQUES DE REVENUS
# =========================================

class RevenueStats(Base):
    """
    Statistiques de revenus journaliers
    Agrégation pour les graphiques et rapports
    """
    __tablename__ = "revenue_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    # Nouveaux abonnements
    new_users = Column(Integer, default=0)
    new_subscriptions = Column(Integer, default=0)
    
    # Revenus par plan
    monthly_revenue = Column(Integer, default=0)
    quarterly_revenue = Column(Integer, default=0)
    biannual_revenue = Column(Integer, default=0)
    annual_revenue = Column(Integer, default=0)
    
    # Total
    total_revenue = Column(Integer, default=0)
    
    # Renouvellements
    renewals = Column(Integer, default=0)
    
    # Conversions période d'essai
    trial_to_paid = Column(Integer, default=0)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def formatted_date(self) -> str:
        """Date formatée"""
        return self.date.strftime("%d/%m/%Y")
    
    @property
    def formatted_revenue(self) -> str:
        """Revenu total formaté"""
        return f"{self.total_revenue:,} FCFA".replace(",", " ")
    
    @property
    def subscription_breakdown(self) -> dict:
        """Répartition des abonnements"""
        total = self.new_subscriptions
        if total == 0:
            return {}
        
        monthly = (self.monthly_revenue / 2500) if self.monthly_revenue > 0 else 0
        quarterly = (self.quarterly_revenue / 5500) if self.quarterly_revenue > 0 else 0
        biannual = (self.biannual_revenue / 9500) if self.biannual_revenue > 0 else 0
        annual = (self.annual_revenue / 16500) if self.annual_revenue > 0 else 0
        
        return {
            "monthly": int(monthly),
            "quarterly": int(quarterly),
            "biannual": int(biannual),
            "annual": int(annual)
        }
    
    @property
    def revenue_breakdown(self) -> dict:
        """Répartition des revenus"""
        return {
            "monthly": self.monthly_revenue,
            "quarterly": self.quarterly_revenue,
            "biannual": self.biannual_revenue,
            "annual": self.annual_revenue,
            "total": self.total_revenue
        }
    
    @property
    def trial_conversion_rate(self) -> float:
        """Taux de conversion période d'essai"""
        if self.new_users == 0:
            return 0.0
        return round((self.trial_to_paid / self.new_users) * 100, 2)
    
    @property
    def average_revenue_per_user(self) -> int:
        """Revenu moyen par utilisateur"""
        if self.new_subscriptions == 0:
            return 0
        return round(self.total_revenue / self.new_subscriptions)
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire pour l'API"""
        return {
            "date": self.formatted_date,
            "new_users": self.new_users,
            "new_subscriptions": self.new_subscriptions,
            "total_revenue": self.total_revenue,
            "formatted_revenue": self.formatted_revenue,
            "subscription_breakdown": self.subscription_breakdown,
            "revenue_breakdown": self.revenue_breakdown,
            "trial_conversion_rate": self.trial_conversion_rate,
            "average_revenue_per_user": self.average_revenue_per_user
        }


# =========================================
# STATISTIQUES JOURNALIÈRES (NOUVEAU)
# =========================================

class DailyStats(Base):
    """
    Statistiques journalières agrégées
    Utilisé pour les graphiques et analytics
    """
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    # Métriques utilisateurs
    total_users = Column(Integer, default=0)
    new_users = Column(Integer, default=0)
    total_providers = Column(Integer, default=0)
    new_providers = Column(Integer, default=0)
    active_users = Column(Integer, default=0)
    
    # Métriques financières
    total_revenue = Column(Integer, default=0)
    new_subscriptions = Column(Integer, default=0)
    active_subscriptions = Column(Integer, default=0)
    trial_conversions = Column(Integer, default=0)
    
    # Métriques d'engagement
    total_searches = Column(Integer, default=0)
    total_quotes = Column(Integer, default=0)
    total_reviews = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def formatted_date(self) -> str:
        """Date formatée"""
        return self.date.strftime("%d/%m/%Y")
    
    @property
    def formatted_revenue(self) -> str:
        """Revenu formaté"""
        return f"{self.total_revenue:,} FCFA".replace(",", " ")
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire"""
        return {
            "date": self.formatted_date,
            "total_users": self.total_users,
            "new_users": self.new_users,
            "total_providers": self.total_providers,
            "new_providers": self.new_providers,
            "active_users": self.active_users,
            "total_revenue": self.total_revenue,
            "formatted_revenue": self.formatted_revenue,
            "new_subscriptions": self.new_subscriptions,
            "active_subscriptions": self.active_subscriptions,
            "trial_conversions": self.trial_conversions,
            "total_searches": self.total_searches,
            "total_quotes": self.total_quotes,
            "total_reviews": self.total_reviews
        }
