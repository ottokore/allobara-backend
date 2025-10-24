"""
Endpoints de recherche AlloBara
Recherche globale, suggestions, filtres avancés
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.user import UserService
from app.schemas.user import SearchFilters, UserSearchResponse
from app.api.deps.auth import get_optional_user
from app.models.user import User

# Router pour les endpoints de recherche
router = APIRouter()

# =========================================
# RECHERCHE PRINCIPALE
# =========================================

@router.get("/", response_model=UserSearchResponse)
async def global_search(
    q: str = Query(..., min_length=2, max_length=100, description="Terme de recherche"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    domain: Optional[str] = Query(None, description="Domaine d'activité"),
    country: Optional[str] = Query(None, description="Pays"),  # ✅ AJOUTÉ
    city: Optional[str] = Query(None, description="Ville"),
    commune: Optional[str] = Query(None, description="Commune"),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_distance: Optional[int] = Query(None, ge=1, le=50, description="Distance max en km"),
    verified_only: bool = Query(False),
    user_lat: Optional[float] = Query(None, ge=-90, le=90),
    user_lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db)
):
    """
    Recherche globale dans tous les prestataires
    """
    user_service = UserService(db)
    
    # Construire les filtres
    filters = SearchFilters(
        query=q,
        domain=domain,
        country=country,  # ✅ AJOUTÉ
        city=city,
        commune=commune,
        min_rating=min_rating,
        max_distance_km=max_distance,
        verified_only=verified_only,
        user_latitude=user_lat,
        user_longitude=user_lng
    )
    
    result = user_service.search_providers(filters, page, limit)
    return UserSearchResponse(**result)

@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1, max_length=50, description="Début du terme"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Auto-suggestions pour la recherche
    """
    try:
        from sqlalchemy import func, distinct
        
        suggestions = []
        search_term = f"{q.lower()}%"
        
        # Suggestions de professions
        professions = db.query(distinct(User.profession)).filter(
            and_(
                func.lower(User.profession).like(search_term),
                User.profession.isnot(None),
                User.is_active == True
            )
        ).limit(5).all()
        
        for profession in professions:
            if profession[0]:
                suggestions.append({
                    "text": profession[0],
                    "type": "profession",
                    "icon": "🔧"
                })
        
        # Suggestions de villes
        cities = db.query(distinct(User.city)).filter(
            and_(
                func.lower(User.city).like(search_term),
                User.city.isnot(None),
                User.is_active == True
            )
        ).limit(3).all()
        
        for city in cities:
            if city[0]:
                suggestions.append({
                    "text": city[0],
                    "type": "city", 
                    "icon": "📍"
                })
        
        # Suggestions de noms (si assez long)
        if len(q) >= 3:
            names = db.query(
                User.first_name,
                User.last_name,
                User.profession
            ).filter(
                and_(
                    or_(
                        func.lower(User.first_name).like(search_term),
                        func.lower(User.last_name).like(search_term)
                    ),
                    User.is_active == True,
                    User.is_verified == True
                )
            ).limit(3).all()
            
            for name_data in names:
                if name_data[0] or name_data[1]:
                    full_name = f"{name_data[0] or ''} {name_data[1] or ''}".strip()
                    profession = name_data[2] or "Prestataire"
                    suggestions.append({
                        "text": full_name,
                        "type": "provider",
                        "icon": "👤",
                        "subtitle": profession
                    })
        
        # Limiter le total
        suggestions = suggestions[:limit]
        
        return {
            "suggestions": suggestions,
            "count": len(suggestions),
            "query": q
        }
        
    except Exception as e:
        print(f"Erreur get_search_suggestions: {e}")
        return {"suggestions": [], "count": 0, "query": q}

@router.get("/trending")
async def get_trending_searches(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Recherches tendance et populaires
    """
    try:
        # Pour l'instant, retourner des suggestions statiques
        # Plus tard, on pourra tracker les recherches réelles
        trending = [
            {"term": "Plombier", "category": "Bâtiment", "count": 245},
            {"term": "Électricien", "category": "Bâtiment", "count": 189},
            {"term": "Femme de ménage", "category": "Ménage", "count": 156},
            {"term": "Maçon", "category": "Bâtiment", "count": 134},
            {"term": "Peintre", "category": "Bâtiment", "count": 112},
            {"term": "Chauffeur", "category": "Transport", "count": 98},
            {"term": "Cuisinier", "category": "Restauration", "count": 87},
            {"term": "Coiffeur", "category": "Beauté", "count": 76},
            {"term": "Jardinier", "category": "Ménage", "count": 65},
            {"term": "Soudeur", "category": "Bâtiment", "count": 54}
        ]
        
        return {
            "trending": trending[:limit],
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Erreur get_trending_searches: {e}")
        return {"trending": [], "updated_at": None}

@router.get("/categories/{domain}")
async def search_by_category(
    domain: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    city: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    user_lat: Optional[float] = Query(None, ge=-90, le=90),
    user_lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db)
):
    """
    Recherche par catégorie de service
    """
    user_service = UserService(db)
    
    # Valider le domaine
    valid_domains = ["batiment", "menage", "transport", "restauration", "beaute", "autres"]
    if domain not in valid_domains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domaine invalide. Domaines valides: {', '.join(valid_domains)}"
        )
    
    filters = SearchFilters(
        domain=domain,
        city=city,
        min_rating=min_rating,
        user_latitude=user_lat,
        user_longitude=user_lng
    )
    
    result = user_service.search_providers(filters, page, limit)
    
    # Ajouter des infos sur la catégorie
    category_info = {
        "batiment": {"name": "Bâtiment et BTP", "icon": "🔧"},
        "menage": {"name": "Ménage et Domestique", "icon": "🧹"},
        "transport": {"name": "Transport", "icon": "🚗"},
        "restauration": {"name": "Restauration", "icon": "🍽️"},
        "beaute": {"name": "Beauté et Bien-être", "icon": "💇🏾"},
        "autres": {"name": "Autres Services", "icon": "🛠️"}
    }
    
    result["category"] = category_info.get(domain, {"name": domain, "icon": "⚙️"})
    
    return result

@router.get("/cities/{city}")
async def search_by_city(
    city: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    domain: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    db: Session = Depends(get_db)
):
    """
    Recherche par ville
    """
    user_service = UserService(db)
    
    filters = SearchFilters(
        city=city,
        domain=domain,
        min_rating=min_rating
    )
    
    result = user_service.search_providers(filters, page, limit)
    result["city"] = city
    
    return result

@router.get("/nearby")
async def search_nearby(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius: int = Query(5, ge=1, le=50, description="Rayon en km"),
    domain: Optional[str] = Query(None),
    profession: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Recherche géolocalisée dans un rayon spécifique
    """
    user_service = UserService(db)
    
    filters = SearchFilters(
        domain=domain,
        query=profession,
        user_latitude=lat,
        user_longitude=lng,
        max_distance_km=radius
    )
    
    result = user_service.search_providers(filters, 1, limit)
    
    # Ajouter les infos de géolocalisation
    result["search_center"] = {"latitude": lat, "longitude": lng}
    result["radius_km"] = radius
    
    return result

@router.get("/filters/options")
async def get_filter_options(
    db: Session = Depends(get_db)
):
    """
    Options disponibles pour les filtres de recherche
    """
    try:
        from sqlalchemy import func, distinct
        
        # Récupérer les villes disponibles
        cities = db.query(distinct(User.city)).filter(
            and_(
                User.city.isnot(None),
                User.is_active == True
            )
        ).order_by(User.city).all()
        
        # Récupérer les communes par ville
        communes_by_city = {}
        for city_row in cities:
            city = city_row[0]
            communes = db.query(distinct(User.commune)).filter(
                and_(
                    User.city == city,
                    User.commune.isnot(None),
                    User.is_active == True
                )
            ).order_by(User.commune).all()
            
            communes_by_city[city] = [c[0] for c in communes if c[0]]
        
        # Récupérer les professions par domaine
        professions_by_domain = {}
        domains = ["batiment", "menage", "transport", "restauration", "beaute", "autres"]
        
        for domain in domains:
            professions = db.query(distinct(User.profession)).filter(
                and_(
                    User.domain == domain,
                    User.profession.isnot(None),
                    User.is_active == True
                )
            ).order_by(User.profession).all()
            
            professions_by_domain[domain] = [p[0] for p in professions if p[0]]
        
        # Plages de prix
        price_ranges = [
            {"label": "Moins de 5,000 FCFA", "min": 0, "max": 5000},
            {"label": "5,000 - 10,000 FCFA", "min": 5000, "max": 10000},
            {"label": "10,000 - 20,000 FCFA", "min": 10000, "max": 20000},
            {"label": "20,000 - 50,000 FCFA", "min": 20000, "max": 50000},
            {"label": "Plus de 50,000 FCFA", "min": 50000, "max": None}
        ]
        
        return {
            "cities": [c[0] for c in cities if c[0]],
            "communes_by_city": communes_by_city,
            "professions_by_domain": professions_by_domain,
            "domains": [
                {"id": "batiment", "name": "Bâtiment et BTP", "icon": "🔧"},
                {"id": "menage", "name": "Ménage et Domestique", "icon": "🧹"},
                {"id": "transport", "name": "Transport", "icon": "🚗"},
                {"id": "restauration", "name": "Restauration", "icon": "🍽️"},
                {"id": "beaute", "name": "Beauté et Bien-être", "icon": "💇🏾"},
                {"id": "autres", "name": "Autres Services", "icon": "🛠️"}
            ],
            "price_ranges": price_ranges,
            "rating_options": [
                {"label": "4+ étoiles", "value": 4.0},
                {"label": "3+ étoiles", "value": 3.0}, 
                {"label": "2+ étoiles", "value": 2.0},
                {"label": "Toutes les notes", "value": 0.0}
            ],
            "distance_options": [
                {"label": "1 km", "value": 1},
                {"label": "3 km", "value": 3},
                {"label": "5 km", "value": 5},
                {"label": "10 km", "value": 10},
                {"label": "20 km", "value": 20},
                {"label": "50 km", "value": 50}
            ]
        }
        
    except Exception as e:
        print(f"Erreur get_filter_options: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des options"
        )

@router.get("/autocomplete")
async def search_autocomplete(
    q: str = Query(..., min_length=1, max_length=50),
    type: str = Query("all", description="all, profession, city, provider"),
    limit: int = Query(8, ge=1, le=15),
    db: Session = Depends(get_db)
):
    """
    Auto-complétion pour la barre de recherche
    """
    try:
        from sqlalchemy import func, distinct
        
        results = []
        search_term = f"%{q.lower()}%"
        
        if type in ["all", "profession"]:
            # Recherche dans les professions
            professions = db.query(
                distinct(User.profession),
                func.count(User.id).label('count')
            ).filter(
                and_(
                    func.lower(User.profession).like(search_term),
                    User.profession.isnot(None),
                    User.is_active == True
                )
            ).group_by(User.profession).order_by(
                func.count(User.id).desc()
            ).limit(limit // 2).all()
            
            for profession, count in professions:
                results.append({
                    "text": profession,
                    "type": "profession",
                    "count": count,
                    "icon": "🔧"
                })
        
        if type in ["all", "city"]:
            # Recherche dans les villes
            cities = db.query(
                distinct(User.city),
                func.count(User.id).label('count')
            ).filter(
                and_(
                    func.lower(User.city).like(search_term),
                    User.city.isnot(None),
                    User.is_active == True
                )
            ).group_by(User.city).order_by(
                func.count(User.id).desc()
            ).limit(limit // 2).all()
            
            for city, count in cities:
                results.append({
                    "text": city,
                    "type": "city",
                    "count": count,
                    "icon": "📍"
                })
        
        if type in ["all", "provider"] and len(q) >= 3:
            # Recherche dans les noms de prestataires
            providers = db.query(User).filter(
                and_(
                    or_(
                        func.lower(User.first_name).like(search_term),
                        func.lower(User.last_name).like(search_term)
                    ),
                    User.is_active == True,
                    User.is_verified == True
                )
            ).order_by(
                User.rating_average.desc()
            ).limit(3).all()
            
            for provider in providers:
                results.append({
                    "text": provider.full_name,
                    "type": "provider",
                    "id": provider.id,
                    "profession": provider.profession,
                    "city": provider.city,
                    "rating": provider.rating_average,
                    "icon": "👤"
                })
        
        # Trier par pertinence (type profession d'abord, puis par count)
        results.sort(key=lambda x: (
            0 if x["type"] == "profession" else 1 if x["type"] == "city" else 2,
            -x.get("count", 0)
        ))
        
        return {
            "results": results[:limit],
            "total": len(results),
            "query": q
        }
        
    except Exception as e:
        print(f"Erreur search_autocomplete: {e}")
        return {"results": [], "total": 0, "query": q}

@router.get("/popular")
async def get_popular_providers(
    domain: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Prestataires populaires (les mieux notés avec le plus d'avis)
    """
    try:
        from sqlalchemy import desc
        
        query = db.query(User).filter(
            and_(
                User.is_active == True,
                User.is_verified == True,
                User.rating_count >= 3,  # Au moins 3 avis
                User.rating_average >= 4.0  # Note minimum 4/5
            )
        )
        
        if domain:
            query = query.filter(User.domain == domain)
        
        if city:
            query = query.filter(User.city == city)
        
        # Trier par score de popularité (note * nombre d'avis)
        popular_providers = query.order_by(
            desc(User.rating_average * User.rating_count),
            desc(User.profile_views)
        ).limit(limit).all()
        
        results = []
        for provider in popular_providers:
            results.append({
                "id": provider.id,
                "full_name": provider.full_name,
                "profession": provider.profession,
                "city": provider.city,
                "commune": provider.commune,
                "rating_average": provider.rating_average,
                "rating_count": provider.rating_count,
                "profile_picture": provider.profile_picture,
                "popularity_score": round(provider.rating_average * provider.rating_count, 1),
                "profile_views": provider.profile_views
            })
        
        return {
            "popular_providers": results,
            "total": len(results),
            "filters": {"domain": domain, "city": city}
        }
        
    except Exception as e:
        print(f"Erreur get_popular_providers: {e}")
        return {"popular_providers": [], "total": 0}

@router.get("/recent")
async def get_recent_providers(
    days: int = Query(7, ge=1, le=30, description="Jours depuis inscription"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Nouveaux prestataires récemment inscrits
    """
    try:
        from datetime import datetime, timedelta
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        recent_providers = db.query(User).filter(
            and_(
                User.created_at >= since_date,
                User.is_active == True,
                User.is_profile_complete == True
            )
        ).order_by(
            User.created_at.desc()
        ).limit(limit).all()
        
        results = []
        for provider in recent_providers:
            days_since = (datetime.utcnow() - provider.created_at).days
            results.append({
                "id": provider.id,
                "full_name": provider.full_name,
                "profession": provider.profession,
                "city": provider.city,
                "domain": provider.domain,
                "profile_picture": provider.profile_picture,
                "created_at": provider.created_at.isoformat(),
                "days_since_creation": days_since,
                "is_new": days_since <= 3
            })
        
        return {
            "recent_providers": results,
            "total": len(results),
            "period_days": days
        }
        
    except Exception as e:
        print(f"Erreur get_recent_providers: {e}")
        return {"recent_providers": [], "total": 0}

@router.get("/stats")
async def get_search_stats(
    db: Session = Depends(get_db)
):
    """
    Statistiques générales de recherche
    """
    try:
        from sqlalchemy import func
        
        # Compter par domaine
        domain_stats = db.query(
            User.domain,
            func.count(User.id).label('count')
        ).filter(
            User.is_active == True
        ).group_by(User.domain).all()
        
        # Compter par ville
        city_stats = db.query(
            User.city,
            func.count(User.id).label('count')
        ).filter(
            and_(
                User.city.isnot(None),
                User.is_active == True
            )
        ).group_by(User.city).order_by(
            func.count(User.id).desc()
        ).limit(10).all()
        
        # Statistiques générales
        total_providers = db.query(User).filter(User.is_active == True).count()
        verified_providers = db.query(User).filter(
            and_(User.is_active == True, User.is_verified == True)
        ).count()
        
        return {
            "total_providers": total_providers,
            "verified_providers": verified_providers,
            "verification_rate": round(verified_providers / total_providers * 100, 1) if total_providers > 0 else 0,
            "by_domain": {domain: count for domain, count in domain_stats if domain},
            "top_cities": [{"city": city, "count": count} for city, count in city_stats if city],
            "average_rating": 4.2,  # À calculer dynamiquement plus tard
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"Erreur get_search_stats: {e}")
        return {"error": "Erreur lors du calcul des statistiques"}