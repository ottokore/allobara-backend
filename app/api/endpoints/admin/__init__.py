"""
Routers Admin AlloBara
Point d'entrée principal pour toutes les routes admin
"""

from fastapi import APIRouter

# Import des sous-routers
from .system_settings import router as system_settings_router
from .fraud_detection import router as fraud_detection_router
from .payments import router as payments_router

# Router principal
router = APIRouter()

# Inclusion des sous-routers
router.include_router(system_settings_router, prefix="/settings", tags=["Admin - Settings"])
router.include_router(fraud_detection_router, prefix="/fraud", tags=["Admin - Fraud Detection"])
router.include_router(payments_router, prefix="/payments", tags=["Admin - Payments"])

# Route de test
@router.get("/health")
async def admin_health():
    """Vérifier que le module admin fonctionne"""
    return {
        "success": True,
        "message": "Admin module is running",
        "version": "2.0",
        "modules": {
            "settings": "✅",
            "fraud_detection": "✅",
            "payments": "✅"
        }
    }