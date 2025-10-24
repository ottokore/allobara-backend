# backend/app/api/endpoints/reviews.py
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime

from app.db.database import get_db
from app.models.review import Review, ReviewStatus
from app.models.user import User
from app.schemas.review import (
    ReviewAnonymous, 
    ReviewResponse, 
    ReviewListResponse,
    ReviewStats
)

router = APIRouter()

def review_to_response(review: Review) -> dict:
    """Convertir un Review en ReviewResponse"""
    # Déterminer le nom à afficher
    if review.is_anonymous:
        display_name = "Client anonyme"
    else:
        display_name = review.client_name or "Client"
    
    return {
        "id": review.id,
        "providerId": review.provider_id,
        "clientId": None,
        "clientName": display_name,  # ✅ Utiliser le nom réel si pas anonyme
        "clientAvatar": None,
        "rating": float(review.rating),
        "comment": review.comment or "",
        "isVerified": review.is_verified,
        "isAnonymous": review.is_anonymous,
        "serviceType": review.service_type,
        "createdAt": review.created_at.isoformat() if review.created_at else None,
        "updatedAt": review.updated_at.isoformat() if review.updated_at else None,
    }

@router.get("/{provider_id}/reviews")
async def get_provider_reviews(
    provider_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Récupérer tous les avis approuvés d'un prestataire"""
    
    # Vérifier que le prestataire existe
    provider = db.query(User).filter(User.id == provider_id).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestataire non trouvé"
        )
    
    # Récupérer uniquement les avis approuvés
    reviews = db.query(Review).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED
    ).order_by(desc(Review.created_at)).offset(skip).limit(limit).all()
    
    # Calculer les statistiques
    stats = db.query(
        func.count(Review.id).label('total'),
        func.avg(Review.rating).label('average')
    ).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED
    ).first()
    
    total = stats.total or 0
    average_rating = float(stats.average) if stats.average else 0.0
    
    # Distribution des notes (1 à 5)
    rating_dist_query = db.query(
        Review.rating,
        func.count(Review.id)
    ).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED
    ).group_by(Review.rating).all()
    
    rating_distribution = {int(rating): count for rating, count in rating_dist_query}
    # Initialiser toutes les notes de 1 à 5
    for i in range(1, 6):
        if i not in rating_distribution:
            rating_distribution[i] = 0
    
    # Convertir les reviews en format API
    reviews_data = [review_to_response(review) for review in reviews]
    
    return {
        "reviews": reviews_data,
        "total": total,
        "average_rating": round(average_rating, 1),
        "rating_distribution": rating_distribution
    }

@router.post("/{provider_id}/reviews/anonymous")
async def create_anonymous_review(
    provider_id: int,
    review_data: ReviewAnonymous,
    request: Request,
    db: Session = Depends(get_db)
):
    """Créer un avis anonyme (sans authentification)"""
    
    # Vérifier que le prestataire existe
    provider = db.query(User).filter(User.id == provider_id).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestataire non trouvé"
        )
    
    # Obtenir l'IP du client
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")
    
    # Créer l'avis
    new_review = Review(
        provider_id=provider_id,
        client_name=review_data.client_name,
        client_phone=review_data.client_phone,
        client_location=review_data.client_location,
        rating=review_data.rating,
        comment=review_data.comment,
        service_type=review_data.service_type,
        is_anonymous=False,  # ✅ CHANGÉ : Afficher le nom du client
        is_verified=False,
        status=ReviewStatus.PENDING,
        source="app",
        ip_address=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
        created_at=datetime.utcnow()
    )
    
    # Auto-approuver si les conditions sont remplies
    if new_review.should_auto_approve():
        new_review.status = ReviewStatus.APPROVED
        new_review.moderated_at = datetime.utcnow()
    
    db.add(new_review)
    db.flush()
    
    # Mettre à jour les statistiques du prestataire si approuvé
    if new_review.status == ReviewStatus.APPROVED:
        approved_reviews = db.query(Review).filter(
            Review.provider_id == provider_id,
            Review.status == ReviewStatus.APPROVED
        ).all()
        
        provider.review_count = len(approved_reviews)
        if approved_reviews:
            provider.rating = sum(r.rating for r in approved_reviews) / len(approved_reviews)
    
    db.commit()
    db.refresh(new_review)
    
    return review_to_response(new_review)

@router.get("/{provider_id}/reviews/stats")
async def get_review_stats(
    provider_id: int,
    db: Session = Depends(get_db)
):
    """Obtenir les statistiques des avis d'un prestataire"""
    
    provider = db.query(User).filter(User.id == provider_id).first()
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestataire non trouvé"
        )
    
    # Statistiques sur les avis approuvés uniquement
    stats = db.query(
        func.count(Review.id).label('total'),
        func.avg(Review.rating).label('average'),
        func.max(Review.created_at).label('last_review')
    ).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED
    ).first()
    
    verified_count = db.query(func.count(Review.id)).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED,
        Review.is_verified == True
    ).scalar()
    
    # Distribution des notes
    rating_dist_query = db.query(
        Review.rating,
        func.count(Review.id)
    ).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED
    ).group_by(Review.rating).all()
    
    rating_distribution = {int(rating): count for rating, count in rating_dist_query}
    for i in range(1, 6):
        if i not in rating_distribution:
            rating_distribution[i] = 0
    
    return {
        "providerId": provider_id,
        "averageRating": round(float(stats.average), 1) if stats.average else 0.0,
        "totalReviews": stats.total or 0,
        "ratingDistribution": rating_distribution,
        "verifiedReviews": verified_count or 0,
        "lastReviewDate": stats.last_review
    }

@router.post("/{review_id}/helpful")
async def mark_review_helpful(
    review_id: int,
    db: Session = Depends(get_db)
):
    """Marquer un avis comme utile"""
    
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avis non trouvé"
        )
    
    review.mark_helpful()
    db.commit()
    
    return {"message": "Avis marqué comme utile", "helpful_count": review.helpful_count}

@router.post("/{review_id}/report")
async def report_review(
    review_id: int,
    reason: str,
    db: Session = Depends(get_db)
):
    """Signaler un avis"""
    
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avis non trouvé"
        )
    
    review.report(reason)
    db.commit()
    
    return {"message": "Avis signalé avec succès"}

@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    db: Session = Depends(get_db)
):
    """Supprimer un avis (admin uniquement)"""
    
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avis non trouvé"
        )
    
    provider_id = review.provider_id
    db.delete(review)
    
    # Recalculer les stats du prestataire
    approved_reviews = db.query(Review).filter(
        Review.provider_id == provider_id,
        Review.status == ReviewStatus.APPROVED
    ).all()
    
    provider = db.query(User).filter(User.id == provider_id).first()
    if provider:
        provider.review_count = len(approved_reviews)
        if approved_reviews:
            provider.rating = sum(r.rating for r in approved_reviews) / len(approved_reviews)
        else:
            provider.rating = 0.0
    
    db.commit()
    
    return {"message": "Avis supprimé avec succès"}