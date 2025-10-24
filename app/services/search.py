# app/services/search.py

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
from geopy.distance import geodesic
import math

from app.models.user import User
from app.models.subscription import Subscription
from app.core.config import settings

class SearchService:
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calcul de la distance en km entre deux points avec la formule Haversine
        """
        # Rayon de la Terre en km
        R = 6371.0
        
        # Conversion en radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Différences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Formule Haversine
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    @staticmethod
    def search_providers(
        db: Session,
        query: Optional[str] = None,
        category: Optional[str] = None,
        city: Optional[str] = None,
        commune: Optional[str] = None,
        country: Optional[str] = None,
        min_rating: Optional[float] = None,
        max_price: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: int = 5,  # Rayon par défaut de 5km
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "relevance"  # relevance, distance, rating, price
    ) -> Dict[str, Any]:
        """
        Recherche avancée de prestataires avec géolocalisation
        """
        
        # Query de base : utilisateurs actifs avec abonnements valides
        base_query = db.query(User).join(Subscription).filter(
            and_(
                User.is_active == True,
                User.subscription_status == "active",
                Subscription.is_active == True,
                Subscription.end_date > func.now()
            )
        )
        
        # Filtres texte
        if query:
            search_term = f"%{query.lower()}%"
            base_query = base_query.filter(
                or_(
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term),
                    func.lower(User.business_category).like(search_term),
                    func.lower(User.description).like(search_term)
                )
            )
        
        # Filtre par catégorie
        if category:
            base_query = base_query.filter(
                func.lower(User.business_category) == category.lower()
            )
        
        # Filtres géographiques
        if country:
            base_query = base_query.filter(User.country == country)
        if city:
            base_query = base_query.filter(
                func.lower(User.city) == city.lower()
            )
        if commune:
            base_query = base_query.filter(
                func.lower(User.commune) == commune.lower()
            )
        
        # Filtre par note minimale
        if min_rating:
            base_query = base_query.filter(User.average_rating >= min_rating)
        
        # Filtre par prix maximum
        if max_price:
            base_query = base_query.filter(User.daily_rate <= max_price)
        
        # Récupération des résultats bruts
        all_providers = base_query.all()
        
        # Filtrage par distance si coordonnées fournies
        filtered_providers = []
        if latitude and longitude:
            for provider in all_providers:
                if provider.latitude and provider.longitude:
                    distance = SearchService.haversine_distance(
                        latitude, longitude, 
                        provider.latitude, provider.longitude
                    )
                    if distance <= radius_km:
                        # Ajouter la distance calculée au provider
                        provider.distance_km = round(distance, 2)
                        filtered_providers.append(provider)
        else:
            # Pas de filtre distance
            filtered_providers = all_providers
            for provider in filtered_providers:
                provider.distance_km = None
        
        # Tri des résultats
        if sort_by == "distance" and latitude and longitude:
            filtered_providers.sort(key=lambda x: x.distance_km if x.distance_km else float('inf'))
        elif sort_by == "rating":
            filtered_providers.sort(key=lambda x: x.average_rating or 0, reverse=True)
        elif sort_by == "price":
            filtered_providers.sort(key=lambda x: x.daily_rate or float('inf'))
        else:  # relevance (défaut)
            # Tri par pertinence : note + nombre d'avis + sponsoring
            def relevance_score(provider):
                score = 0
                if provider.average_rating:
                    score += provider.average_rating * 2
                if provider.reviews_count:
                    score += min(provider.reviews_count * 0.1, 2)  # Max 2 points pour les avis
                if provider.is_sponsored:
                    score += 5  # Boost pour les sponsorisés
                return score
            
            filtered_providers.sort(key=relevance_score, reverse=True)
        
        # Pagination
        total = len(filtered_providers)
        paginated_providers = filtered_providers[offset:offset + limit]
        
        return {
            "providers": paginated_providers,
            "total": total,
            "page": offset // limit + 1,
            "pages": math.ceil(total / limit) if total > 0 else 0,
            "has_next": offset + limit < total,
            "search_params": {
                "query": query,
                "category": category,
                "city": city,
                "commune": commune,
                "latitude": latitude,
                "longitude": longitude,
                "radius_km": radius_km,
                "sort_by": sort_by
            }
        }

    @staticmethod
    def get_suggestions(
        db: Session, 
        query: str, 
        limit: int = 5
    ) -> Dict[str, List[str]]:
        """
        Suggestions d'autocomplétion pour la recherche
        """
        if not query or len(query) < 2:
            return {"categories": [], "providers": [], "cities": []}
        
        search_term = f"%{query.lower()}%"
        
        # Suggestions de catégories
        categories = db.query(User.business_category).filter(
            and_(
                func.lower(User.business_category).like(search_term),
                User.is_active == True,
                User.subscription_status == "active"
            )
        ).distinct().limit(limit).all()
        
        # Suggestions de prestataires
        providers = db.query(User.first_name, User.last_name).filter(
            and_(
                or_(
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term)
                ),
                User.is_active == True,
                User.subscription_status == "active"
            )
        ).limit(limit).all()
        
        # Suggestions de villes
        cities = db.query(User.city).filter(
            and_(
                func.lower(User.city).like(search_term),
                User.is_active == True,
                User.subscription_status == "active"
            )
        ).distinct().limit(limit).all()
        
        return {
            "categories": [cat[0] for cat in categories if cat[0]],
            "providers": [f"{p[0]} {p[1]}" for p in providers if p[0] and p[1]],
            "cities": [city[0] for city in cities if city[0]]
        }

    @staticmethod
    def get_nearby_providers(
        db: Session,
        latitude: float,
        longitude: float,
        radius_km: int = 3,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[User]:
        """
        Trouver les prestataires les plus proches
        """
        query = db.query(User).join(Subscription).filter(
            and_(
                User.is_active == True,
                User.subscription_status == "active",
                User.latitude.isnot(None),
                User.longitude.isnot(None),
                Subscription.is_active == True,
                Subscription.end_date > func.now()
            )
        )
        
        if category:
            query = query.filter(
                func.lower(User.business_category) == category.lower()
            )
        
        providers = query.all()
        
        # Calcul de distance et filtrage
        nearby_providers = []
        for provider in providers:
            distance = SearchService.haversine_distance(
                latitude, longitude,
                provider.latitude, provider.longitude
            )
            if distance <= radius_km:
                provider.distance_km = round(distance, 2)
                nearby_providers.append(provider)
        
        # Tri par distance
        nearby_providers.sort(key=lambda x: x.distance_km)
        
        return nearby_providers[:limit]

    @staticmethod
    def get_popular_categories(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Catégories les plus populaires avec nombre de prestataires
        """
        categories = db.query(
            User.business_category,
            func.count(User.id).label('count')
        ).join(Subscription).filter(
            and_(
                User.is_active == True,
                User.subscription_status == "active",
                User.business_category.isnot(None),
                Subscription.is_active == True,
                Subscription.end_date > func.now()
            )
        ).group_by(User.business_category).order_by(
            func.count(User.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "name": cat[0],
                "count": cat[1],
                "slug": cat[0].lower().replace(' ', '-') if cat[0] else ""
            }
            for cat in categories
        ]

    @staticmethod
    def get_search_stats(db: Session) -> Dict[str, int]:
        """
        Statistiques globales de recherche
        """
        total_active = db.query(User).join(Subscription).filter(
            and_(
                User.is_active == True,
                User.subscription_status == "active",
                Subscription.is_active == True,
                Subscription.end_date > func.now()
            )
        ).count()
        
        total_categories = db.query(User.business_category).filter(
            and_(
                User.is_active == True,
                User.subscription_status == "active",
                User.business_category.isnot(None)
            )
        ).distinct().count()
        
        total_cities = db.query(User.city).filter(
            and_(
                User.is_active == True,
                User.subscription_status == "active",
                User.city.isnot(None)
            )
        ).distinct().count()
        
        return {
            "total_providers": total_active,
            "total_categories": total_categories,
            "total_cities": total_cities
        }