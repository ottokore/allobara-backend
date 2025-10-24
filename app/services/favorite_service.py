"""
Service de gestion des favoris AlloBara
Logique métier pour les favoris utilisateurs
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime

from app.models.favorite import Favorite
from app.models.user import User
from app.schemas.user import UserCardResponse


class FavoriteService:
    def __init__(self, db: Session):
        self.db = db
    
    def add_favorite(self, user_id: int, provider_id: int) -> Dict[str, Any]:
        """
        Ajouter un prestataire aux favoris
        """
        try:
            # Vérifier que le prestataire existe
            provider = self.db.query(User).filter(User.id == provider_id).first()
            if not provider:
                return {
                    "success": False,
                    "message": "Prestataire introuvable",
                    "is_favorite": False,
                    "provider_id": provider_id
                }
            
            # Vérifier que l'utilisateur ne s'ajoute pas lui-même
            if user_id == provider_id:
                return {
                    "success": False,
                    "message": "Vous ne pouvez pas vous ajouter vous-même en favori",
                    "is_favorite": False,
                    "provider_id": provider_id
                }
            
            # Vérifier si déjà en favori
            existing = self.db.query(Favorite).filter(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.provider_id == provider_id
                )
            ).first()
            
            if existing:
                return {
                    "success": False,
                    "message": "Ce prestataire est déjà dans vos favoris",
                    "is_favorite": True,
                    "provider_id": provider_id
                }
            
            # Créer le favori
            favorite = Favorite(
                user_id=user_id,
                provider_id=provider_id,
                created_at=datetime.utcnow()
            )
            
            self.db.add(favorite)
            self.db.commit()
            self.db.refresh(favorite)
            
            return {
                "success": True,
                "message": "Prestataire ajouté aux favoris",
                "is_favorite": True,
                "provider_id": provider_id
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"❌ Erreur add_favorite: {e}")
            return {
                "success": False,
                "message": f"Erreur lors de l'ajout aux favoris: {str(e)}",
                "is_favorite": False,
                "provider_id": provider_id
            }
    
    def remove_favorite(self, user_id: int, provider_id: int) -> Dict[str, Any]:
        """
        Retirer un prestataire des favoris
        """
        try:
            favorite = self.db.query(Favorite).filter(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.provider_id == provider_id
                )
            ).first()
            
            if not favorite:
                return {
                    "success": False,
                    "message": "Ce prestataire n'est pas dans vos favoris",
                    "is_favorite": False,
                    "provider_id": provider_id
                }
            
            self.db.delete(favorite)
            self.db.commit()
            
            return {
                "success": True,
                "message": "Prestataire retiré des favoris",
                "is_favorite": False,
                "provider_id": provider_id
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"❌ Erreur remove_favorite: {e}")
            return {
                "success": False,
                "message": f"Erreur lors de la suppression du favori: {str(e)}",
                "is_favorite": True,
                "provider_id": provider_id
            }
    
    def toggle_favorite(self, user_id: int, provider_id: int) -> Dict[str, Any]:
        """
        Basculer le statut favori (ajouter si absent, retirer si présent)
        """
        is_favorite = self.is_favorite(user_id, provider_id)
        
        if is_favorite:
            return self.remove_favorite(user_id, provider_id)
        else:
            return self.add_favorite(user_id, provider_id)
    
    def is_favorite(self, user_id: int, provider_id: int) -> bool:
        """
        Vérifier si un prestataire est en favori
        """
        try:
            favorite = self.db.query(Favorite).filter(
                and_(
                    Favorite.user_id == user_id,
                    Favorite.provider_id == provider_id
                )
            ).first()
            
            return favorite is not None
            
        except Exception as e:
            print(f"❌ Erreur is_favorite: {e}")
            return False
    
    def get_user_favorites(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Récupérer la liste des prestataires favoris d'un utilisateur
        """
        try:
            # Query pour récupérer les favoris avec les infos des prestataires
            query = self.db.query(User).join(
                Favorite, User.id == Favorite.provider_id
            ).filter(
                Favorite.user_id == user_id
            ).order_by(desc(Favorite.created_at))
            
            # Compter le total
            total = query.count()
            
            # Pagination
            offset = (page - 1) * limit
            providers = query.offset(offset).limit(limit).all()
            
            # Convertir en format UserCardResponse
            favorites_list = []
            for provider in providers:
                # Calculer le rating depuis les reviews
                from app.models.review import Review
                from sqlalchemy import func
                
                review_stats = self.db.query(
                    func.count(Review.id).label('count'),
                    func.avg(Review.rating).label('avg')
                ).filter(
                    Review.provider_id == provider.id,
                    Review.status == 'approved'
                ).first()
                
                provider_data = UserCardResponse.from_orm(provider).dict()
                provider_data['rating'] = float(review_stats.avg or 0.0)
                provider_data['review_count'] = review_stats.count or 0
                provider_data['is_favorite'] = True  # Forcément vrai puisque c'est la liste des favoris
                
                favorites_list.append(provider_data)
            
            return {
                "favorites": favorites_list,
                "total": total,
                "page": page,
                "limit": limit,
                "has_next": (page * limit) < total
            }
            
        except Exception as e:
            print(f"❌ Erreur get_user_favorites: {e}")
            import traceback
            traceback.print_exc()
            return {
                "favorites": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "has_next": False
            }
    
    def get_favorites_count(self, user_id: int) -> int:
        """
        Compter le nombre de favoris d'un utilisateur
        """
        try:
            count = self.db.query(Favorite).filter(
                Favorite.user_id == user_id
            ).count()
            return count
            
        except Exception as e:
            print(f"❌ Erreur get_favorites_count: {e}")
            return 0
    
    def get_provider_favorites_count(self, provider_id: int) -> int:
        """
        Compter combien d'utilisateurs ont mis ce prestataire en favori
        """
        try:
            count = self.db.query(Favorite).filter(
                Favorite.provider_id == provider_id
            ).count()
            return count
            
        except Exception as e:
            print(f"❌ Erreur get_provider_favorites_count: {e}")
            return 0