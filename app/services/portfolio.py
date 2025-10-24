"""
Service portfolio AlloBara
Gestion des réalisations des prestataires (images et vidéos)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc

from app.models.portfolio import PortfolioItem, PortfolioType, PortfolioStatus, CompressionStatus
from app.models.user import User
from app.services.file_upload import FileUploadService
from app.schemas.portfolio import PortfolioItemCreate, PortfolioItemUpdate

class PortfolioService:
    def __init__(self, db: Session):
        self.db = db
        self.file_service = FileUploadService()
    
    async def create_portfolio_item(
        self,
        user_id: int,
        file_data: bytes,
        original_filename: str,
        item_data: PortfolioItemCreate
    ) -> Dict[str, Any]:
        """
        Créer un élément de portfolio avec upload de fichier
        """
        try:
            # Vérifier que l'utilisateur n'a pas trop d'éléments (limite: 20)
            existing_count = self.db.query(PortfolioItem).filter(
                PortfolioItem.user_id == user_id
            ).count()
            
            if existing_count >= 20:
                return {
                    "success": False,
                    "message": "Limite de 20 éléments de portfolio atteinte"
                }
            
            # Upload du fichier
            upload_result = await self.file_service.upload_portfolio_item(
                file_data,
                original_filename,
                user_id,
                item_data.title,
                item_data.description
            )
            
            if not upload_result["success"]:
                return upload_result
            
            # Déterminer le type de fichier
            file_type = PortfolioType.IMAGE if upload_result["file_type"] == "image" else PortfolioType.VIDEO
            
            # Créer l'élément en base
            portfolio_item = PortfolioItem(
                user_id=user_id,
                title=item_data.title,
                description=item_data.description,
                file_path=upload_result["file_path"],
                file_name=original_filename,
                file_type=file_type,
                file_extension=upload_result["file_path"].split('.')[-1],
                file_size=upload_result["file_size"],
                file_hash=upload_result["file_hash"],
                width=upload_result.get("width"),
                height=upload_result.get("height"),
                duration=upload_result.get("duration"),
                thumbnail_path=upload_result.get("thumbnail_path"),
                status=PortfolioStatus.ACTIVE,  # Auto-approuvé pour l'instant
                order_index=item_data.order_index or existing_count,
                compression_status=CompressionStatus.ORIGINAL
            )
            
            self.db.add(portfolio_item)
            self.db.commit()
            self.db.refresh(portfolio_item)
            
            # Lancer la compression en arrière-plan si nécessaire
            if file_type == PortfolioType.IMAGE:
                await self._compress_item_async(portfolio_item.id)
            
            return {
                "success": True,
                "message": "Élément ajouté au portfolio",
                "data": portfolio_item.to_dict()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur create_portfolio_item: {e}")
            return {
                "success": False,
                "message": "Erreur lors de l'ajout au portfolio"
            }
    
    def get_user_portfolio(
        self,
        user_id: int,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Récupérer le portfolio complet d'un utilisateur
        """
        try:
            query = self.db.query(PortfolioItem).filter(
                PortfolioItem.user_id == user_id
            )
            
            if not include_inactive:
                query = query.filter(PortfolioItem.status == PortfolioStatus.ACTIVE)
            
            items = query.order_by(
                desc(PortfolioItem.is_featured),
                asc(PortfolioItem.order_index),
                desc(PortfolioItem.created_at)
            ).all()
            
            # Convertir en réponse
            items_data = [item.to_dict() for item in items]
            
            # Calculer les statistiques
            total_items = len(items)
            images_count = sum(1 for item in items if item.file_type == PortfolioType.IMAGE)
            videos_count = sum(1 for item in items if item.file_type == PortfolioType.VIDEO)
            featured_count = sum(1 for item in items if item.is_featured)
            total_views = sum(item.views_count for item in items)
            
            return {
                "items": items_data,
                "total_items": total_items,
                "images_count": images_count,
                "videos_count": videos_count,
                "featured_count": featured_count,
                "total_views": total_views
            }
            
        except Exception as e:
            print(f"Erreur get_user_portfolio: {e}")
            return {
                "items": [],
                "total_items": 0,
                "images_count": 0,
                "videos_count": 0,
                "featured_count": 0,
                "total_views": 0,
                "error": "Erreur lors de la récupération"
            }
    
    def get_portfolio_item(self, item_id: int, user_id: Optional[int] = None) -> Optional[Dict]:
        """
        Récupérer un élément spécifique du portfolio
        """
        try:
            query = self.db.query(PortfolioItem).filter(PortfolioItem.id == item_id)
            
            # Si user_id fourni, vérifier la propriété
            if user_id:
                query = query.filter(PortfolioItem.user_id == user_id)
            
            item = query.first()
            
            if not item:
                return None
            
            # Incrémenter les vues si c'est un accès public
            if not user_id or user_id != item.user_id:
                item.increment_views()
                self.db.commit()
            
            return item.to_dict()
            
        except Exception as e:
            print(f"Erreur get_portfolio_item: {e}")
            return None
    
    def update_portfolio_item(
        self,
        item_id: int,
        user_id: int,
        update_data: PortfolioItemUpdate
    ) -> Dict[str, Any]:
        """
        Mettre à jour un élément du portfolio
        """
        try:
            item = self.db.query(PortfolioItem).filter(
                and_(
                    PortfolioItem.id == item_id,
                    PortfolioItem.user_id == user_id
                )
            ).first()
            
            if not item:
                return {
                    "success": False,
                    "message": "Élément introuvable"
                }
            
            # Mettre à jour les champs
            if update_data.title is not None:
                item.title = update_data.title
            if update_data.description is not None:
                item.description = update_data.description
            if update_data.order_index is not None:
                item.order_index = update_data.order_index
            if update_data.is_featured is not None:
                item.set_featured(update_data.is_featured)
            
            item.updated_at = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "message": "Élément mis à jour",
                "data": item.to_dict()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur update_portfolio_item: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la mise à jour"
            }
    
    def delete_portfolio_item(self, item_id: int, user_id: int) -> Dict[str, Any]:
        """
        Supprimer un élément du portfolio
        """
        try:
            item = self.db.query(PortfolioItem).filter(
                and_(
                    PortfolioItem.id == item_id,
                    PortfolioItem.user_id == user_id
                )
            ).first()
            
            if not item:
                return {
                    "success": False,
                    "message": "Élément introuvable"
                }
            
            # Vérifier si peut être supprimé
            if not item.can_be_deleted_by_user():
                return {
                    "success": False,
                    "message": "Impossible de supprimer le seul élément mis en avant"
                }
            
            # Supprimer les fichiers
            if item.file_path:
                self.file_service.delete_file(item.file_path)
            if item.compressed_path:
                self.file_service.delete_file(item.compressed_path)
            if item.thumbnail_path:
                self.file_service.delete_file(item.thumbnail_path)
            
            # Supprimer de la base
            self.db.delete(item)
            self.db.commit()
            
            return {
                "success": True,
                "message": "Élément supprimé du portfolio"
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur delete_portfolio_item: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la suppression"
            }
    
    def reorder_portfolio_items(
        self,
        user_id: int,
        item_orders: List[Dict[str, int]]
    ) -> Dict[str, Any]:
        """
        Réorganiser les éléments du portfolio
        """
        try:
            # Vérifier que tous les éléments appartiennent à l'utilisateur
            item_ids = [item["id"] for item in item_orders]
            user_items = self.db.query(PortfolioItem).filter(
                and_(
                    PortfolioItem.user_id == user_id,
                    PortfolioItem.id.in_(item_ids)
                )
            ).all()
            
            if len(user_items) != len(item_ids):
                return {
                    "success": False,
                    "message": "Certains éléments n'appartiennent pas à votre portfolio"
                }
            
            # Mettre à jour les ordres
            for item_order in item_orders:
                item = next((i for i in user_items if i.id == item_order["id"]), None)
                if item:
                    item.order_index = item_order["order"]
                    item.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Portfolio réorganisé",
                "updated_count": len(item_orders)
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur reorder_portfolio_items: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la réorganisation"
            }
    
    def get_portfolio_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Statistiques du portfolio d'un utilisateur
        """
        try:
            items = self.db.query(PortfolioItem).filter(
                PortfolioItem.user_id == user_id
            ).all()
            
            if not items:
                return {
                    "total_items": 0,
                    "images_count": 0,
                    "videos_count": 0,
                    "featured_items": 0,
                    "total_views": 0,
                    "total_file_size_mb": 0,
                    "average_views_per_item": 0
                }
            
            # Calculer les statistiques
            total_items = len(items)
            images_count = sum(1 for item in items if item.file_type == PortfolioType.IMAGE)
            videos_count = sum(1 for item in items if item.file_type == PortfolioType.VIDEO)
            featured_items = sum(1 for item in items if item.is_featured)
            total_views = sum(item.views_count for item in items)
            total_file_size = sum(item.file_size or 0 for item in items)
            
            # Élément le plus vu
            most_viewed = max(items, key=lambda x: x.views_count)
            latest_item = max(items, key=lambda x: x.created_at)
            
            return {
                "total_items": total_items,
                "images_count": images_count,
                "videos_count": videos_count,
                "featured_items": featured_items,
                "total_views": total_views,
                "total_file_size_mb": round(total_file_size / (1024 * 1024), 2),
                "average_views_per_item": round(total_views / total_items, 1),
                "most_viewed_item": {
                    "id": most_viewed.id,
                    "title": most_viewed.get_display_title(),
                    "views": most_viewed.views_count
                } if most_viewed.views_count > 0 else None,
                "latest_item": {
                    "id": latest_item.id,
                    "title": latest_item.get_display_title(),
                    "created_at": latest_item.created_at.isoformat()
                }
            }
            
        except Exception as e:
            print(f"Erreur get_portfolio_stats: {e}")
            return {"error": "Erreur lors du calcul des statistiques"}
    
    async def bulk_action_portfolio(
        self,
        user_id: int,
        item_ids: List[int],
        action: str
    ) -> Dict[str, Any]:
        """
        Action en lot sur les éléments du portfolio
        """
        try:
            # Récupérer les éléments de l'utilisateur
            items = self.db.query(PortfolioItem).filter(
                and_(
                    PortfolioItem.user_id == user_id,
                    PortfolioItem.id.in_(item_ids)
                )
            ).all()
            
            if not items:
                return {
                    "success": False,
                    "message": "Aucun élément trouvé"
                }
            
            processed_count = 0
            
            for item in items:
                if action == "archive":
                    item.archive()
                    processed_count += 1
                elif action == "delete":
                    # Supprimer les fichiers
                    if item.file_path:
                        self.file_service.delete_file(item.file_path)
                    if item.compressed_path:
                        self.file_service.delete_file(item.compressed_path)
                    if item.thumbnail_path:
                        self.file_service.delete_file(item.thumbnail_path)
                    
                    self.db.delete(item)
                    processed_count += 1
                elif action == "feature":
                    item.set_featured(True)
                    processed_count += 1
                elif action == "unfeature":
                    item.set_featured(False)
                    processed_count += 1
            
            self.db.commit()
            
            action_names = {
                "archive": "archivé(s)",
                "delete": "supprimé(s)",
                "feature": "mis en avant",
                "unfeature": "retiré(s) de la mise en avant"
            }
            
            return {
                "success": True,
                "message": f"{processed_count} élément(s) {action_names.get(action, 'traité(s)')}",
                "processed_count": processed_count
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur bulk_action_portfolio: {e}")
            return {
                "success": False,
                "message": "Erreur lors de l'action en lot"
            }
    
    async def _compress_item_async(self, item_id: int):
        """
        Compresser un élément de portfolio en arrière-plan
        """
        try:
            import asyncio
            
            # Attendre un peu pour ne pas surcharger le système
            await asyncio.sleep(2)
            
            item = self.db.query(PortfolioItem).filter(PortfolioItem.id == item_id).first()
            if not item or item.file_type != PortfolioType.IMAGE:
                return
            
            # Marquer comme en cours de compression
            item.update_compression_status(CompressionStatus.COMPRESSING)
            self.db.commit()
            
            # Compresser le fichier
            compressed_path = await self.file_service.compress_image(item.file_path)
            
            if compressed_path:
                import os
                compressed_size = os.path.getsize(compressed_path)
                item.update_compression_status(
                    CompressionStatus.COMPRESSED,
                    compressed_path,
                    compressed_size
                )
                print(f"✅ Compression réussie pour l'élément {item_id}")
            else:
                item.update_compression_status(CompressionStatus.FAILED)
                print(f"❌ Échec compression pour l'élément {item_id}")
            
            self.db.commit()
            
        except Exception as e:
            print(f"Erreur _compress_item_async: {e}")
    
    def get_featured_portfolio_items(
        self,
        limit: int = 20,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """
        Récupérer les éléments de portfolio mis en avant
        """
        try:
            query = self.db.query(PortfolioItem).join(User).filter(
                and_(
                    PortfolioItem.is_featured == True,
                    PortfolioItem.status == PortfolioStatus.ACTIVE,
                    User.is_active == True,
                    User.is_verified == True
                )
            )
            
            if domain:
                query = query.filter(User.domain == domain)
            
            items = query.order_by(
                desc(PortfolioItem.views_count),
                desc(PortfolioItem.created_at)
            ).limit(limit).all()
            
            results = []
            for item in items:
                item_data = item.to_dict()
                item_data["user_name"] = item.user.full_name
                item_data["user_profession"] = item.user.profession
                item_data["user_city"] = item.user.city
                results.append(item_data)
            
            return results
            
        except Exception as e:
            print(f"Erreur get_featured_portfolio_items: {e}")
            return []
    
    def search_portfolio_items(
        self,
        query: Optional[str] = None,
        file_type: Optional[PortfolioType] = None,
        domain: Optional[str] = None,
        city: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Rechercher dans tous les portfolios
        """
        try:
            from sqlalchemy import func, or_
            
            search_query = self.db.query(PortfolioItem).join(User).filter(
                and_(
                    PortfolioItem.status == PortfolioStatus.ACTIVE,
                    User.is_active == True
                )
            )
            
            # Filtrer par texte
            if query:
                search_term = f"%{query.lower()}%"
                search_query = search_query.filter(
                    or_(
                        func.lower(PortfolioItem.title).like(search_term),
                        func.lower(PortfolioItem.description).like(search_term),
                        func.lower(User.profession).like(search_term)
                    )
                )
            
            # Filtrer par type de fichier
            if file_type:
                search_query = search_query.filter(PortfolioItem.file_type == file_type)
            
            # Filtrer par domaine utilisateur
            if domain:
                search_query = search_query.filter(User.domain == domain)
            
            # Filtrer par ville
            if city:
                search_query = search_query.filter(User.city.ilike(f"%{city}%"))
            
            # Compter le total
            total = search_query.count()
            
            # Paginer et trier
            items = search_query.order_by(
                desc(PortfolioItem.is_featured),
                desc(PortfolioItem.views_count),
                desc(PortfolioItem.created_at)
            ).offset((page - 1) * limit).limit(limit).all()
            
            # Convertir en réponse
            items_data = []
            for item in items:
                item_dict = item.to_dict()
                item_dict["user_name"] = item.user.full_name
                item_dict["user_profession"] = item.user.profession
                item_dict["user_city"] = item.user.city
                item_dict["user_rating"] = item.user.rating_average
                items_data.append(item_dict)
            
            return {
                "items": items_data,
                "total": total,
                "page": page,
                "limit": limit,
                "has_next": (page * limit) < total,
                "filters_applied": {
                    "query": query,
                    "file_type": file_type.value if file_type else None,
                    "domain": domain,
                    "city": city
                }
            }
            
        except Exception as e:
            print(f"Erreur search_portfolio_items: {e}")
            return {
                "items": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "has_next": False,
                "error": "Erreur lors de la recherche"
            }
    
    def get_portfolio_by_domain(self, domain: str, limit: int = 12) -> List[Dict]:
        """
        Récupérer des exemples de portfolio par domaine
        """
        try:
            items = self.db.query(PortfolioItem).join(User).filter(
                and_(
                    User.domain == domain,
                    PortfolioItem.status == PortfolioStatus.ACTIVE,
                    User.is_active == True,
                    User.is_verified == True
                )
            ).order_by(
                desc(PortfolioItem.is_featured),
                desc(PortfolioItem.views_count)
            ).limit(limit).all()
            
            results = []
            for item in items:
                item_data = item.to_dict()
                item_data["user_name"] = item.user.full_name
                item_data["user_profession"] = item.user.profession
                results.append(item_data)
            
            return results
            
        except Exception as e:
            print(f"Erreur get_portfolio_by_domain: {e}")
            return []
    
    # =========================================
    # MÉTHODES ADMIN
    # =========================================
    
    def get_pending_moderation_items(self, limit: int = 50) -> List[Dict]:
        """
        Récupérer les éléments en attente de modération
        """
        try:
            items = self.db.query(PortfolioItem).join(User).filter(
                PortfolioItem.status == PortfolioStatus.PENDING
            ).order_by(
                PortfolioItem.created_at.asc()
            ).limit(limit).all()
            
            results = []
            for item in items:
                item_data = item.to_dict()
                item_data["user_name"] = item.user.full_name
                item_data["user_phone"] = item.user.phone
                results.append(item_data)
            
            return results
            
        except Exception as e:
            print(f"Erreur get_pending_moderation_items: {e}")
            return []
    
    def moderate_portfolio_item(
        self,
        item_id: int,
        action: str,
        admin_id: int,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Modérer un élément de portfolio (admin)
        """
        try:
            item = self.db.query(PortfolioItem).filter(PortfolioItem.id == item_id).first()
            
            if not item:
                return {
                    "success": False,
                    "message": "Élément introuvable"
                }
            
            if action == "approve":
                item.approve(admin_id, reason)
            elif action == "reject":
                item.reject(admin_id, reason or "Contenu inapproprié")
            elif action == "hide":
                item.status = PortfolioStatus.ARCHIVED
                item.moderated_at = datetime.utcnow()
                item.moderated_by = admin_id
                if reason:
                    item.moderation_notes = reason
            else:
                return {
                    "success": False,
                    "message": "Action invalide"
                }
            
            self.db.commit()
            
            action_names = {
                "approve": "approuvé",
                "reject": "rejeté", 
                "hide": "masqué"
            }
            
            return {
                "success": True,
                "message": f"Élément {action_names[action]}",
                "action": action,
                "item_id": item_id
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur moderate_portfolio_item: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la modération"
            }