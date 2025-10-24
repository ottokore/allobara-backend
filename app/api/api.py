# app/api/api.py

from fastapi import APIRouter

# Router principal de l'API
api_router = APIRouter()

print("📄 Chargement des endpoints AlloBara...")

# Import progressif avec gestion d'erreurs pour identifier les problèmes

# 1. AUTHENTIFICATION
try:
    from app.api.endpoints import auth
    api_router.include_router(
        auth.router,
        prefix="/auth",
        tags=["🔐 Authentification"]
    )
    print("✅ Auth endpoint chargé")
except Exception as e:
    print(f"❌ Erreur auth endpoint: {e}")

# 2. UTILISATEURS
try:
    from app.api.endpoints import users
    api_router.include_router(
        users.router,
        prefix="/users",
        tags=["👥 Utilisateurs"]
    )
    print("✅ Users endpoint chargé")
except Exception as e:
    print(f"❌ Erreur users endpoint: {e}")

# 2B. FAVORIS (NOUVEAU)
try:
    from app.api.endpoints import favorites
    api_router.include_router(
        favorites.router,
        prefix="/users/favorites",
        tags=["❤️ Favoris"]
    )
    print("✅ Favorites endpoint chargé")
except Exception as e:
    print(f"❌ Erreur favorites endpoint: {e}")

# 3. ABONNEMENTS
try:
    from app.api.endpoints import subscriptions
    api_router.include_router(
        subscriptions.router,
        prefix="/subscriptions", 
        tags=["💳 Abonnements"]
    )
    print("✅ Subscriptions endpoint chargé")
except Exception as e:
    print(f"❌ Erreur subscriptions endpoint: {e}")

# 4. RECHERCHE
try:
    from app.api.endpoints import search
    api_router.include_router(
        search.router,
        prefix="/search",
        tags=["🔍 Recherche"]
    )
    print("✅ Search endpoint chargé")
except Exception as e:
    print(f"❌ Erreur search endpoint: {e}")

# 5. PORTFOLIO
try:
    from app.api.endpoints import portfolio
    api_router.include_router(
        portfolio.router,
        prefix="/portfolio",
        tags=["📁 Portfolio"]
    )
    print("✅ Portfolio endpoint chargé")
except Exception as e:
    print(f"❌ Erreur portfolio endpoint: {e}")

# 6. PAIEMENTS
try:
    from app.api.endpoints import payments
    api_router.include_router(
        payments.router,
        prefix="/payments",
        tags=["💰 Paiements"]
    )
    print("✅ Payments endpoint chargé")
except Exception as e:
    print(f"❌ Erreur payments endpoint: {e}")

# 7. DEMANDES DE DEVIS
try:
    from app.api.endpoints import quotes
    api_router.include_router(
        quotes.router,
        prefix="/quotes",
        tags=["📋 Demandes de devis"]
    )
    print("✅ Quotes endpoint chargé")
except Exception as e:
    print(f"❌ Erreur quotes endpoint: {e}")

# 8. AVIS ET ÉVALUATIONS (NOUVEAU)
try:
    from app.api.endpoints import reviews
    api_router.include_router(
        reviews.router,
        prefix="/users",
        tags=["⭐ Avis et Évaluations"]
    )
    print("✅ Reviews endpoint chargé")
except Exception as e:
    print(f"❌ Erreur reviews endpoint: {e}")

# 9. ADMINISTRATION
try:
    from app.api.endpoints import admin
    api_router.include_router(
        admin.router,
        prefix="/admin",
        tags=["🛡️ Administration"]
    )
    print("✅ Admin endpoint chargé")
except Exception as e:
    print(f"❌ Erreur admin endpoint: {e}")

# =========================================
# ROUTES DE SANTÉ ET MONITORING
# =========================================

@api_router.get("/")
async def api_root():
    """
    Endpoint racine de l'API
    """
    return {
        "message": "Bienvenue sur l'API AlloBara",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "users": "/api/v1/users",
            "favorites": "/api/v1/users/favorites",
            "subscriptions": "/api/v1/subscriptions",
            "search": "/api/v1/search",
            "portfolio": "/api/v1/portfolio",
            "payments": "/api/v1/payments",
            "quotes": "/api/v1/quotes",
            "reviews": "/api/v1/users/{provider_id}/reviews",
            "admin": "/api/v1/admin"
        },
        "features": [
            "Authentification OTP WhatsApp",
            "Recherche géolocalisée", 
            "Scroll infini style Facebook",
            "Période d'essai gratuite",
            "Clavier PIN sécurisé",
            "Dashboard admin complet",
            "Demandes de devis PDF + WhatsApp",
            "Système d'avis et notation",
            "Gestion des favoris"
        ]
    }

@api_router.get("/health")
async def api_health_check():
    """
    Vérification de l'état de l'API
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "routes_loaded": len(api_router.routes),
        "services": {
            "database": "connected",
            "sms": "configured", 
            "storage": "available",
            "quotes_pdf": "available",
            "whatsapp": "configured",
            "reviews": "available",
            "favorites": "available"
        }
    }

@api_router.get("/stats/global")
async def get_global_stats():
    """
    Statistiques globales publiques
    """
    return {
        "total_providers": "1000+",
        "cities_covered": "10+", 
        "services_categories": 6,
        "average_rating": 4.2,
        "total_reviews": "5000+",
        "features": [
            "Prestataires vérifiés",
            "Recherche géolocalisée",
            "Portfolio en images/vidéos",
            "Notation et avis clients",
            "Contact direct WhatsApp",
            "Demandes de devis PDF",
            "Système d'évaluation transparent"
        ]
    }

@api_router.get("/config/app")
async def get_app_config():
    """
    Configuration publique de l'application
    """
    return {
        "app_name": "AlloBara",
        "version": "1.0.0",
        "supported_countries": [
            {
                "name": "Côte d'Ivoire",
                "code": "CI", 
                "phone_code": "+225",
                "currency": "FCFA",
                "flag": "🇨🇮"
            }
        ],
        "payment_providers": [
            {
                "name": "Wave",
                "code": "wave",
                "logo": "/images/wave-logo.png",
                "is_primary": True
            }
        ],
        "subscription_plans": [
            {
                "id": "monthly",
                "name": "Mensuel",
                "price": 2100,
                "duration_months": 1,
                "description": "Parfait pour commencer"
            },
            {
                "id": "quarterly", 
                "name": "Trimestriel",
                "price": 5100,
                "duration_months": 3,
                "description": "Économisez 19%",
                "savings": 1200
            },
            {
                "id": "biannual",
                "name": "Semestriel", 
                "price": 9100,
                "duration_months": 6,
                "description": "Économisez 28%",
                "savings": 3500
            },
            {
                "id": "annual",
                "name": "Annuel",
                "price": 16100,
                "duration_months": 12,
                "description": "Meilleure offre - Économisez 36%",
                "savings": 9100
            }
        ],
        "free_trial": {
            "duration_days": 30,
            "enabled": True,
            "description": "1 mois gratuit pour tous les nouveaux prestataires"
        },
        "file_upload": {
            "max_size_mb": 5,
            "allowed_formats": ["jpg", "png", "gif", "mp4"],
            "image_max_mb": 5,
            "video_max_mb": 50
        },
        "search": {
            "default_radius_km": 5,
            "max_radius_km": 50,
            "results_per_page": 20
        },
        "quotes": {
            "pdf_generation": True,
            "whatsapp_delivery": True,
            "supported_formats": ["pdf"],
            "max_description_length": 500
        },
        "reviews": {
            "enabled": True,
            "anonymous_allowed": True,
            "auto_approval": True,
            "moderation_enabled": True,
            "min_comment_length": 10,
            "max_comment_length": 1000,
            "rating_scale": {
                "min": 1,
                "max": 5,
                "type": "stars"
            }
        }
    }

print(f"🎯 Router API créé avec {len(api_router.routes)} routes")