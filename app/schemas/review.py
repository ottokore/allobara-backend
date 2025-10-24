# backend/app/schemas/review.py
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class ReviewAnonymous(BaseModel):
    """Schéma pour les avis anonymes sans authentification"""
    client_name: str = Field(..., min_length=3, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field(..., min_length=10, max_length=1000)
    client_phone: Optional[str] = None
    client_location: Optional[str] = None
    service_type: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('La note doit être entre 1 et 5')
        return v
    
    @validator('comment')
    def validate_comment(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Le commentaire doit contenir au moins 10 caractères')
        return v.strip()

class ReviewResponse(BaseModel):
    """Réponse API pour un avis"""
    id: int
    providerId: int
    clientId: Optional[str] = None
    clientName: str
    clientAvatar: Optional[str] = None
    rating: float
    comment: str
    isVerified: bool
    isAnonymous: bool
    serviceType: Optional[str] = None
    createdAt: datetime
    updatedAt: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ReviewListResponse(BaseModel):
    """Réponse pour la liste des avis"""
    reviews: list[ReviewResponse]
    total: int
    average_rating: float
    rating_distribution: dict

class ReviewStats(BaseModel):
    """Statistiques des avis d'un prestataire"""
    providerId: int
    averageRating: float
    totalReviews: int
    ratingDistribution: dict
    verifiedReviews: int
    lastReviewDate: Optional[datetime] = None
    
    class Config:
        populate_by_name = True