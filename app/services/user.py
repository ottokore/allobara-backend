"""
Service utilisateurs AlloBara
CRUD utilisateurs, recherche avec géolocalisation, profils
"""

import math
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.sql import text

from app.models.user import User, UserRole, Gender, DocumentType
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.user import (
    PersonalInfoUpdate, ProfessionalInfoUpdate, LocationUpdate,
    SearchFilters, UserCardResponse, UserProfileResponse
)

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculer la distance entre deux points GPS en kilomètres (formule Haversine)
        """
        if not all([lat1, lon1, lat2, lon2]):
            return None
        
        # Rayon de la Terre en km
        R = 6371.0
        
        # Convertir en radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Différences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Formule Haversine
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def search_providers(
        self,
        filters: SearchFilters,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Rechercher des prestataires avec filtres et géolocalisation
        Support du scroll infini comme Facebook
        """
        try:
            # Base query : utilisateurs actifs avec abonnement
            query = self.db.query(User).join(Subscription).filter(
                and_(
                    User.is_active == True,
                    User.is_blocked == False,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE, 
                        SubscriptionStatus.TRIAL
                    ])
                )
            )
            
            # Filtre par texte (recherche dans nom, profession, description)
            if filters.query:
                search_term = f"%{filters.query.lower()}%"
                query = query.filter(
                    or_(
                        func.lower(User.first_name).like(search_term),
                        func.lower(User.last_name).like(search_term),
                        func.lower(User.profession).like(search_term),
                        func.lower(User.description).like(search_term)
                    )
                )
            
            # Filtre par domaine
            if filters.domain:
                query = query.filter(User.domain == filters.domain.value)
            
            # ✅ AJOUTÉ : Filtre par pays
            if filters.country:
                query = query.filter(User.country.ilike(f"%{filters.country}%"))
            
            # Filtre par ville
            if filters.city:
                # ✅ MODIFIÉ : Recherche exacte au lieu de LIKE pour éviter les faux positifs
                query = query.filter(
                    or_(
                        func.lower(User.city) == filters.city.lower(),
                        func.lower(User.commune) == filters.city.lower()
                    )
                )
            
            # Filtre par commune
            if filters.commune:
                query = query.filter(func.lower(User.commune) == filters.commune.lower())
            
            # Filtre par note minimum
            if filters.min_rating:
                query = query.filter(User.rating_average >= filters.min_rating)
            
            # Filtre prestataires vérifiés uniquement
            if filters.verified_only:
                query = query.filter(User.is_verified == True)
            
            # Filtre par prix
            if filters.min_price or filters.max_price:
                price_conditions = []
                if filters.min_price:
                    price_conditions.append(
                        or_(
                            User.daily_rate >= filters.min_price,
                            User.monthly_rate >= filters.min_price
                        )
                    )
                if filters.max_price:
                    price_conditions.append(
                        or_(
                            User.daily_rate <= filters.max_price,
                            User.monthly_rate <= filters.max_price
                        )
                    )
                if price_conditions:
                    query = query.filter(and_(*price_conditions))
            
            # Compter le total avant pagination
            total_count = query.count()
            
            print(f"🔍 Recherche: {total_count} résultats trouvés")
            print(f"   Filtres: city={filters.city}, country={filters.country}, domain={filters.domain}")
            
            # Tri par défaut : vérifiés d'abord, puis par note, puis par dernière activité
            query = query.order_by(
                desc(User.is_verified),
                desc(User.is_featured),  # Sponsorisés en premier
                desc(User.rating_average),
                desc(User.last_seen)
            )
            
            # Pagination
            offset = (page - 1) * limit
            users = query.offset(offset).limit(limit).all()
            
            # Convertir en réponse avec calcul de distance
            user_cards = []
            for user in users:
                # Calculer le rating réel depuis la table reviews
                from app.models.review import Review
                
                review_stats = self.db.query(
                    func.count(Review.id).label('count'),
                    func.avg(Review.rating).label('avg')
                ).filter(
                    Review.provider_id == user.id,
                    Review.status == 'approved'
                ).first()
                
                user_data = UserCardResponse.from_orm(user).dict()
                user_data['rating'] = float(review_stats.avg or 0.0)
                user_data['review_count'] = review_stats.count or 0
                
                # Calculer la distance si coordonnées fournies
                if (filters.user_latitude and filters.user_longitude and 
                    user.latitude and user.longitude):
                    distance = self.calculate_distance(
                        filters.user_latitude, filters.user_longitude,
                        user.latitude, user.longitude
                    )
                    user_data["distance_km"] = round(distance, 1) if distance else None
                
                user_cards.append(user_data)
            
            # Filtrer par distance si spécifiée
            if filters.max_distance_km and filters.user_latitude and filters.user_longitude:
                user_cards = [
                    user for user in user_cards 
                    if user.get("distance_km") and user["distance_km"] <= filters.max_distance_km
                ]
            
            # Trier par distance si géolocalisation active
            if filters.user_latitude and filters.user_longitude:
                user_cards.sort(key=lambda x: x.get("distance_km", float('inf')))
            
            return {
                "users": user_cards,
                "total": total_count,
                "page": page,
                "limit": limit,
                "has_next": len(user_cards) == limit,
                "filters_applied": {
                    "query": filters.query,
                    "domain": filters.domain.value if filters.domain else None,
                    "country": filters.country,
                    "city": filters.city,
                    "commune": filters.commune,
                    "verified_only": filters.verified_only,
                    "has_geolocation": bool(filters.user_latitude and filters.user_longitude)
                }
            }
            
        except Exception as e:
            print(f"❌ Erreur search_providers: {e}")
            import traceback
            traceback.print_exc()
            return {
                "users": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "has_next": False,
                "error": "Erreur lors de la recherche"
            }
    
    def get_provider_by_id(self, provider_id: int, viewer_location: Tuple[float, float] = None) -> Optional[Dict]:
        """
        Récupérer un prestataire par son ID (profil détaillé)
        """
        try:
            user = self.db.query(User).filter(
                and_(
                    User.id == provider_id,
                    User.is_active == True,
                    User.is_blocked == False
                )
            ).first()
            
            if not user:
                return None
            
            # Incrémenter les vues du profil
            user.increment_profile_views()
            self.db.commit()
            
            # Convertir en réponse
            # Calculer le rating réel depuis la table reviews
            from app.models.review import Review
            
            review_stats = self.db.query(
                func.count(Review.id).label('count'),
                func.avg(Review.rating).label('avg')
            ).filter(
                Review.provider_id == user.id,
                Review.status == 'approved'
            ).first()
            
            profile_data = UserProfileResponse.from_orm(user).dict()
            profile_data['rating'] = float(review_stats.avg or 0.0)
            profile_data['review_count'] = review_stats.count or 0
            
            # Calculer la distance si coordonnées du visiteur fournies
            if (viewer_location and user.latitude and user.longitude):
                distance = self.calculate_distance(
                    viewer_location[0], viewer_location[1],
                    user.latitude, user.longitude
                )
                profile_data["distance_km"] = round(distance, 1) if distance else None
            
            return profile_data
            
        except Exception as e:
            print(f"Erreur get_provider_by_id: {e}")
            return None
    
    def update_personal_info(self, user_id: int, update_data: PersonalInfoUpdate) -> Dict[str, Any]:
        """
        Mettre à jour les informations personnelles
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Utilisateur introuvable"}
            
            # Mettre à jour les champs
            user.first_name = update_data.first_name
            user.last_name = update_data.last_name
            user.birth_date = update_data.birth_date
            user.gender = update_data.gender
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Informations personnelles mises à jour",
                "profile_completion": user.profile_completion_percentage
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur update_personal_info: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}
    
    def update_professional_info(self, user_id: int, update_data: ProfessionalInfoUpdate) -> Dict[str, Any]:
        """
        Mettre à jour les informations professionnelles
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Utilisateur introuvable"}
            
            # Mettre à jour les champs
            user.profession = update_data.profession
            user.domain = update_data.domain.value
            user.years_experience = update_data.years_experience
            user.description = update_data.description
            user.daily_rate = update_data.daily_rate
            user.monthly_rate = update_data.monthly_rate
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Informations professionnelles mises à jour",
                "profile_completion": user.profile_completion_percentage
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur update_professional_info: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}
    
    def update_location(self, user_id: int, update_data: LocationUpdate) -> Dict[str, Any]:
        """
        Mettre à jour la localisation
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Utilisateur introuvable"}
            
            # Mettre à jour les champs
            user.country = update_data.country
            user.city = update_data.city
            user.commune = update_data.commune
            user.latitude = update_data.latitude
            user.longitude = update_data.longitude
            user.work_radius_km = update_data.work_radius_km
            user.address = update_data.address
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Localisation mise à jour",
                "profile_completion": user.profile_completion_percentage
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur update_location: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}
    
    def get_nearby_providers(
        self, 
        latitude: float, 
        longitude: float, 
        radius_km: int = 5,
        limit: int = 10
    ) -> List[Dict]:
        """
        Trouver les prestataires dans un rayon donné (3-5km)
        """
        try:
            # Requête avec calcul de distance SQL (plus efficace)
            distance_query = text(f"""
                SELECT *, (
                    6371 * acos(
                        cos(radians({latitude})) * 
                        cos(radians(latitude)) * 
                        cos(radians(longitude) - radians({longitude})) + 
                        sin(radians({latitude})) * 
                        sin(radians(latitude))
                    )
                ) as distance_km
                FROM users 
                WHERE latitude IS NOT NULL 
                AND longitude IS NOT NULL
                AND is_active = true 
                AND is_blocked = false
                HAVING distance_km <= {radius_km}
                ORDER BY distance_km ASC
                LIMIT {limit}
            """)
            
            result = self.db.execute(distance_query)
            providers = []
            
            for row in result:
                providers.append({
                    "id": row.id,
                    "full_name": f"{row.first_name} {row.last_name}" if row.first_name else "Prestataire",
                    "profession": row.profession,
                    "city": row.city,
                    "commune": row.commune,
                    "rating_average": row.rating_average,
                    "rating_count": row.rating_count,
                    "profile_picture": row.profile_picture,
                    "daily_rate": row.daily_rate,
                    "monthly_rate": row.monthly_rate,
                    "distance_km": round(row.distance_km, 1),
                    "is_verified": row.is_verified
                })
            
            return providers
            
        except Exception as e:
            print(f"Erreur get_nearby_providers: {e}")
            return []
    
    def get_featured_providers(self, limit: int = 10) -> List[Dict]:
        """
        Récupérer les prestataires mis en avant (sponsorisés)
        """
        try:
            users = self.db.query(User).join(Subscription).filter(
                and_(
                    User.is_active == True,
                    User.is_blocked == False,
                    User.is_featured == True,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIAL
                    ])
                )
            ).order_by(
                desc(User.rating_average),
                desc(User.last_seen)
            ).limit(limit).all()
            
            return [UserCardResponse.from_orm(user).dict() for user in users]
            
        except Exception as e:
            print(f"Erreur get_featured_providers: {e}")
            return []
    
    def get_providers_for_home_feed(
        self,
        page: int = 1,
        limit: int = 20,
        user_location: Tuple[float, float] = None
    ) -> Dict[str, Any]:
        """
        Récupérer les prestataires pour le feed d'accueil (scroll infini Facebook)
        """
        try:
            # CORRECTION: Query simplifiée qui fonctionne avec votre modèle
            query = self.db.query(User).filter(
                User.role == UserRole.PROVIDER  # Utilise l'enum correct
            )
            
            # Tri par date de création (les plus récents en premier)
            query = query.order_by(desc(User.created_at))
            
            # Pagination
            offset = (page - 1) * limit
            users = query.offset(offset).limit(limit).all()
            
            # Compter le total
            total_count = self.db.query(User).filter(
                User.role == UserRole.PROVIDER
            ).count()
            
            # Convertir en format de réponse
            user_list = []
            for user in users:
                # Calculer le rating réel depuis la table reviews
                from app.models.review import Review
                
                review_stats = self.db.query(
                    func.count(Review.id).label('count'),
                    func.avg(Review.rating).label('avg')
                ).filter(
                    Review.provider_id == user.id,
                    Review.status == 'approved'
                ).first()
                
                user_data = {
                    "id": user.id,
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "phone": user.phone,
                    "profession": user.profession or "",
                    "domain": user.domain or "",
                    "city": user.city or "",
                    "commune": user.commune or "",
                    "country": user.country or "",
                    "years_experience": user.years_experience,
                    "daily_rate": user.daily_rate,
                    "monthly_rate": user.monthly_rate,
                    "profile_picture": user.profile_picture,
                    "cover_picture": user.cover_picture,
                    # Calculer les ratings depuis les reviews
                    "rating": float(review_stats.avg or 0.0),
                    "review_count": review_stats.count or 0,
                    "is_verified": user.is_verified or False,
                    "is_available": True,
                    "is_online": True,
                    "portfolio": [item.file_url for item in user.portfolio_items] if user.portfolio_items else [],
                    "latitude": user.latitude,
                    "longitude": user.longitude,
                }
                user_list.append(user_data)
            
            # Calculer s'il y a une page suivante
            has_next = (page * limit) < total_count
            
            return {
                "users": user_list,
                "total": total_count,
                "page": page,
                "limit": limit,
                "has_next": has_next,
                "featured_count": 0
            }
            
        except Exception as e:
            print(f"Erreur get_providers_for_home_feed: {e}")
            return {
                "users": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "has_next": False,
                "featured_count": 0
            }
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """
        Récupérer les statistiques d'un utilisateur
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            # Compter les éléments du portfolio
            portfolio_count = len(user.portfolio_items) if user.portfolio_items else 0
            
            # Calculer les jours depuis la création
            days_since_creation = (datetime.utcnow() - user.created_at).days
            
            # Statut de l'abonnement
            subscription_status = "Aucun"
            subscription_days_remaining = None
            if user.subscription:
                subscription_status = user.subscription.status_display_name
                subscription_days_remaining = user.subscription.days_remaining
            
            return {
                "profile_views": user.profile_views,
                "total_contacts": user.total_contacts,
                "rating_average": user.rating_average,
                "rating_count": user.rating_count,
                "portfolio_items_count": portfolio_count,
                "days_since_creation": days_since_creation,
                "subscription_status": subscription_status,
                "subscription_days_remaining": subscription_days_remaining,
                "profile_completion": user.profile_completion_percentage
            }
            
        except Exception as e:
            print(f"Erreur get_user_stats: {e}")
            return None
    
    def increment_contact_count(self, provider_id: int) -> bool:
        """
        Incrémenter le compteur de contacts pour un prestataire
        """
        try:
            user = self.db.query(User).filter(User.id == provider_id).first()
            if user:
                user.increment_contacts()
                self.db.commit()
                return True
            return False
            
        except Exception as e:
            print(f"Erreur increment_contact_count: {e}")
            return False
    
    def get_cities_with_providers(self) -> List[Dict]:
        """
        Récupérer les villes avec le nombre de prestataires
        """
        try:
            result = self.db.query(
                User.city,
                func.count(User.id).label('provider_count')
            ).join(Subscription).filter(
                and_(
                    User.is_active == True,
                    User.city.isnot(None),
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE,
                        SubscriptionStatus.TRIAL
                    ])
                )
            ).group_by(User.city).order_by(
                desc('provider_count')
            ).all()
            
            cities = []
            for row in result:
                cities.append({
                    "name": row.city,
                    "provider_count": row.provider_count
                })
            
            return cities
            
        except Exception as e:
            print(f"Erreur get_cities_with_providers: {e}")
            return []
    
    def update_profile_picture(self, user_id: int, picture_url: str) -> Dict[str, Any]:
        """
        Mettre à jour la photo de profil
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Utilisateur introuvable"}
            
            user.profile_picture = picture_url
            user.updated_at = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "message": "Photo de profil mise à jour",
                "profile_picture": picture_url
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur update_profile_picture: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}
    
    def update_cover_picture(self, user_id: int, picture_url: str) -> Dict[str, Any]:
        """
        Mettre à jour la photo de couverture
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Utilisateur introuvable"}
            
            user.cover_picture = picture_url
            user.updated_at = datetime.utcnow()
            self.db.commit()
            
            return {
                "success": True,
                "message": "Photo de couverture mise à jour",
                "cover_picture": picture_url
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur update_cover_picture: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}