"""
Modèle du portfolio AlloBara
Gestion des images et vidéos des réalisations des prestataires
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import os

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class PortfolioType(str, enum.Enum):
    """Types d'éléments du portfolio"""
    IMAGE = "image"       # Images JPG, PNG, GIF
    VIDEO = "video"       # Vidéos MP4

class PortfolioStatus(str, enum.Enum):
    """Statut des éléments du portfolio"""
    ACTIVE = "active"         # Visible publiquement
    PENDING = "pending"       # En attente de modération
    REJECTED = "rejected"     # Rejeté par la modération
    ARCHIVED = "archived"     # Archivé par l'utilisateur

class CompressionStatus(str, enum.Enum):
    """Statut de compression des fichiers"""
    ORIGINAL = "original"     # Fichier original non compressé
    COMPRESSING = "compressing"  # En cours de compression
    COMPRESSED = "compressed" # Compression terminée
    FAILED = "failed"        # Échec de compression

# =========================================
# MODÈLE PORTFOLIO
# =========================================

class PortfolioItem(Base):
    """
    Éléments du portfolio d'un prestataire
    Images et vidéos de ses réalisations
    """
    __tablename__ = "portfolio_items"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # =====================================
    # CONTENU
    # =====================================
    title = Column(String(200), nullable=True)          # Titre de la réalisation
    description = Column(Text, nullable=True)           # Description du travail
    
    # Fichier principal
    file_path = Column(String(500), nullable=False)     # Chemin vers le fichier
    file_name = Column(String(255), nullable=False)     # Nom original du fichier
    file_type = Column(SQLEnum(PortfolioType), nullable=False)
    file_extension = Column(String(10), nullable=False) # jpg, png, mp4, etc.
    file_size = Column(Integer, nullable=True)          # Taille en bytes
    
    # Métadonnées du fichier
    mime_type = Column(String(100), nullable=True)      # image/jpeg, video/mp4
    width = Column(Integer, nullable=True)              # Largeur (images/vidéos)
    height = Column(Integer, nullable=True)             # Hauteur (images/vidéos)
    duration = Column(Float, nullable=True)             # Durée en secondes (vidéos)
    
    # =====================================
    # COMPRESSION ET OPTIMISATION
    # =====================================
    compression_status = Column(SQLEnum(CompressionStatus), default=CompressionStatus.ORIGINAL)
    
    # Fichier compressé
    compressed_path = Column(String(500), nullable=True)     # Chemin fichier compressé
    compressed_size = Column(Integer, nullable=True)         # Taille fichier compressé
    compression_ratio = Column(Float, nullable=True)         # Ratio de compression
    
    # Vignette (thumbnail)
    thumbnail_path = Column(String(500), nullable=True)      # Chemin vignette
    thumbnail_width = Column(Integer, default=300)           # Largeur vignette
    thumbnail_height = Column(Integer, default=200)          # Hauteur vignette
    
    # =====================================
    # STATUT ET MODÉRATION
    # =====================================
    status = Column(SQLEnum(PortfolioStatus), default=PortfolioStatus.ACTIVE, nullable=False)
    is_featured = Column(Boolean, default=False)             # Mis en avant
    order_index = Column(Integer, default=0)                 # Ordre d'affichage
    
    # Modération
    moderation_notes = Column(Text, nullable=True)           # Notes de modération
    moderated_at = Column(DateTime, nullable=True)           # Date de modération
    moderated_by = Column(Integer, nullable=True)            # ID admin qui a modéré
    
    # =====================================
    # STATISTIQUES ET ENGAGEMENT
    # =====================================
    views_count = Column(Integer, default=0)                 # Nombre de vues
    likes_count = Column(Integer, default=0)                 # Nombre de likes (futur)
    shares_count = Column(Integer, default=0)                # Nombre de partages (futur)
    
    # =====================================
    # MÉTADONNÉES TECHNIQUES
    # =====================================
    # Informations EXIF (images)
    camera_make = Column(String(50), nullable=True)          # Marque appareil photo
    camera_model = Column(String(100), nullable=True)        # Modèle appareil photo
    taken_at = Column(DateTime, nullable=True)               # Date prise de vue
    gps_latitude = Column(Float, nullable=True)              # Coordonnées GPS de la photo
    gps_longitude = Column(Float, nullable=True)
    
    # Hash pour détecter les doublons
    file_hash = Column(String(64), nullable=True, index=True) # SHA256 du fichier
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    archived_at = Column(DateTime, nullable=True)            # Date d'archivage
    
    # =====================================
    # RELATIONS
    # =====================================
    user = relationship("User", back_populates="portfolio_items")
    
    # =====================================
    # REPRÉSENTATION STRING
    # =====================================
    def __repr__(self):
        return f"<PortfolioItem(id={self.id}, user_id={self.user_id}, type={self.file_type.value})>"
    
    def __str__(self):
        title = self.title or f"Réalisation {self.id}"
        return f"{title} ({self.file_type.value})"
    
    # =====================================
    # PROPRIÉTÉS CALCULÉES
    # =====================================
    
    @property
    def is_image(self) -> bool:
        """Vérifier si c'est une image"""
        return self.file_type == PortfolioType.IMAGE
    
    @property
    def is_video(self) -> bool:
        """Vérifier si c'est une vidéo"""
        return self.file_type == PortfolioType.VIDEO
    
    @property
    def is_active(self) -> bool:
        """Vérifier si l'élément est actif"""
        return self.status == PortfolioStatus.ACTIVE
    
    @property
    def is_pending_moderation(self) -> bool:
        """Vérifier si en attente de modération"""
        return self.status == PortfolioStatus.PENDING
    
    @property
    def file_url(self) -> str:
        """URL publique du fichier"""
        if self.compressed_path and self.compression_status == CompressionStatus.COMPRESSED:
            return f"/uploads/portfolio/{os.path.basename(self.compressed_path)}"
        return f"/uploads/portfolio/{os.path.basename(self.file_path)}"
    
    @property
    def thumbnail_url(self) -> str:
        """URL de la vignette"""
        if self.thumbnail_path:
            return f"/uploads/portfolio/thumbnails/{os.path.basename(self.thumbnail_path)}"
        return self.file_url  # Fallback sur le fichier original
    
    @property
    def formatted_file_size(self) -> str:
        """Taille du fichier formatée"""
        if not self.file_size:
            return "Inconnue"
        
        # Convertir en unités lisibles
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"
    
    @property
    def formatted_duration(self) -> str:
        """Durée formatée pour les vidéos"""
        if not self.duration or not self.is_video:
            return None
        
        minutes = int(self.duration // 60)
        seconds = int(self.duration % 60)
        return f"{minutes}:{seconds:02d}"
    
    @property
    def aspect_ratio(self) -> float:
        """Ratio d'aspect (largeur/hauteur)"""
        if self.width and self.height and self.height > 0:
            return self.width / self.height
        return None
    
    @property
    def is_landscape(self) -> bool:
        """Vérifier si format paysage"""
        ratio = self.aspect_ratio
        return ratio and ratio > 1.0
    
    @property
    def is_portrait(self) -> bool:
        """Vérifier si format portrait"""
        ratio = self.aspect_ratio
        return ratio and ratio < 1.0
    
    @property
    def is_square(self) -> bool:
        """Vérifier si format carré"""
        ratio = self.aspect_ratio
        return ratio and 0.9 <= ratio <= 1.1
    
    @property
    def compression_savings(self) -> str:
        """Économies grâce à la compression"""
        if not self.compressed_size or not self.file_size:
            return "0%"
        
        savings = ((self.file_size - self.compressed_size) / self.file_size) * 100
        return f"{savings:.1f}%"
    
    @property
    def status_display(self) -> str:
        """Nom d'affichage du statut"""
        status_names = {
            PortfolioStatus.ACTIVE: "Actif",
            PortfolioStatus.PENDING: "En attente",
            PortfolioStatus.REJECTED: "Rejeté",
            PortfolioStatus.ARCHIVED: "Archivé"
        }
        return status_names.get(self.status, self.status.value)
    
    @property
    def coordinates(self) -> tuple:
        """Coordonnées GPS de la photo"""
        if self.gps_latitude and self.gps_longitude:
            return (self.gps_latitude, self.gps_longitude)
        return None
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    def increment_views(self):
        """Incrémenter le nombre de vues"""
        self.views_count = (self.views_count or 0) + 1
    
    def archive(self):
        """Archiver l'élément"""
        self.status = PortfolioStatus.ARCHIVED
        self.archived_at = datetime.utcnow()
    
    def unarchive(self):
        """Désarchiver l'élément"""
        if self.status == PortfolioStatus.ARCHIVED:
            self.status = PortfolioStatus.ACTIVE
            self.archived_at = None
    
    def approve(self, admin_id: int, notes: str = None):
        """Approuver l'élément (modération)"""
        self.status = PortfolioStatus.ACTIVE
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_id
        if notes:
            self.moderation_notes = notes
    
    def reject(self, admin_id: int, reason: str):
        """Rejeter l'élément (modération)"""
        self.status = PortfolioStatus.REJECTED
        self.moderated_at = datetime.utcnow()
        self.moderated_by = admin_id
        self.moderation_notes = reason
    
    def set_featured(self, featured: bool = True):
        """Mettre en avant ou retirer de la mise en avant"""
        self.is_featured = featured
        # Si mis en avant, mettre en premier
        if featured and self.order_index == 0:
            self.order_index = 1
    
    def update_compression_status(self, status: CompressionStatus, 
                                 compressed_path: str = None, 
                                 compressed_size: int = None):
        """Mettre à jour le statut de compression"""
        self.compression_status = status
        if compressed_path:
            self.compressed_path = compressed_path
        if compressed_size:
            self.compressed_size = compressed_size
            if self.file_size:
                self.compression_ratio = compressed_size / self.file_size
    
    def generate_thumbnail_path(self) -> str:
        """Générer le chemin de la vignette"""
        if not self.file_path:
            return None
        
        # Changer l'extension et le dossier
        base_name = os.path.splitext(os.path.basename(self.file_path))[0]
        return f"uploads/portfolio/thumbnails/{base_name}_thumb.jpg"
    
    def get_display_title(self) -> str:
        """Obtenir le titre d'affichage"""
        if self.title:
            return self.title
        
        # Générer un titre basé sur le type et la date
        if self.is_image:
            return f"Photo du {self.created_at.strftime('%d/%m/%Y')}"
        else:
            return f"Vidéo du {self.created_at.strftime('%d/%m/%Y')}"
    
    def can_be_deleted_by_user(self) -> bool:
        """Vérifier si peut être supprimé par l'utilisateur"""
        # Ne peut pas supprimer si c'est le seul élément featured
        if self.is_featured:
            user_featured_count = (
                PortfolioItem.query
                .filter_by(user_id=self.user_id, is_featured=True)
                .filter(PortfolioItem.id != self.id)
                .count()
            )
            return user_featured_count > 0
        return True
    
    @classmethod
    def get_allowed_extensions(cls) -> list:
        """Obtenir les extensions autorisées"""
        return ['jpg', 'jpeg', 'png', 'gif', 'mp4']
    
    @classmethod
    def get_max_file_size_mb(cls, file_type: PortfolioType) -> int:
        """Obtenir la taille max selon le type"""
        if file_type == PortfolioType.IMAGE:
            return 5  # 5 MB pour les images
        else:  # VIDEO
            return 50  # 50 MB pour les vidéos
    
    @classmethod
    def is_valid_file_type(cls, extension: str, file_type: PortfolioType) -> bool:
        """Vérifier si l'extension correspond au type"""
        image_extensions = ['jpg', 'jpeg', 'png', 'gif']
        video_extensions = ['mp4']
        
        extension = extension.lower().lstrip('.')
        
        if file_type == PortfolioType.IMAGE:
            return extension in image_extensions
        else:  # VIDEO
            return extension in video_extensions
    
    def to_dict(self) -> dict:
        """Convertir en dictionnaire pour l'API"""
        return {
            "id": self.id,
            "title": self.get_display_title(),
            "description": self.description,
            "file_type": self.file_type.value,
            "file_url": self.file_url,
            "thumbnail_url": self.thumbnail_url,
            "width": self.width,
            "height": self.height,
            "duration": self.formatted_duration,
            "file_size": self.formatted_file_size,
            "is_featured": self.is_featured,
            "views_count": self.views_count,
            "status": self.status.value,
            "status_display": self.status_display,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "coordinates": self.coordinates
        }