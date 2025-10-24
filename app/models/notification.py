# =====================================================
# app/models/notification.py - Système de notifications
# =====================================================

"""
Modèles de notifications AlloBara
Notifications push, SMS et in-app
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.db.database import Base

# =========================================
# ENUMS NOTIFICATION
# =========================================

class NotificationType(str, enum.Enum):
    """Types de notifications"""
    # Abonnements
    SUBSCRIPTION_EXPIRING = "subscription_expiring"          # Expiration dans 7 jours
    SUBSCRIPTION_EXPIRED = "subscription_expired"            # Abonnement expiré
    SUBSCRIPTION_RENEWED = "subscription_renewed"            # Renouvellement réussi
    PAYMENT_FAILED = "payment_failed"                        # Échec de paiement
    
    # Profile et contenu
    PROFILE_APPROVED = "profile_approved"                    # Profil approuvé
    PROFILE_REJECTED = "profile_rejected"                    # Profil rejeté
    PORTFOLIO_APPROVED = "portfolio_approved"                # Portfolio approuvé
    REVIEW_RECEIVED = "review_received"                      # Nouvel avis reçu
    
    # Parrainage
    REFERRAL_BONUS = "referral_bonus"                        # Bonus de parrainage
    REFERRAL_JOINED = "referral_joined"                      # Filleul inscrit
    
    # Système
    SYSTEM_MAINTENANCE = "system_maintenance"                 # Maintenance programmée
    WELCOME = "welcome"                                      # Message de bienvenue
    PROMOTION = "promotion"                                  # Offres promotionnelles
    
    # Admin
    ADMIN_ALERT = "admin_alert"                              # Alerte admin

class NotificationChannel(str, enum.Enum):
    """Canaux de notification"""
    IN_APP = "in_app"        # Notification dans l'app
    SMS = "sms"              # SMS
    WHATSAPP = "whatsapp"    # WhatsApp
    EMAIL = "email"          # Email (futur)
    PUSH = "push"            # Notification push

class NotificationStatus(str, enum.Enum):
    """Statut des notifications"""
    PENDING = "pending"      # En attente d'envoi
    SENT = "sent"           # Envoyée avec succès
    DELIVERED = "delivered"  # Livrée (confirmation reçue)
    READ = "read"           # Lue par l'utilisateur
    FAILED = "failed"       # Échec d'envoi
    CANCELLED = "cancelled" # Annulée

class NotificationPriority(str, enum.Enum):
    """Priorité des notifications"""
    LOW = "low"             # Basse priorité
    NORMAL = "normal"       # Priorité normale
    HIGH = "high"           # Haute priorité
    URGENT = "urgent"       # Urgent

# =========================================
# MODÈLE NOTIFICATION
# =========================================

class Notification(Base):
    """
    Notifications utilisateurs AlloBara
    Multi-canaux (SMS, WhatsApp, Push, In-App)
    """
    __tablename__ = "notifications"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # =====================================
    # CONTENU DE LA NOTIFICATION
    # =====================================
    type = Column(SQLEnum(NotificationType), nullable=False, index=True)
    title = Column(String(200), nullable=False)              # Titre court
    message = Column(Text, nullable=False)                   # Message principal
    
    # Contenu riche (optionnel)
    subtitle = Column(String(300), nullable=True)            # Sous-titre
    action_text = Column(String(50), nullable=True)          # Texte du bouton d'action
    action_url = Column(String(500), nullable=True)          # URL d'action
    image_url = Column(String(500), nullable=True)           # Image de la notification
    
    # =====================================
    # PARAMÈTRES D'ENVOI
    # =====================================
    channels = Column(JSON, nullable=False)                  # Liste des canaux
    priority = Column(SQLEnum(NotificationPriority), default=NotificationPriority.NORMAL)
    
    # Planification
    scheduled_at = Column(DateTime, nullable=True)           # Envoi programmé
    expires_at = Column(DateTime, nullable=True)             # Date d'expiration
    
    # =====================================
    # STATUT ET SUIVI
    # =====================================
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING, index=True)
    
    # Détails d'envoi par canal
    sms_sent = Column(Boolean, default=False)
    sms_delivered = Column(Boolean, default=False)
    whatsapp_sent = Column(Boolean, default=False)
    whatsapp_delivered = Column(Boolean, default=False)
    push_sent = Column(Boolean, default=False)
    in_app_read = Column(Boolean, default=False)
    
    # =====================================
    # MÉTADONNÉES TECHNIQUES
    # =====================================
    # Réponses des providers
    sms_provider_response = Column(JSON, nullable=True)      # Réponse Twilio SMS
    whatsapp_provider_response = Column(JSON, nullable=True) # Réponse Twilio WhatsApp
    push_provider_response = Column(JSON, nullable=True)     # Réponse service push
    
    # Références externes
    sms_message_id = Column(String(100), nullable=True)      # ID message SMS
    whatsapp_message_id = Column(String(100), nullable=True) # ID message WhatsApp
    push_message_id = Column(String(100), nullable=True)     # ID notification push
    
    # Erreurs
    error_message = Column(String(1000), nullable=True)      # Message d'erreur
    retry_count = Column(Integer, default=0)                 # Nombre de tentatives
    max_retries = Column(Integer, default=3)                 # Max tentatives
    
    # =====================================
    # DONNÉES CONTEXTUELLES
    # =====================================
    context_data = Column(JSON, nullable=True)               # Données contextuelles
    template_id = Column(String(50), nullable=True)          # ID du template utilisé
    
    # Ciblage
    user_segments = Column(JSON, nullable=True)              # Segments utilisateur
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at = Column(DateTime, nullable=True)                # Date d'envoi
    delivered_at = Column(DateTime, nullable=True)           # Date de livraison
    read_at = Column(DateTime, nullable=True)                # Date de lecture
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # =====================================
    # RELATIONS
    # =====================================
    user = relationship("User", back_populates="notifications")
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.type.value}, user_id={self.user_id})>"
    
    def __str__(self):
        return f"{self.type.value} - {self.title}"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def is_pending(self) -> bool:
        """Vérifier si en attente"""
        return self.status == NotificationStatus.PENDING
    
    @property
    def is_sent(self) -> bool:
        """Vérifier si envoyée"""
        return self.status in [NotificationStatus.SENT, NotificationStatus.DELIVERED, NotificationStatus.READ]
    
    @property
    def is_read(self) -> bool:
        """Vérifier si lue"""
        return self.status == NotificationStatus.READ or self.in_app_read
    
    @property
    def is_expired(self) -> bool:
        """Vérifier si expirée"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @property
    def should_send_now(self) -> bool:
        """Vérifier si doit être envoyée maintenant"""
        if self.status != NotificationStatus.PENDING:
            return False
        if self.is_expired:
            return False
        if self.scheduled_at and datetime.utcnow() < self.scheduled_at:
            return False
        return True
    
    @property
    def can_retry(self) -> bool:
        """Vérifier si peut être retentée"""
        return (
            self.status == NotificationStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    @property
    def delivery_rate(self) -> float:
        """Taux de livraison (canaux livrés / canaux envoyés)"""
        sent_channels = sum([
            self.sms_sent,
            self.whatsapp_sent, 
            self.push_sent,
            True  # in_app toujours "envoyé"
        ])
        
        if sent_channels == 0:
            return 0.0
        
        delivered_channels = sum([
            self.sms_delivered,
            self.whatsapp_delivered,
            True,  # push considéré comme livré si envoyé
            True   # in_app toujours "livré"
        ])
        
        return delivered_channels / sent_channels
    
    @property
    def priority_color(self) -> str:
        """Couleur selon la priorité"""
        colors = {
            NotificationPriority.LOW: "gray",
            NotificationPriority.NORMAL: "blue",
            NotificationPriority.HIGH: "orange",
            NotificationPriority.URGENT: "red"
        }
        return colors.get(self.priority, "blue")
    
    @property
    def formatted_created_at(self) -> str:
        """Date de création formatée"""
        return self.created_at.strftime("%d/%m/%Y %H:%M")
    
    @property
    def time_since_created(self) -> str:
        """Temps écoulé depuis la création"""
        delta = datetime.utcnow() - self.created_at
        
        if delta.days > 0:
            return f"Il y a {delta.days} jour(s)"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"Il y a {hours}h"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"Il y a {minutes}min"
        else:
            return "À l'instant"
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    def mark_as_sent(self, channel: NotificationChannel, message_id: str = None):
        """Marquer comme envoyée pour un canal"""
        if channel == NotificationChannel.SMS:
            self.sms_sent = True
            if message_id:
                self.sms_message_id = message_id
        elif channel == NotificationChannel.WHATSAPP:
            self.whatsapp_sent = True
            if message_id:
                self.whatsapp_message_id = message_id
        elif channel == NotificationChannel.PUSH:
            self.push_sent = True
            if message_id:
                self.push_message_id = message_id
        
        # Mettre à jour le statut global
        if not self.sent_at:
            self.sent_at = datetime.utcnow()
            self.status = NotificationStatus.SENT
    
    def mark_as_delivered(self, channel: NotificationChannel):
        """Marquer comme livrée pour un canal"""
        if channel == NotificationChannel.SMS:
            self.sms_delivered = True
        elif channel == NotificationChannel.WHATSAPP:
            self.whatsapp_delivered = True
        
        self.delivered_at = datetime.utcnow()
        self.status = NotificationStatus.DELIVERED
    
    def mark_as_read(self):
        """Marquer comme lue"""
        self.in_app_read = True
        self.read_at = datetime.utcnow()
        self.status = NotificationStatus.READ
    
    def mark_as_failed(self, error_message: str):
        """Marquer comme échouée"""
        self.status = NotificationStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
    
    def cancel(self):
        """Annuler la notification"""
        self.status = NotificationStatus.CANCELLED
    
    def schedule(self, scheduled_at: datetime):
        """Programmer l'envoi"""
        self.scheduled_at = scheduled_at
    
    def add_context_data(self, **data):
        """Ajouter des données contextuelles"""
        if self.context_data is None:
            self.context_data = {}
        self.context_data.update(data)
    
    @classmethod
    def create_subscription_expiring(cls, user_id: int, days_remaining: int):
        """Créer notification d'expiration d'abonnement"""
        return cls(
            user_id=user_id,
            type=NotificationType.SUBSCRIPTION_EXPIRING,
            title="⚠️ Abonnement bientôt expiré",
            message=f"Votre abonnement AlloBara expire dans {days_remaining} jour(s). Renouvelez maintenant pour rester visible !",
            channels=["sms", "whatsapp", "in_app"],
            priority=NotificationPriority.HIGH,
            action_text="Renouveler",
            action_url="/subscription/renew"
        )
    
    @classmethod
    def create_welcome(cls, user_id: int, user_name: str):
        """Créer notification de bienvenue"""
        return cls(
            user_id=user_id,
            type=NotificationType.WELCOME,
            title=f"🎉 Bienvenue sur AlloBara, {user_name} !",
            message="Félicitations ! Votre compte est créé. Complétez votre profil pour attirer plus de clients.",
            channels=["whatsapp", "in_app"],
            priority=NotificationPriority.NORMAL,
            action_text="Compléter mon profil",
            action_url="/profile/complete"
        )
    
    @classmethod
    def create_review_received(cls, user_id: int, rating: int, client_name: str):
        """Créer notification de nouvel avis"""
        stars = "⭐" * rating
        return cls(
            user_id=user_id,
            type=NotificationType.REVIEW_RECEIVED,
            title="📝 Nouvel avis reçu !",
            message=f"{client_name} vous a laissé un avis : {stars} ({rating}/5)",
            channels=["sms", "in_app"],
            priority=NotificationPriority.NORMAL,
            action_text="Voir l'avis",
            action_url="/reviews"
        )
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convertir en dictionnaire pour l'API"""
        data = {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "subtitle": self.subtitle,
            "action_text": self.action_text,
            "action_url": self.action_url,
            "image_url": self.image_url,
            "priority": self.priority.value,
            "priority_color": self.priority_color,
            "status": self.status.value,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "formatted_created_at": self.formatted_created_at,
            "time_since_created": self.time_since_created
        }
        
        if include_sensitive:
            data.update({
                "channels": self.channels,
                "retry_count": self.retry_count,
                "error_message": self.error_message,
                "context_data": self.context_data
            })
        
        return data