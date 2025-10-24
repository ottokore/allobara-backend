"""
Endpoints API pour les favoris
Routes: /api/v1/users/favorites/*
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.api.deps.auth import get_current_user
from app.models.user import User
from app.services.favorite_service import FavoriteService
from app.schemas.favorite import (
    FavoriteToggleResponse,
    FavoriteStatusResponse,
    FavoriteListResponse
)


router = APIRouter()


@router.post("/{provider_id}", response_model=FavoriteToggleResponse)
async def add_to_favorites(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    ✅ Ajouter un prestataire aux favoris
    
    **Requête:** POST /api/v1/users/favorites/{provider_id}
    
    **Headers:**
    - Authorization: Bearer {token}
    
    **Réponse:**
    ```json
    {
        "success": true,
        "message": "Prestataire ajouté aux favoris",
        "is_favorite": true,
        "provider_id": 36
    }
    ```
    """
    try:
        service = FavoriteService(db)
        result = service.add_favorite(current_user.id, provider_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur add_to_favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'ajout aux favoris"
        )


@router.delete("/{provider_id}", response_model=FavoriteToggleResponse)
async def remove_from_favorites(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    ❌ Retirer un prestataire des favoris
    
    **Requête:** DELETE /api/v1/users/favorites/{provider_id}
    
    **Headers:**
    - Authorization: Bearer {token}
    
    **Réponse:**
    ```json
    {
        "success": true,
        "message": "Prestataire retiré des favoris",
        "is_favorite": false,
        "provider_id": 36
    }
    ```
    """
    try:
        service = FavoriteService(db)
        result = service.remove_favorite(current_user.id, provider_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur remove_from_favorites: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression du favori"
        )


@router.put("/{provider_id}/toggle", response_model=FavoriteToggleResponse)
async def toggle_favorite(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    🔄 Basculer le statut favori (ajouter si absent, retirer si présent)
    
    **Requête:** PUT /api/v1/users/favorites/{provider_id}/toggle
    
    **Headers:**
    - Authorization: Bearer {token}
    
    **Réponse:**
    ```json
    {
        "success": true,
        "message": "Prestataire ajouté aux favoris",
        "is_favorite": true,
        "provider_id": 36
    }
    ```
    """
    try:
        service = FavoriteService(db)
        result = service.toggle_favorite(current_user.id, provider_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur toggle_favorite: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du basculement du favori"
        )


@router.get("/check/{provider_id}", response_model=FavoriteStatusResponse)
async def check_favorite_status(
    provider_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    ✔️ Vérifier si un prestataire est en favori
    
    **Requête:** GET /api/v1/users/favorites/check/{provider_id}
    
    **Headers:**
    - Authorization: Bearer {token}
    
    **Réponse:**
    ```json
    {
        "is_favorite": true,
        "provider_id": 36
    }
    ```
    """
    try:
        service = FavoriteService(db)
        is_favorite = service.is_favorite(current_user.id, provider_id)
        
        return {
            "is_favorite": is_favorite,
            "provider_id": provider_id
        }
        
    except Exception as e:
        print(f"❌ Erreur check_favorite_status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification du statut favori"
        )


@router.get("", response_model=FavoriteListResponse)
async def get_my_favorites(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    📋 Récupérer la liste de mes prestataires favoris
    
    **Requête:** GET /api/v1/users/favorites?page=1&limit=20
    
    **Headers:**
    - Authorization: Bearer {token}
    
    **Query Params:**
    - page: Numéro de page (défaut: 1)
    - limit: Nombre par page (défaut: 20)
    
    **Réponse:**
    ```json
    {
        "favorites": [
            {
                "id": 36,
                "first_name": "Armand",
                "last_name": "Kouassi",
                "profession": "Electricien",
                "city": "Marcory",
                "rating": 3.0,
                "review_count": 1,
                "is_favorite": true,
                ...
            }
        ],
        "total": 5,
        "page": 1,
        "limit": 20
    }
    ```
    """
    try:
        service = FavoriteService(db)
        result = service.get_user_favorites(current_user.id, page, limit)
        
        return result
        
    except Exception as e:
        print(f"❌ Erreur get_my_favorites: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des favoris"
        )


@router.get("/count", response_model=dict)
async def get_favorites_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    🔢 Compter le nombre de favoris
    
    **Requête:** GET /api/v1/users/favorites/count
    
    **Headers:**
    - Authorization: Bearer {token}
    
    **Réponse:**
    ```json
    {
        "count": 5
    }
    ```
    """
    try:
        service = FavoriteService(db)
        count = service.get_favorites_count(current_user.id)
        
        return {"count": count}
        
    except Exception as e:
        print(f"❌ Erreur get_favorites_count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du comptage des favoris"
        )