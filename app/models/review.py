"""
Modèle des avis et évaluations AlloBara
Système de notation et commentaires des prestataires
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class ReviewStatus(str, enum.Enum):
    """Statut des avis"""
    PENDING = "pending"       # En attente de modération
    APPROVED = "approved"     # Approuvé et visible
    REJECTED = "rejected"     # Rejeté par la modération
    HIDDEN = "hidden"         # Masqué par l'admin
    SPAM = "spam"            # Marqué comme spam

class ReviewSource(str, enum.Enum):
    """Source de l'avis"""
    APP = "app"              # Via l'application mobile
    WEB = "web"              # Via le site web
    SMS = "sms"              # Via SMS (futur)
    IMPORTED = "imported"     # Importé depuis autre plateforme

# =========================================
# MODÈLE AVIS
# =========================================

class Review(Base):
    """
    Avis et évaluations des prestataires par les clients
    """
    __tablename__ = "reviews"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # =====================================
    # INFORMATIONS CLIENT (ANONYMES)
    # =====================================
    # Pas de FK vers users car les clients n'ont pas de compte
    client_name = Column(String(100), nullable=True)     # Nom du client (optionnel)
    client_phone = Column(String(20), nullable=True)     # Téléphone (pour validation)
    client_location = Column(String(100), nullable=True) # Ville du client
    is_anonymous = Column(Boolean, default=False)        # Avis anonyme
    
    # =====================================
    # ÉVALUATION
    # =====================================
    rating = Column(Integer, nullable=False)             # Note de 1 à 5 étoiles
    
    # Critères détaillés (optionnels)
    quality_rating = Column(Integer, nullable=True)      # Qualité du travail (1-5)
    punctuality_rating = Column(Integer, nullable=True)  # Ponctualité (1-5)
    communication_rating = Column(Integer, nullable=True) # Communication (1-5)
    value_rating = Column(Integer, nullable=True)        # Rapport qualité-prix (1-5)
    
    # =====================================
    # COMMENTAIRE
    # =====================================
    title = Column(String(200), nullable=True)           # Titre de l'avis
    comment = Column(Text, nullable=True)                # Commentaire détaillé
    
    # Détails du service
    service_type = Column(String(100), nullable=True)    # Type de service reçu
    service_date = Column(DateTime, nullable=True)       # Date de la prestation
    service_duration = Column(String(50), nullable=True) # Durée du service
    service_cost = Column(Float, nullable=True)          # Coût du service (optionnel)
    
    # =====================================
    # STATUT ET MODÉRATION
    # =====================================
    status = Column(SQLEnum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False)
    
    # Modération
    moderated_at = Column(DateTime, nullable=True)       # Date de modération
    moderated_by = Column(Integer, nullable=True)        # Admin qui a modéré
    moderation_notes = Column(Text, nullable=True)       # Notes de modération
    
    # Signalements
    is_reported = Column(Boolean, default=False)         # Avis signalé
    report_count = Column(Integer, default=0)            # Nombre de signalements
    report_reasons = Column(Text, nullable=True)         # Raisons des signalements
    
    # =====================================
    # MÉTADONNÉES
    # =====================================
    source = Column(SQLEnum(ReviewSource), default=ReviewSource.APP)
    ip_address = Column(String(45), nullable=True)       # IP du client
    user_agent = Column(String(500), nullable=True)      # User agent
    
    # Vérification
    is_verified = Column(Boolean, default=False)         # Avis vérifié (vrai client)
    verification_method = Column(String(50), nullable=True) # Méthode de vérification
    phone_verified = Column(Boolean, default=False)      # Téléphone vérifié
    
    # =====================================
    # ENGAGEMENT ET INTERACTIONS
    # =====================================
    helpful_count = Column(Integer, default=0)           # Nombre de "utile"
    not_helpful_count = Column(Integer, default=0)       # Nombre de "pas utile"
    
    # Réponse du prestataire
    provider_response = Column(Text, nullable=True)      # Réponse du prestataire
    provider_response_date = Column(DateTime, nullable=True)
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # =====================================
    # RELATIONS
    # =====================================
    provider = relationship("User", back_populates="received_reviews")
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<Review(id={self.id}, provider_id={self.provider_id}, rating={self.rating})>"
    
    def __str__(self):
        client = self.display_client_name
        return f"Avis de {client} - {self.rating}⭐"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def is_approved(self) -> bool:
        """Vérifier si l'avis est approuvé"""
        return self.status == ReviewStatus.APPROVED
    
    @property
    def is_pending(self) -> bool:
        """Vérifier si l'avis est en attente"""
        return self.status == ReviewStatus.PENDING
    
    @property
    def is_visible(self) -> bool:
        """Vérifier si l'avis est visible publiquement"""
        return self.status == ReviewStatus.APPROVED
    
    @property
    def display_client_name(self) -> str:
        """Nom d'affichage du client"""
        if self.is_anonymous:
            return "Client anonyme"
        elif self.client_name:
            # Masquer partiellement le nom pour la confidentialité
            if len(self.client_name) > 3:
                return f"{self.client_name[0]}{'*' * (len(self.client_name) - 2)}{self.client_name[-1]}"
            return self.client_name
        else:
            return "Client"
    
    @property
    def rating_stars(self) -> str:
        """Affichage étoiles de la note"""
        full_stars = "⭐" * self.rating
        empty_stars = "☆" * (5 - self.rating)
        return f"{full_stars}{empty_stars}"
    
    @property
    def rating_text(self) -> str:
        """Texte descriptif de la note"""
        ratings = {
            1: "Très insatisfait",
            2: "Insatisfait", 
            3: "Satisfait",
            4: "Très satisfait",
            5: "Excellent"
        }
        return ratings.get(self.rating, "Non évalué")
    
    @property
    def average_detailed_rating(self) -> float:
        """Moyenne des notes détaillées"""
        ratings = [
            self.quality_rating,
            self.punctuality_rating, 
            self.communication_rating,
            self.value_rating
        ]
        valid_ratings = [r for r in ratings if r is not None]
        
        if not valid_ratings:
            return self.rating
        
        return sum(valid_ratings) / len(valid_ratings)
    
    @property
    def has_detailed_ratings(self) -> bool:
        """Vérifier si a des notes détaillées"""
        return any([
            self.quality_rating,
            self.punctuality_rating,
            self.communication_rating, 
            self.value_rating
        ])
    
    @property
    def helpful_ratio(self) -> float:
        """Ratio d'utilité (helpful / total)"""
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0.0
        return self.helpful_count / total
    
    @property
    def age_days(self) -> int:
        """Âge de l'avis en jours"""
        return (datetime.utcnow() - self.created_at).days
    
    @property
    def is_recent(self) -> bool:
        """Vérifier si l'avis est récent (moins de 30 jours)"""
        return self.age_days <= 30
    
    @property
    def service_date_formatted(self) -> str:
        """Date de service formatée"""
        if not self.service_date:
            return None
        return self.service_date.strftime("%d/%m/%Y")
    
    @property
    def status_display(self) -> str:
        """Nom d'affichage du statut"""
        status_names = {
            ReviewStatus.PENDING: "En attente",
            ReviewStatus.APPROVED: "Approuvé",
            ReviewStatus.REJECTED: "Rejeté",
            ReviewStatus.HIDDEN: "Masqué",
            ReviewStatus.SPAM: "Spam"
        }
        return status_names.get(self.status, self.status.value)
    
    @property
    def verification_badges(self) -> list:
        """Badges de vérification"""
        badges = []
        if self.is_verified:
            badges.append("✅ Vérifié")
        if self.phone_verified:
            badges.append("📱 Téléphone vérifié")
        return badges
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    def approve(self, admin_id: int, notes: str = None):
        """Approuver l'avis"""
        self.status = ReviewStatus.APPROVED
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_id
        if notes:
            self.moderation_notes = notes
    
    def reject(self, admin_id: int, reason: str):
        """Rejeter l'avis"""
        self.status = ReviewStatus.REJECTED
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_id
        self.moderation_notes = reason
    
    def hide(self, admin_id: int, reason: str = None):
        """Masquer l'avis"""
        self.status = ReviewStatus.HIDDEN
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_id
        if reason:
            self.moderation_notes = reason
    
    def mark_as_spam(self, admin_id: int):
        """Marquer comme spam"""
        self.status = ReviewStatus.SPAM
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_id
    
    def add_provider_response(self, response: str):
        """Ajouter une réponse du prestataire"""
        self.provider_response = response
        self.provider_response_date = datetime.utcnow()
    
    def mark_helpful(self):
        """Marquer comme utile"""
        self.helpful_count = (self.helpful_count or 0) + 1
    
    def mark_not_helpful(self):
        """Marquer comme pas utile"""
        self.not_helpful_count = (self.not_helpful_count or 0) + 1
    
    def report(self, reason: str):
        """Signaler l'avis"""
        self.is_reported = True
        self.report_count = (self.report_count or 0) + 1
        
        if self.report_reasons:
            self.report_reasons += f"; {reason}"
        else:
            self.report_reasons = reason
    
    def verify_phone(self):
        """Marquer le téléphone comme vérifié"""
        self.phone_verified = True
        if not self.is_verified:
            self.is_verified = True
            self.verification_method = "phone"
    
    @classmethod
    def calculate_provider_stats(cls, provider_id: int) -> dict:
        """Calculer les statistiques d'un prestataire"""
        # Cette méthode serait implémentée dans le service
        # pour éviter les dépendances circulaires
        pass
    
    @classmethod
    def is_valid_rating(cls, rating: int) -> bool:
        """Vérifier si la note est valide"""
        return 1 <= rating <= 5
    
    def get_detailed_ratings_dict(self) -> dict:
        """Obtenir les notes détaillées sous forme de dictionnaire"""
        return {
            "quality": self.quality_rating,
            "punctuality": self.punctuality_rating,
            "communication": self.communication_rating,
            "value": self.value_rating
        }
    
    def update_detailed_ratings(self, ratings: dict):
        """Mettre à jour les notes détaillées"""
        if "quality" in ratings:
            self.quality_rating = ratings["quality"]
        if "punctuality" in ratings:
            self.punctuality_rating = ratings["punctuality"]
        if "communication" in ratings:
            self.communication_rating = ratings["communication"]
        if "value" in ratings:
            self.value_rating = ratings["value"]
    
    def can_be_edited(self) -> bool:
        """Vérifier si l'avis peut être modifié"""
        # Les avis peuvent être modifiés dans les 24h après création
        return self.age_days <= 1 and self.status == ReviewStatus.PENDING
    
    # Auto-approuver les avis simples
    def should_auto_approve(self) -> bool:
        """Vérifier si doit être auto-approuvé"""
        # Pour l'instant, auto-approuver tous les avis pour simplifier
        # Plus tard, vous pourrez ajouter des règles de modération
        return True
        
        # Ancien code commenté pour référence future:
        # if not self.phone_verified:
        #     return False
        # 
        # if self.comment:
        #     suspect_words = ["spam", "fake", "bot", "arnaque"]
        #     comment_lower = self.comment.lower()
        #     if any(word in comment_lower for word in suspect_words):
        #         return False
        # 
        # return True
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convertir en dictionnaire pour l'API"""
        data = {
            "id": self.id,
            "rating": self.rating,
            "rating_stars": self.rating_stars,
            "rating_text": self.rating_text,
            "title": self.title,
            "comment": self.comment,
            "client_name": self.display_client_name,
            "client_location": self.client_location,
            "service_type": self.service_type,
            "service_date": self.service_date_formatted,
            "is_verified": self.is_verified,
            "verification_badges": self.verification_badges,
            "helpful_count": self.helpful_count,
            "provider_response": self.provider_response,
            "provider_response_date": self.provider_response_date.isoformat() if self.provider_response_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "age_days": self.age_days,
            "is_recent": self.is_recent
        }
        
        # Données détaillées
        if self.has_detailed_ratings:
            data["detailed_ratings"] = self.get_detailed_ratings_dict()
            data["average_detailed_rating"] = self.average_detailed_rating
        
        # Données sensibles (admin uniquement)
        if include_sensitive:
            data.update({
                "client_phone": self.client_phone,
                "status": self.status.value,
                "status_display": self.status_display,
                "ip_address": self.ip_address,
                "is_reported": self.is_reported,
                "report_count": self.report_count,
                "moderation_notes": self.moderation_notes
            })
        
        return data