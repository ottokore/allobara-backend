"""
Configuration globale d'AlloBara
Gestion des variables d'environnement et paramètres
"""

from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class Settings(BaseSettings):
    """Configuration principale de l'application AlloBara"""
    
    # =========================================
    # APPLICATION
    # =========================================
    APP_NAME: str = "AlloBara"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    DEMO_MODE: bool = True  # AJOUT POUR LES TESTS SMS
    
    # =========================================
    # BASE DE DONNÉES
    # =========================================
    DATABASE_URL: str = "postgresql://allobara_user:Gnahore2025@localhost:5432/allobara_db"            
    
    # =========================================
    # JWT ET SÉCURITÉ
    # =========================================
    SECRET_KEY: str = "allobara-super-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # =========================================
    # SMS/WHATSAPP (TWILIO)
    # =========================================
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    TWILIO_WHATSAPP_NUMBER: Optional[str] = None  # AJOUT MANQUANT
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"
    
    # =========================================
    # PAIEMENTS WAVE
    # =========================================
    WAVE_API_KEY: Optional[str] = None
    WAVE_API_SECRET: Optional[str] = None
    WAVE_WEBHOOK_SECRET: Optional[str] = None

    # =========================================
    # PAIEMENTS CINETPAY
    # =========================================
    CINETPAY_API_KEY: Optional[str] = None
    CINETPAY_SITE_ID: Optional[str] = None
    CINETPAY_SECRET_KEY: Optional[str] = None
    CINETPAY_SANDBOX: bool = True
    APP_BASE_URL: str = "http://localhost:8000"
    
    # =========================================
    # REDIS (CACHE ET CELERY)
    # =========================================
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # =========================================
    # UPLOAD ET STOCKAGE
    # =========================================
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,gif,mp4"
    UPLOAD_DIR: str = "uploads"
    
    # =========================================
    # TARIFICATION (PRIX MIS À JOUR +100 FCFA)
    # =========================================
    PRICE_MONTHLY: int = 2100      # 2000 + 100 FCFA
    PRICE_QUARTERLY: int = 5100    # 5000 + 100 FCFA
    PRICE_BIANNUAL: int = 9100     # 9000 + 100 FCFA
    PRICE_ANNUAL: int = 16100      # 16000 + 100 FCFA
    
    @property
    def SUBSCRIPTION_PRICES(self) -> dict:
        """Dictionnaire des prix d'abonnement"""
        return {
            "monthly": self.PRICE_MONTHLY,
            "quarterly": self.PRICE_QUARTERLY,
            "biannual": self.PRICE_BIANNUAL,
            "annual": self.PRICE_ANNUAL
        }
    
    # =========================================
    # ADMIN PAR DÉFAUT
    # =========================================
    ADMIN_PHONE: str = "+2250701234567"
    ADMIN_PIN: str = "1234"
    SUPER_ADMIN_PHONE: str = "+2250123456789"
    
    # =========================================
    # PÉRIODE D'ESSAI GRATUITE
    # =========================================
    FREE_TRIAL_DAYS: int = 30
    
    # =========================================
    # GÉOLOCALISATION
    # =========================================
    DEFAULT_SEARCH_RADIUS_KM: int = 5
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    
    # =========================================
    # EMAIL (OPTIONNEL)
    # =========================================
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    # =========================================
    # STORAGE CLOUD (OPTIONNEL)
    # =========================================
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "eu-west-1"
    AWS_BUCKET_NAME: str = "allobara-uploads"
    
    CLOUDINARY_CLOUD_NAME: Optional[str] = None
    CLOUDINARY_API_KEY: Optional[str] = None
    CLOUDINARY_API_SECRET: Optional[str] = None
    
    # =========================================
    # MONITORING (OPTIONNEL)
    # =========================================
    SENTRY_DSN: Optional[str] = None
    
    # =========================================
    # RATE LIMITING
    # =========================================
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # =========================================
    # CONFIGURATION PYDANTIC
    # =========================================
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore les variables non définies

# =========================================
# INSTANCE GLOBALE DES PARAMÈTRES
# =========================================
settings = Settings()

# =========================================
# FONCTIONS UTILITAIRES
# =========================================

def get_allowed_extensions() -> List[str]:
    """Obtenir la liste des extensions autorisées"""
    return settings.ALLOWED_EXTENSIONS.split(',')

def get_max_file_size_bytes() -> int:
    """Obtenir la taille max de fichier en bytes"""
    return settings.MAX_FILE_SIZE_MB * 1024 * 1024

def get_price_for_plan(plan: str) -> int:
    """Obtenir le prix pour un plan d'abonnement"""
    return settings.SUBSCRIPTION_PRICES.get(plan, 0)

def is_production() -> bool:
    """Vérifier si nous sommes en production"""
    return settings.ENVIRONMENT == "production"

def is_development() -> bool:
    """Vérifier si nous sommes en développement"""
    return settings.ENVIRONMENT == "development"

def get_upload_path(subfolder: str = "") -> str:
    """Obtenir le chemin complet d'upload"""
    base_path = os.path.join(os.getcwd(), settings.UPLOAD_DIR)
    if subfolder:
        return os.path.join(base_path, subfolder)
    return base_path

# =========================================
# VALIDATION DE LA CONFIGURATION
# =========================================

def validate_config():
    """Valider que la configuration est correcte"""
    errors = []
    
    # Vérifier la base de données
    if not settings.DATABASE_URL:
        errors.append("DATABASE_URL is required")
    
    # Vérifier JWT secret
    if len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY should be at least 32 characters long")
    
    # Vérifier les prix
    if any(price <= 0 for price in settings.SUBSCRIPTION_PRICES.values()):
        errors.append("All subscription prices must be positive")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True