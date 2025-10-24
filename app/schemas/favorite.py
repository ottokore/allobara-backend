"""
Schémas Pydantic pour les favoris
Validation et sérialisation des données
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FavoriteBase(BaseModel):
    """Schéma de base pour les favoris"""
    provider_id: int


class FavoriteCreate(FavoriteBase):
    """Schéma pour créer un favori"""
    pass


class FavoriteResponse(BaseModel):
    """Schéma de réponse pour un favori"""
    id: int
    user_id: int
    provider_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class FavoriteStatusResponse(BaseModel):
    """Schéma pour vérifier si un prestataire est en favori"""
    is_favorite: bool
    provider_id: int


class FavoriteToggleResponse(BaseModel):
    """Schéma de réponse pour l'ajout/suppression d'un favori"""
    success: bool
    message: str
    is_favorite: bool
    provider_id: int


class FavoriteListResponse(BaseModel):
    """Schéma de réponse pour la liste des favoris"""
    favorites: list
    total: int
    page: int
    limit: int