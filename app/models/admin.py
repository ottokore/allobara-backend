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
    
    # =====================================
    # IDENTIFIANT
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    
    # =====================================
    # SOLDES
    # =====================================
    total_balance = Column(Float, default=0.0, nullable=False)        # Solde total
    available_balance = Column(Float, default=0.0, nullable=False)    # Solde disponible
    pending_balance = Column(Float, default=0.0, nullable=False)      # Solde en attente
    withdrawn_balance = Column(Float, default=0.0, nullable=False)    # Total retiré
    
    # =====================================
    # STATISTIQUES REVENUS
    # =====================================
    today_revenue = Column(Float, default=0.0)           # Revenus aujourd'hui
    week_revenue = Column(Float, default=0.0)            # Revenus cette semaine
    month_revenue = Column(Float, default=0.0)           # Revenus ce mois
    year_revenue = Column(Float, default=0.0)            # Revenus cette année
    
    # Compteurs transactions
    total_transactions = Column(Integer, default=0)       # Nombre total de transactions
    today_transactions = Column(Integer, default=0)       # Transactions aujourd'hui
    
    # =====================================
    # COMMISSION ET FEES
    # =====================================
    commission_rate = Column(Float, default=0.0)         # Taux de commission (futur)
    processing_fee = Column(Float, default=0.0)          # Frais de traitement
    
    # =====================================
    # MÉTADONNÉES
    # =====================================
    last_transaction_date = Column(DateTime, nullable=True)  # Dernière transaction
    last_withdrawal_date = Column(DateTime, nullable=True)   # Dernier retrait
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Informations du compte Wave principal
    wave_account_number = Column(String(20), nullable=True)  # Numéro de compte Wave
    wave_account_name = Column(String(100), nullable=True)   # Nom du compte
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<AdminWallet(total={self.total_balance} FCFA, available={self.available_balance} FCFA)>"
    
    def __str__(self):
        return f"Wallet Admin - {self.formatted_total_balance} FCFA"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def formatted_total_balance(self) -> str:
        """Solde total formaté"""
        return f"{int(self.total_balance):,} FCFA".replace(",", " ")
    
    @property
    def formatted_available_balance(self) -> str:
        """Solde disponible formaté"""
        return f"{int(self.available_balance):,} FCFA".replace(",", " ")
    
    @property
    def formatted_today_revenue(self) -> str:
        """Revenus du jour formatés"""
        return f"{int(self.today_revenue):,} FCFA".replace(",", " ")
    
    @property
    def can_withdraw(self) -> bool:
        """Vérifier si un retrait est possible"""
        return self.available_balance > 0
    
    @property
    def pending_withdrawal_ratio(self) -> float:
        """Ratio de solde en attente"""
        if self.total_balance == 0:
            return 0.0
        return self.pending_balance / self.total_balance
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    def add_revenue(self, amount: float, transaction_type: TransactionType = TransactionType.SUBSCRIPTION):
        """Ajouter des revenus au wallet"""
        if amount <= 0:
            return False
        
        self.total_balance += amount
        self.available_balance += amount
        self.today_revenue += amount
        self.month_revenue += amount
        self.year_revenue += amount
        self.total_transactions += 1
        self.today_transactions += 1
        self.last_transaction_date = datetime.utcnow()
        self.last_updated = datetime.utcnow()
        
        return True
    
    def reserve_for_withdrawal(self, amount: float) -> bool:
        """Réserver un montant pour retrait"""
        if amount > self.available_balance:
            return False
        
        self.available_balance -= amount
        self.pending_balance += amount
        self.last_updated = datetime.utcnow()
        
        return True
    
    def complete_withdrawal(self, amount: float) -> bool:
        """Finaliser un retrait"""
        if amount > self.pending_balance:
            return False
        
        self.pending_balance -= amount
        self.withdrawn_balance += amount
        self.last_withdrawal_date = datetime.utcnow()
        self.last_updated = datetime.utcnow()
        
        return True
    
    def cancel_withdrawal(self, amount: float) -> bool:
        """Annuler un retrait"""
        if amount > self.pending_balance:
            return False
        
        self.pending_balance -= amount
        self.available_balance += amount
        self.last_updated = datetime.utcnow()
        
        return True
    
    def reset_daily_stats(self):
        """Remettre à zéro les stats journalières"""
        self.today_revenue = 0.0
        self.today_transactions = 0
        self.last_updated = datetime.utcnow()

# =========================================
# DEMANDES DE RETRAIT
# =========================================

class WithdrawalRequest(Base):
    """
    Demandes de retrait d'argent par l'admin
    """
    __tablename__ = "withdrawal_requests"
    __table_args__ = {'extend_existing': True}  # 🔧 FIX: Évite l'erreur "already defined"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String(20), unique=True, index=True)  # WDR2024001
    
    # =====================================
    # MONTANT ET DESTINATION
    # =====================================
    amount = Column(Float, nullable=False)                # Montant demandé
    provider = Column(SQLEnum(PaymentProvider), nullable=False) # Wave, MTN, etc.
    destination_number = Column(String(20), nullable=False)  # Numéro de destination
    destination_name = Column(String(100), nullable=True)    # Nom du bénéficiaire
    
    # =====================================
    # STATUT ET TRAITEMENT
    # =====================================
    status = Column(SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING)
    
    # Détails du traitement
    processed_at = Column(DateTime, nullable=True)        # Date de traitement
    completed_at = Column(DateTime, nullable=True)        # Date de finalisation
    failed_at = Column(DateTime, nullable=True)           # Date d'échec
    
    # Réponse du provider
    provider_reference = Column(String(100), nullable=True)  # Référence externe
    provider_response = Column(Text, nullable=True)          # Réponse complète
    error_message = Column(String(500), nullable=True)      # Message d'erreur
    
    # =====================================
    # FRAIS ET COMMISSION
    # =====================================
    fees = Column(Float, default=0.0)                    # Frais de retrait
    net_amount = Column(Float, nullable=True)             # Montant net reçu
    
    # =====================================
    # MÉTADONNÉES
    # =====================================
    notes = Column(Text, nullable=True)                   # Notes admin
    ip_address = Column(String(45), nullable=True)       # IP de la demande
    user_agent = Column(String(500), nullable=True)      # User agent
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<WithdrawalRequest(ref={self.reference}, amount={self.amount}, status={self.status.value})>"
    
    def __str__(self):
        return f"Retrait {self.reference} - {self.formatted_amount}"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def formatted_amount(self) -> str:
        """Montant formaté"""
        return f"{int(self.amount):,} FCFA".replace(",", " ")
    
    @property
    def formatted_net_amount(self) -> str:
        """Montant net formaté"""
        if self.net_amount:
            return f"{int(self.net_amount):,} FCFA".replace(",", " ")
        return self.formatted_amount
    
    @property
    def status_display(self) -> str:
        """Statut d'affichage"""
        status_names = {
            WithdrawalStatus.PENDING: "En attente",
            WithdrawalStatus.PROCESSING: "En cours",
            WithdrawalStatus.COMPLETED: "Terminé",
            WithdrawalStatus.FAILED: "Échec",
            WithdrawalStatus.CANCELLED: "Annulé"
        }
        return status_names.get(self.status, self.status.value)
    
    @property
    def is_pending(self) -> bool:
        """Vérifier si en attente"""
        return self.status == WithdrawalStatus.PENDING
    
    @property
    def is_completed(self) -> bool:
        """Vérifier si terminé"""
        return self.status == WithdrawalStatus.COMPLETED
    
    @property
    def can_be_cancelled(self) -> bool:
        """Vérifier si peut être annulé"""
        return self.status in [WithdrawalStatus.PENDING, WithdrawalStatus.PROCESSING]
    
    @property
    def processing_time_minutes(self) -> int:
        """Temps de traitement en minutes"""
        if self.completed_at and self.created_at:
            delta = self.completed_at - self.created_at
            return int(delta.total_seconds() / 60)
        return 0
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    def start_processing(self):
        """Démarrer le traitement"""
        self.status = WithdrawalStatus.PROCESSING
        self.processed_at = datetime.utcnow()
    
    def complete(self, provider_reference: str = None, net_amount: float = None):
        """Finaliser le retrait"""
        self.status = WithdrawalStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if provider_reference:
            self.provider_reference = provider_reference
        if net_amount:
            self.net_amount = net_amount
    
    def fail(self, error_message: str):
        """Marquer comme échoué"""
        self.status = WithdrawalStatus.FAILED
        self.failed_at = datetime.utcnow()
        self.error_message = error_message
    
    def cancel(self, reason: str = None):
        """Annuler la demande"""
        self.status = WithdrawalStatus.CANCELLED
        if reason:
            self.notes = f"Annulé: {reason}"
    
    @classmethod
    def generate_reference(cls) -> str:
        """Générer une référence unique"""
        from datetime import datetime
        now = datetime.utcnow()
        # Format: WDR + année + mois + jour + compteur
        base = f"WDR{now.strftime('%Y%m%d')}"
        # Ici on devrait compter les retraits du jour
        # Pour simplifier, on utilise l'heure/minute
        return f"{base}{now.strftime('%H%M')}"

# =========================================
# STATISTIQUES JOURNALIÈRES
# =========================================

class AdminDailyStats(Base):
    """
    Statistiques journalières AlloBara
    Pour le dashboard admin et les rapports
    """
    __tablename__ = "admin_daily_stats"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True, nullable=False)  # Date des stats
    
    # =====================================
    # INSCRIPTIONS
    # =====================================
    new_users = Column(Integer, default=0)               # Nouvelles inscriptions
    new_users_verified = Column(Integer, default=0)      # Inscriptions vérifiées
    trial_started = Column(Integer, default=0)           # Essais commencés
    trial_converted = Column(Integer, default=0)         # Essais convertis
    
    # =====================================
    # ABONNEMENTS
    # =====================================
    new_subscriptions = Column(Integer, default=0)       # Nouveaux abonnements
    subscription_renewals = Column(Integer, default=0)    # Renouvellements
    subscription_cancellations = Column(Integer, default=0) # Annulations
    subscription_expirations = Column(Integer, default=0)  # Expirations
    
    # Répartition par plan
    monthly_subscriptions = Column(Integer, default=0)
    quarterly_subscriptions = Column(Integer, default=0)
    biannual_subscriptions = Column(Integer, default=0)
    annual_subscriptions = Column(Integer, default=0)
    
    # =====================================
    # REVENUS
    # ================================================
    total_revenue = Column(Float, default=0.0)           # Revenus total du jour
    subscription_revenue = Column(Float, default=0.0)    # Revenus abonnements
    
    # Répartition des revenus par plan
    monthly_revenue = Column(Float, default=0.0)
    quarterly_revenue = Column(Float, default=0.0)
    biannual_revenue = Column(Float, default=0.0)
    annual_revenue = Column(Float, default=0.0)
    
    # =====================================
    # ACTIVITÉ UTILISATEURS
    # =====================================
    active_users = Column(Integer, default=0)            # Utilisateurs actifs
    profile_views = Column(Integer, default=0)           # Vues de profils
    searches_performed = Column(Integer, default=0)      # Recherches effectuées
    contacts_made = Column(Integer, default=0)           # Contacts établis
    
    # =====================================
    # CONTENU
    # =====================================
    new_portfolio_items = Column(Integer, default=0)     # Nouveaux éléments portfolio
    new_reviews = Column(Integer, default=0)             # Nouveaux avis
    reviews_approved = Column(Integer, default=0)        # Avis approuvés
    reviews_rejected = Column(Integer, default=0)        # Avis rejetés
    
    # =====================================
    # FINANCE
    # =====================================
    withdrawals_requested = Column(Integer, default=0)   # Demandes de retrait
    withdrawals_completed = Column(Integer, default=0)   # Retraits terminés
    withdrawal_amount = Column(Float, default=0.0)       # Montant retiré
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<DailyStats(date={self.date}, users={self.new_users}, revenue={self.total_revenue})>"
    
    def __str__(self):
        return f"Stats du {self.date.strftime('%d/%m/%Y')}"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def formatted_date(self) -> str:
        """Date formatée"""
        return self.date.strftime("%d/%m/%Y")
    
    @property
    def formatted_revenue(self) -> str:
        """Revenus formatés"""
        return f"{int(self.total_revenue):,} FCFA".replace(",", " ")
    
    @property
    def average_revenue_per_user(self) -> float:
        """Revenus moyens par utilisateur"""
        if self.new_users == 0:
            return 0.0
        return self.total_revenue / self.new_users
    
    @property
    def trial_conversion_rate(self) -> float:
        """Taux de conversion des essais"""
        if self.trial_started == 0:
            return 0.0
        return self.trial_converted / self.trial_started
    
    @property
    def subscription_breakdown(self) -> dict:
        """Répartition des abonnements"""
        return {
            "monthly": self.monthly_subscriptions,
            "quarterly": self.quarterly_subscriptions, 
            "biannual": self.biannual_subscriptions,
            "annual": self.annual_subscriptions
        }
    
    @property
    def revenue_breakdown(self) -> dict:
        """Répartition des revenus"""
        return {
            "monthly": self.monthly_revenue,
            "quarterly": self.quarterly_revenue,
            "biannual": self.biannual_revenue, 
            "annual": self.annual_revenue
        }
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @classmethod
    def get_or_create_today(cls, db_session):
        """Obtenir ou créer les stats d'aujourd'hui"""
        today = date.today()
        stats = db_session.query(cls).filter(cls.date == today).first()
        
        if not stats:
            stats = cls(date=today)
            db_session.add(stats)
            db_session.commit()
        
        return stats
    
    def increment_new_users(self, count: int = 1):
        """Incrémenter les nouvelles inscriptions"""
        self.new_users += count
    
    def increment_revenue(self, amount: float, subscription_type: str = None):
        """Incrémenter les revenus"""
        self.total_revenue += amount
        self.subscription_revenue += amount
        
        # Répartition par type d'abonnement
        if subscription_type:
            if subscription_type == "monthly":
                self.monthly_revenue += amount
                self.monthly_subscriptions += 1
            elif subscription_type == "quarterly":
                self.quarterly_revenue += amount
                self.quarterly_subscriptions += 1
            elif subscription_type == "biannual":
                self.biannual_revenue += amount
                self.biannual_subscriptions += 1
            elif subscription_type == "annual":
                self.annual_revenue += amount
                self.annual_subscriptions += 1
        
        self.new_subscriptions += 1
    
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
