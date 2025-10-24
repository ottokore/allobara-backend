"""
AlloBara Backend - Point d'entrée principal
Serveur FastAPI pour la plateforme de prestataires de services
"""

import os
import sys
import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

# Configuration du logging avant les imports locaux
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Imports locaux avec gestion d'erreurs
try:
    from app.core.config import settings, validate_config
    from app.db.database import init_database, check_database_connection
    from app.api.api import api_router  # AJOUT IMPORTANT
    logger.info("✅ Imports réussis")
except ImportError as e:
    logger.error(f"❌ Erreur d'import: {e}")
    # Créer des objets par défaut pour éviter les crashs
    class MockSettings:
        APP_NAME = "AlloBara"
        APP_VERSION = "1.0.0"
        DEBUG = True
        ENVIRONMENT = "development"
    
    settings = MockSettings()
    def validate_config(): pass
    def init_database(): pass  
    def check_database_connection(): return True
    # Router vide par défaut
    from fastapi import APIRouter
    api_router = APIRouter()

# =========================================
# GESTIONNAIRE DE CONTEXTE D'APPLICATION
# =========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    # DÉMARRAGE
    logger.info("🚀 Démarrage d'AlloBara Backend...")
    
    try:
        # Validation de la configuration
        validate_config()
        logger.info("✅ Configuration validée")
        
        # Initialisation de la base de données
        init_database()
        logger.info("✅ Base de données initialisée")
        
        # 🆕 Initialisation des paramètres système par défaut
        try:
            from app.db.database import SessionLocal
            from app.models.system_settings import SystemSettings
            
            db = SessionLocal()
            SystemSettings.initialize_default_settings(db)
            db.close()
            logger.info("✅ Paramètres système initialisés")
        except Exception as e:
            logger.warning(f"⚠️ Erreur initialisation paramètres: {e}")
        
        # Création des dossiers nécessaires
        os.makedirs("uploads/profile_pictures", exist_ok=True)
        os.makedirs("uploads/cover_pictures", exist_ok=True)
        os.makedirs("uploads/id_documents", exist_ok=True)
        os.makedirs("uploads/portfolio", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        logger.info("✅ Dossiers de stockage créés")
        
        logger.info("🎉 AlloBara Backend démarré avec succès !")
        logger.info(f"📍 Environnement: {settings.ENVIRONMENT}")
        logger.info(f"🔧 Mode debug: {settings.DEBUG}")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du démarrage: {e}")
        # Ne pas arrêter le serveur, continuer avec les valeurs par défaut
    
    yield
    
    # ARRÊT
    logger.info("🛑 Arrêt d'AlloBara Backend...")

# =========================================
# CRÉATION DE L'APPLICATION FASTAPI
# =========================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    🛠️ **AlloBara Backend API**
    
    Plateforme de mise en relation des prestataires de services informels en Côte d'Ivoire.
    
    ## Fonctionnalités principales
    
    * **🔐 Authentification** - Inscription et connexion sécurisées par téléphone + PIN
    * **👤 Profils complets** - Informations personnelles, professionnelles et géolocalisation  
    * **💳 Abonnements** - Période d'essai gratuite + plans flexibles avec paiement CinetPay
    * **📸 Portfolio** - Images et vidéos des réalisations avec compression automatique
    * **⭐ Avis clients** - Système de notation et commentaires
    * **📱 Notifications** - Multi-canaux (SMS, WhatsApp, Push)
    * **👨‍💼 Interface admin** - Dashboard, wallet, statistiques complètes
    * **🛡️ Anti-fraude** - Détection automatique des abus de période d'essai
    
    ## Nouveautés v2.0
    
    * **Nouveaux prix** : Mensuel 2100 FCFA, Semestriel 9100 FCFA, Annuel 16100 FCFA
    * **CinetPay** : Paiement mobile intégré (Orange Money, MTN, Moov, Wave)
    * **Anti-fraude** : Détection automatique des comptes multiples
    * **Paramètres** : Toggle admin pour activer/désactiver la période d'essai
    * **Géolocalisation** : Recherche dans un rayon de 5km par défaut
    * **Période d'essai** : 30 jours gratuits pour tous les nouveaux prestataires
    """,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

# =========================================
# MIDDLEWARE
# =========================================

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [
        "https://allobara.ci",
        "https://admin.allobara.ci"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Middleware de logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logger toutes les requêtes HTTP avec temps de réponse"""
    start_time = time.time()
    
    client_ip = request.client.host if request.client else "unknown"
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    log_message = (
        f"{client_ip} - "
        f'"{request.method} {request.url.path}" '
        f"{response.status_code} - "
        f"{process_time:.3f}s"
    )
    
    if response.status_code >= 400:
        logger.warning(log_message)
    else:
        logger.info(log_message)
    
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-API-Version"] = settings.APP_VERSION
    
    return response

# =========================================
# ROUTES STATIQUES
# =========================================

# Servir les fichiers uploadés
if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    logger.info("✅ Dossier uploads monté sur /uploads")

# =========================================
# INCLUSION DU ROUTER PRINCIPAL API
# =========================================

# Inclure tous les endpoints API sous /api/v1
app.include_router(api_router, prefix="/api/v1")
logger.info("✅ Routes API inclues sous /api/v1")

# =========================================
# ROUTES DE BASE
# =========================================

@app.get("/", tags=["Root"])
async def root():
    """🏠 Page d'accueil de l'API AlloBara"""
    return {
        "message": "Bienvenue sur l'API AlloBara ! 🛠️",
        "description": "Plateforme de mise en relation des prestataires de services informels",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "health": "/health",
            "info": "/info",
            "api": "/api/v1"
        },
        "features": [
            "🔐 Authentification sécurisée par téléphone",
            "👤 Profils de prestataires complets", 
            "💳 Système d'abonnement avec essai gratuit",
            "💳 Paiements CinetPay (Orange Money, MTN, Moov, Wave)",
            "🛡️ Détection anti-fraude automatique",
            "📸 Portfolio avec compression d'images",
            "⭐ Système d'avis et de notation",
            "📱 Notifications multi-canaux",
            "👨‍💼 Interface d'administration avancée"
        ]
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """🏥 Point de santé de l'API"""
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {}
    }
    
    # Vérification de la base de données
    try:
        db_healthy = check_database_connection()
        health_status["services"]["database"] = "healthy" if db_healthy else "unhealthy"
    except Exception as e:
        health_status["services"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Services futurs
    health_status["services"]["redis"] = "not_implemented"
    health_status["services"]["celery"] = "not_implemented"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return JSONResponse(content=health_status, status_code=status_code)

@app.get("/info", tags=["Info"])
async def app_info():
    """ℹ️ Informations détaillées sur l'application"""
    try:
        pricing = {
            "monthly": f"{settings.PRICE_MONTHLY} FCFA",
            "quarterly": f"{settings.PRICE_QUARTERLY} FCFA", 
            "biannual": f"{settings.PRICE_BIANNUAL} FCFA",
            "annual": f"{settings.PRICE_ANNUAL} FCFA"
        }
        features = {
            "free_trial_days": settings.FREE_TRIAL_DAYS,
            "search_radius_km": settings.DEFAULT_SEARCH_RADIUS_KM,
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "allowed_extensions": settings.ALLOWED_EXTENSIONS.split(","),
            "payment_providers": ["wave", "cinetpay"],  # 🆕
            "anti_fraud": "enabled"  # 🆕
        }
        contact = {
            "admin_phone": settings.ADMIN_PHONE
        }
    except AttributeError:
        # Fallback si les paramètres ne sont pas chargés
        pricing = {"monthly": "2100 FCFA", "annual": "16100 FCFA"}
        features = {"free_trial_days": 30}
        contact = {"admin_phone": "+225XXXXXXXX"}
    
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "pricing": pricing,
        "features": features,
        "contact": contact
    }

# =========================================
# DOCUMENTATION PERSONNALISÉE
# =========================================

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Documentation Swagger personnalisée"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.APP_NAME} - Documentation API"
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Documentation ReDoc personnalisée"""
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{settings.APP_NAME} - Documentation API"
    )

# =========================================
# GESTIONNAIRES D'ERREURS
# =========================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Gestionnaire pour les erreurs 404"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Ressource non trouvée",
            "message": "L'endpoint demandé n'existe pas",
            "path": str(request.url.path),
            "suggestion": "Consultez la documentation sur /docs"
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    """Gestionnaire pour les erreurs internes"""
    logger.error(f"Erreur interne: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erreur interne du serveur",
            "message": "Une erreur inattendue s'est produite",
            "details": str(exc) if settings.DEBUG else None
        }
    )

# =========================================
# FONCTION PRINCIPALE
# =========================================

def main():
    """Fonction principale pour démarrer le serveur"""
    import uvicorn
    
    logger.info(f"🚀 Démarrage du serveur AlloBara sur http://0.0.0.0:8000")
    logger.info(f"📚 Documentation disponible sur http://0.0.0.0:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )

if __name__ == "__main__":
    main()