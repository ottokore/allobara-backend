"""
Schémas Pydantic pour le portfolio
Validation des réalisations des prestataires
"""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, validator, Field
from enum import Enum

# =========================================
# ENUMS POUR VALIDATION
# =========================================

class PortfolioTypeEnum(str, Enum):
    IMAGE = "image"
    VIDEO = "video"

class PortfolioStatusEnum(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    REJECTED = "rejected"
    ARCHIVED = "archived"

# =========================================
# SCHÉMAS DE REQUÊTE
# =========================================

class PortfolioItemCreate(BaseModel):
    """
    Création d'un élément de portfolio
    """
    title: Optional[str] = Field(None, max_length=200, description="Titre de la réalisation")
    description: Optional[str] = Field(None, max_length=1000, description="Description du travail")
    service_type: Optional[str] = Field(None, max_length=100, description="Type de service réalisé")
    order_index: int = Field(0, ge=0, le=100, description="Ordre d'affichage")

class PortfolioItemUpdate(BaseModel):
    """
    Mise à jour d'un élément de portfolio
    """
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    order_index: Optional[int] = Field(None, ge=0, le=100)
    is_featured: Optional[bool] = None

class PortfolioReorderRequest(BaseModel):
    """
    Réorganiser les éléments du portfolio
    """
    item_orders: List[Dict[str, int]] = Field(..., description="Liste des ID et nouveaux indices")
    
    @validator('item_orders')
    def validate_orders(cls, v):
        if len(v) > 50:  # Limite raisonnable
            raise ValueError('Trop d\'éléments à réorganiser')
        
        for item in v:
            if 'id' not in item or 'order' not in item:
                raise ValueError('Chaque élément doit avoir un id et un order')
            if not isinstance(item['order'], int) or item['order'] < 0:
                raise ValueError('L\'ordre doit être un entier positif')
        
        return v

class BulkPortfolioAction(BaseModel):
    """
    Actions en lot sur le portfolio
    """
    item_ids: List[int] = Field(..., min_items=1, max_items=20)
    action: str = Field(..., description="archive, delete, feature, unfeature")

# =========================================
# SCHÉMAS DE RÉPONSE
# =========================================

class PortfolioItemResponse(BaseModel):
    """
    Réponse complète d'un élément de portfolio
    """
    id: int
    title: str
    description: Optional[str]
    file_type: str
    file_url: str
    thumbnail_url: str
    width: Optional[int]
    height: Optional[int]
    duration: Optional[str]  # Formatée pour vidéos
    file_size: str  # Formatée
    is_featured: bool
    views_count: int
    status: str
    status_display: str
    order_index: int
    created_at: datetime
    coordinates: Optional[tuple]
    
    class Config:
        from_attributes = True

class PortfolioItemCard(BaseModel):
    """
    Carte simplifiée pour la grille de portfolio
    """
    id: int
    title: str
    file_type: str
    thumbnail_url: str
    is_featured: bool
    views_count: int
    
    class Config:
        from_attributes = True

class PortfolioGalleryResponse(BaseModel):
    """
    Galerie complète du portfolio d'un utilisateur
    """
    items: List[PortfolioItemResponse]
    total_items: int
    images_count: int
    videos_count: int
    featured_count: int
    total_views: int

class PortfolioStatsResponse(BaseModel):
    """
    Statistiques du portfolio
    """
    total_items: int
    images_count: int
    videos_count: int
    featured_items: int
    total_views: int
    total_file_size_mb: float
    average_views_per_item: float
    most_viewed_item: Optional[Dict]
    latest_item: Optional[Dict]

# =========================================
# SCHÉMAS D'UPLOAD
# =========================================

class FileUploadResponse(BaseModel):
    """
    Réponse après upload de fichier
    """
    success: bool
    message: str
    file_id: Optional[int] = None
    file_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    file_size: Optional[str] = None
    compression_applied: bool = False

class MultipleUploadResponse(BaseModel):
    """
    Réponse pour upload multiple
    """
    success: bool
    uploaded_count: int
    failed_count: int
    uploaded_items: List[FileUploadResponse]
    errors: List[str]

# =========================================
# SCHÉMAS DE VALIDATION ADMIN
# =========================================

class PortfolioModerationRequest(BaseModel):
    """
    Modération d'un élément de portfolio
    """
    action: str = Field(..., description="approve, reject, hide")
    reason: Optional[str] = Field(None, max_length=500, description="Raison de la décision")

class PortfolioAdminResponse(BaseModel):
    """
    Réponse portfolio pour l'admin
    """
    id: int
    user_id: int
    user_name: str
    title: str
    file_type: str
    file_url: str
    status: str
    is_featured: bool
    views_count: int
    created_at: datetime
    moderation_notes: Optional[str]
    moderated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class PendingModerationResponse(BaseModel):
    """
    Éléments en attente de modération
    """
    pending_items: List[PortfolioAdminResponse]
    total_pending: int

# =========================================
# SCHÉMAS DE RECHERCHE ET FILTRES
# =========================================

class PortfolioSearchFilters(BaseModel):
    """
    Filtres de recherche dans les portfolios
    """
    file_type: Optional[PortfolioTypeEnum] = None
    user_domain: Optional[str] = None
    city: Optional[str] = None
    featured_only: bool = False
    min_views: Optional[int] = Field(None, ge=0)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class PortfolioSearchResponse(BaseModel):
    """
    Résultats de recherche dans les portfolios
    """
    items: List[PortfolioItemCard]
    total: int
    page: int
    limit: int
    has_next: bool
    filters_applied: dict

# =========================================
# SCHÉMAS UTILITAIRES
# =========================================

class CompressionReport(BaseModel):
    """
    Rapport de compression d'un fichier
    """
    original_size: int
    compressed_size: int
    compression_ratio: float
    savings_percentage: float
    processing_time_seconds: float

class PortfolioBackupRequest(BaseModel):
    """
    Demande de sauvegarde du portfolio
    """
    user_id: int
    include_videos: bool = True
    compression_level: int = Field(70, ge=10, le=100, description="Niveau de compression")

class PortfolioImportRequest(BaseModel):
    """
    Import en lot d'éléments de portfolio
    """
    source_urls: List[str] = Field(..., max_items=10, description="URLs des fichiers à importer")
    default_title: Optional[str] = None
    default_description: Optional[str] = None