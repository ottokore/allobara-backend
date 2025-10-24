"""
Modèle utilisateur AlloBara
Prestataires de services avec authentification, profil, géolocalisation
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
import enum

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class UserRole(str, enum.Enum):
    """Rôles des utilisateurs dans AlloBara"""
    PROVIDER = "provider"        # Prestataire de service (défaut)
    ADMIN = "admin"             # Administrateur
    SUPER_ADMIN = "super_admin" # Super administrateur

class Gender(str, enum.Enum):
    """Genre de l'utilisateur"""
    MALE = "M"
    FEMALE = "F" 
    OTHER = "other"

class DocumentType(str, enum.Enum):
    """Types de documents d'identité"""
    CNI = "cni"                # Carte Nationale d'Identité
    PASSPORT = "passport"       # Passeport
    DRIVING_LICENSE = "permis"  # Permis de conduire

class SubscriptionStatus(str, enum.Enum):
    """Statuts d'abonnement"""
    TRIAL = "trial"            # Période d'essai gratuite
    ACTIVE = "active"          # Abonnement payé et actif
    EXPIRED = "expired"        # Abonnement expiré
    SUSPENDED = "suspended"    # Suspendu (impayé)
    CANCELLED = "cancelled"    # Annulé par l'utilisateur

# =========================================
# MODÈLE UTILISATEUR PRINCIPAL
# =========================================

class User(Base):
    """
    Modèle des utilisateurs AlloBara
    Principalement des prestataires de services informels
    """
    __tablename__ = "users"
    
    # =====================================
    # IDENTIFIANTS ET SÉCURITÉ
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)  # +225XXXXXXXX
    pin_hash = Column(String(255), nullable=False)  # Code PIN haché (4 chiffres)
    role = Column(SQLEnum(UserRole), default=UserRole.PROVIDER, nullable=False)
    
    # =====================================
    # INFORMATIONS PERSONNELLES
    # =====================================
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    birth_date = Column(DateTime, nullable=True)
    gender = Column(SQLEnum(Gender), nullable=True)
    
    # Photos
    profile_picture = Column(String(255), nullable=True)  # URL/chemin image profil
    cover_picture = Column(String(255), nullable=True)    # Photo de couverture
    
    # =====================================
    # INFORMATIONS PROFESSIONNELLES
    # =====================================
    profession = Column(String(100), nullable=True)  # Ex: "Plombier", "Électricien"
    domain = Column(String(50), nullable=True)       # Ex: "batiment", "menage", "transport"
    years_experience = Column(Integer, default=0)    # Années d'expérience
    description = Column(Text, nullable=True)        # Biographie/présentation
    
    # =====================================
    # TARIFICATION
    # =====================================
    daily_rate = Column(Float, nullable=True)        # Tarif journalier (bâtiment)
    monthly_rate = Column(Float, nullable=True)      # Tarif mensuel (autres secteurs)
    
    # =====================================
    # GÉOLOCALISATION
    # =====================================
    country = Column(String(50), default="Côte d'Ivoire")
    city = Column(String(100), nullable=True)        # Ex: "Abidjan", "Bouaké"
    commune = Column(String(100), nullable=True)     # Ex: "Yopougon", "Cocody"
    latitude = Column(Float, nullable=True)          # Coordonnées GPS
    longitude = Column(Float, nullable=True)         # Coordonnées GPS
    work_radius_km = Column(Integer, default=5)     # Rayon de travail en km
    address = Column(Text, nullable=True)            # Adresse complète
    
    # =====================================
    # DOCUMENTS D'IDENTITÉ
    # =====================================
    id_document_type = Column(SQLEnum(DocumentType), nullable=True)
    id_document_front = Column(String(255), nullable=True)  # Recto du document
    id_document_back = Column(String(255), nullable=True)   # Verso du document
    id_document_number = Column(String(50), nullable=True)  # Numéro du document
    
    # =====================================
    # STATUT ET VÉRIFICATIONS
    # =====================================
    is_active = Column(Boolean, default=True)         # Compte actif
    is_verified = Column(Boolean, default=False)      # Profil vérifié par admin
    is_blocked = Column(Boolean, default=False)       # Compte bloqué
    is_featured = Column(Boolean, default=False)      # Mis en avant (sponsoring)
    verification_date = Column(DateTime, nullable=True)
    blocked_reason = Column(Text, nullable=True)      # Raison du blocage
    
    # =====================================
    # ABONNEMENT ET PÉRIODE D'ESSAI
    # =====================================
    subscription_status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.TRIAL, nullable=False)
    trial_expires_at = Column(DateTime, nullable=True)  # Date d'expiration de la période d'essai
    subscription_expires_at = Column(DateTime, nullable=True)  # Date d'expiration de l'abonnement payé
    
    # =====================================
    # PARRAINAGE
    # =====================================
    referral_code = Column(String(10), unique=True, index=True, nullable=True)  # ALL12345
    referred_by = Column(String(10), nullable=True)   # Code du parrain
    referral_count = Column(Integer, default=0)       # Nombre de filleuls
    
    # =====================================
    # STATISTIQUES
    # =====================================
    profile_views = Column(Integer, default=0)        # Vues du profil
    total_contacts = Column(Integer, default=0)       # Contacts reçus
    total_earnings = Column(Float, default=0.0)       # Gains totaux (futur)
    rating_average = Column(Float, default=0.0)       # Note moyenne
    rating_count = Column(Integer, default=0)         # Nombre d'avis
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    
    # =====================================
    # RELATIONS AVEC AUTRES MODÈLES
    # =====================================
    # Abonnement (relation 1:1)
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Portfolio (relation 1:N)
    portfolio_items = relationship("PortfolioItem", back_populates="user", cascade="all, delete-orphan")
    
    # Avis reçus (relation 1:N)
    received_reviews = relationship("Review", back_populates="provider", foreign_keys="Review.provider_id", cascade="all, delete-orphan")
    
    # Notifications (relation 1:N)
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    #Voir les statistiques journalieres
    daily_stats = relationship(
        "DailyStats", 
        back_populates="user", 
        cascade="all, delete-orphan",
        lazy="select"  # ✅ Charge les stats seulement si demandées explicitement
    )

    # Relation avec les avis (si pas déjà présente)
    received_reviews = relationship(
        "Review", 
        back_populates="provider",
        cascade="all, delete-orphan"
    )
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone}, name='{self.full_name}')>"
    
    def __str__(self):
        return f"{self.full_name} ({self.phone})"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def full_name(self) -> str:
        """Nom complet de l'utilisateur"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return "Utilisateur"
    
    @property
    def display_name(self) -> str:
        """Nom d'affichage pour l'interface"""
        name = self.full_name
        if name == "Utilisateur":
            return f"Prestataire {self.phone[-4:]}"  # Derniers 4 chiffres
        return name
    
    @property
    def is_admin(self) -> bool:
        """Vérifier si l'utilisateur est admin"""
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    
    @property
    def is_super_admin(self) -> bool:
        """Vérifier si l'utilisateur est super admin"""
        return self.role == UserRole.SUPER_ADMIN
    
    @property
    def has_active_subscription(self) -> bool:
        """Vérifier si l'utilisateur a un abonnement actif (incluant période d'essai)"""
        now = datetime.utcnow()
        
        # Vérifier la période d'essai
        if self.subscription_status == SubscriptionStatus.TRIAL:
            if self.trial_expires_at and self.trial_expires_at > now:
                return True
            return False
        
        # Vérifier l'abonnement payé
        elif self.subscription_status == SubscriptionStatus.ACTIVE:
            if self.subscription_expires_at and self.subscription_expires_at > now:
                return True
            return False
        
        return False
    
    @property
    def subscription_days_left(self) -> int:
        """Nombre de jours restants sur l'abonnement ou période d'essai"""
        now = datetime.utcnow()
        
        if self.subscription_status == SubscriptionStatus.TRIAL and self.trial_expires_at:
            delta = self.trial_expires_at - now
            return max(0, delta.days)
        
        elif self.subscription_status == SubscriptionStatus.ACTIVE and self.subscription_expires_at:
            delta = self.subscription_expires_at - now
            return max(0, delta.days)
        
        return 0
    
    @property
    def is_profile_complete(self) -> bool:
        """Vérifier si le profil est complet"""
        required_fields = [
            self.first_name,
            self.last_name,
            self.profession,
            self.domain,
            self.city,
            self.description
        ]
        return all(field for field in required_fields)
    
    @property
    def profile_completion_percentage(self) -> int:
        """Pourcentage de complétion du profil"""
        fields_to_check = [
            self.first_name,
            self.last_name,
            self.profession,
            self.domain,
            self.city,
            self.commune,
            self.description,
            self.profile_picture,
            self.daily_rate or self.monthly_rate,
            self.id_document_front,
            self.latitude and self.longitude
        ]
        
        completed_fields = sum(1 for field in fields_to_check if field)
        return int((completed_fields / len(fields_to_check)) * 100)
    
    @property
    def coordinates(self) -> tuple:
        """Coordonnées GPS sous forme de tuple"""
        if self.latitude and self.longitude:
            return (self.latitude, self.longitude)
        return None
    
    @property
    def formatted_phone(self) -> str:
        """Numéro de téléphone formaté"""
        if len(self.phone) == 13 and self.phone.startswith('+225'):
            # Format : +225 XX XX XX XX XX
            phone = self.phone[4:]  # Enlever +225
            return f"+225 {phone[:2]} {phone[2:4]} {phone[4:6]} {phone[6:8]} {phone[8:]}"
        return self.phone
    
    @property
    def age(self) -> int:
        """Âge calculé à partir de la date de naissance"""
        if not self.birth_date:
            return None
        
        today = datetime.now()
        age = today.year - self.birth_date.year
        
        # Ajuster si l'anniversaire n'est pas encore passé cette année
        if today.month < self.birth_date.month or \
           (today.month == self.birth_date.month and today.day < self.birth_date.day):
            age -= 1
            
        return age
    
    @property
    def rating_display(self) -> str:
        """Affichage de la note avec étoiles"""
        if self.rating_count == 0:
            return "Pas encore d'avis"
        
        stars = "⭐" * int(round(self.rating_average))
        return f"{stars} {self.rating_average:.1f} ({self.rating_count} avis)"
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    def update_rating(self, new_rating: float):
        """Mettre à jour la note moyenne"""
        if self.rating_count == 0:
            self.rating_average = new_rating
            self.rating_count = 1
        else:
            total = self.rating_average * self.rating_count
            self.rating_count += 1
            self.rating_average = (total + new_rating) / self.rating_count
    
    def increment_profile_views(self):
        """Incrémenter le nombre de vues du profil"""
        self.profile_views = (self.profile_views or 0) + 1
    
    def increment_contacts(self):
        """Incrémenter le nombre de contacts reçus"""
        self.total_contacts = (self.total_contacts or 0) + 1
    
    def extend_trial(self, days: int):
        """Étendre la période d'essai de X jours"""
        if self.subscription_status == SubscriptionStatus.TRIAL:
            if self.trial_expires_at:
                self.trial_expires_at += timedelta(days=days)
            else:
                self.trial_expires_at = datetime.utcnow() + timedelta(days=days)
    
    def activate_subscription(self, duration_months: int):
        """Activer un abonnement payé"""
        now = datetime.utcnow()
        self.subscription_status = SubscriptionStatus.ACTIVE
        
        # Si l'abonnement existe déjà, l'étendre
        if self.subscription_expires_at and self.subscription_expires_at > now:
            self.subscription_expires_at += timedelta(days=duration_months * 30)
        else:
            self.subscription_expires_at = now + timedelta(days=duration_months * 30)
        
        # Mettre fin à la période d'essai
        self.trial_expires_at = None
    
    def expire_subscription(self):
        """Faire expirer l'abonnement"""
        self.subscription_status = SubscriptionStatus.EXPIRED
    
    def can_work_in_location(self, latitude: float, longitude: float) -> bool:
        """Vérifier si l'utilisateur peut travailler à une localisation donnée"""
        if not self.coordinates:
            return True  # Si pas de coordonnées, on assume qu'il peut travailler partout
        
        from math import radians, cos, sin, asin, sqrt
        
        def haversine(lon1, lat1, lon2, lat2):
            """Calculer la distance entre deux points GPS en km"""
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            return c * 6371  # Rayon de la Terre en km
        
        distance = haversine(self.longitude, self.latitude, longitude, latitude)
        return distance <= self.work_radius_km


# =========================================
# MODÈLE STOCKAGE OTP TEMPORAIRE
# =========================================

class OTPStorage(Base):
    """
    Modèle pour stocker temporairement les codes OTP
    Utilisé pour la vérification des numéros de téléphone
    """
    __tablename__ = "otp_storage"
    
    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    otp_code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def is_expired(self) -> bool:
        """Vérifier si l'OTP a expiré"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self, code: str) -> bool:
        """Vérifier si le code OTP est valide"""
        return (
            not self.is_used and 
            not self.is_expired() and 
            self.otp_code == code and
            self.attempts < 3
        )
    
    def __repr__(self):
        return f"<OTPStorage(phone={self.phone_number}, expires_at={self.expires_at})>"