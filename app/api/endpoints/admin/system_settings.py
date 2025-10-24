"""
Endpoints Admin - Gestion des paramètres système
Toggle période d'essai, durée, etc.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps.auth import get_current_admin_user
from app.models.user import User
from app.services.system_settings_service import SystemSettingsService

router = APIRouter()

# =========================================
# SCHÉMAS DE REQUÊTE
# =========================================

class ToggleFreeTrialSchema(BaseModel):
    enabled: bool

class UpdateTrialDurationSchema(BaseModel):
    days: int

class UpdateSettingSchema(BaseModel):
    key: str
    value: str

# =========================================
# ENDPOINTS - PÉRIODE D'ESSAI
# =========================================

@router.get("/trial/status")
async def get_trial_status(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Obtenir le statut actuel de la période d'essai
    """
    try:
        service = SystemSettingsService(db)
        
        summary = service.get_trial_settings_summary()
        
        return {
            "success": True,
            "data": {
                "free_trial_enabled": summary["enabled"],
                "free_trial_days": summary["duration_days"],
                "max_accounts_per_device": summary["max_accounts_per_device"],
                "fraud_detection_enabled": summary["fraud_detection_enabled"]
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération statut: {str(e)}"
        )

@router.post("/trial/toggle")
async def toggle_free_trial(
    request: ToggleFreeTrialSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Activer/désactiver la période d'essai gratuite
    
    Body:
    {
        "enabled": true/false
    }
    """
    try:
        service = SystemSettingsService(db)
        
        result = service.toggle_free_trial(
            enabled=request.enabled,
            admin_id=admin_user.id,
            admin_name=f"{admin_user.first_name} {admin_user.last_name}"
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "data": {
                "enabled": request.enabled,
                "updated_by": result.get("updated_by"),
                "updated_at": result.get("updated_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur toggle période d'essai: {str(e)}"
        )

@router.post("/trial/duration")
async def update_trial_duration(
    request: UpdateTrialDurationSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Modifier la durée de la période d'essai
    
    Body:
    {
        "days": 30
    }
    """
    try:
        service = SystemSettingsService(db)
        
        result = service.update_free_trial_duration(
            days=request.days,
            admin_id=admin_user.id,
            admin_name=f"{admin_user.first_name} {admin_user.last_name}"
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "data": {
                "days": request.days,
                "updated_by": result.get("updated_by"),
                "updated_at": result.get("updated_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur modification durée: {str(e)}"
        )

# =========================================
# ENDPOINTS - PARAMÈTRES GÉNÉRAUX
# =========================================

@router.get("/all")
async def get_all_settings(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="trial, fraud, pricing")
):
    """
    Récupérer tous les paramètres système
    
    Query params:
    - category: Filtrer par catégorie (optionnel)
    """
    try:
        service = SystemSettingsService(db)
        
        settings = service.get_all_settings(category=category)
        
        return {
            "success": True,
            "data": settings,
            "count": len(settings)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération paramètres: {str(e)}"
        )

@router.get("/{key}")
async def get_setting_by_key(
    key: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer un paramètre spécifique par sa clé
    
    Exemple: /admin/settings/free_trial_days
    """
    try:
        service = SystemSettingsService(db)
        
        setting = service.get_setting_by_key(key)
        
        if not setting:
            raise HTTPException(
                status_code=404,
                detail=f"Paramètre '{key}' introuvable"
            )
        
        return {
            "success": True,
            "data": setting
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération paramètre: {str(e)}"
        )

@router.post("/update")
async def update_setting(
    request: UpdateSettingSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour un paramètre quelconque
    
    Body:
    {
        "key": "max_accounts_per_device",
        "value": "5"
    }
    """
    try:
        service = SystemSettingsService(db)
        
        result = service.update_setting(
            key=request.key,
            value=request.value,
            admin_id=admin_user.id,
            admin_name=f"{admin_user.first_name} {admin_user.last_name}"
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "data": {
                "key": request.key,
                "value": request.value
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur mise à jour paramètre: {str(e)}"
        )

# =========================================
# ENDPOINTS - PARAMÈTRES ANTI-FRAUDE
# =========================================

@router.post("/fraud/max-accounts")
async def update_max_accounts_per_device(
    max_accounts: int = Query(..., ge=1, le=10),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Modifier le nombre max de comptes par appareil
    
    Query param: max_accounts (entre 1 et 10)
    """
    try:
        service = SystemSettingsService(db)
        
        result = service.update_max_accounts_per_device(
            max_accounts=max_accounts,
            admin_id=admin_user.id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "data": {
                "max_accounts": max_accounts
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur mise à jour max comptes: {str(e)}"
        )

@router.post("/fraud/toggle")
async def toggle_fraud_detection(
    enabled: bool = Query(...),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Activer/désactiver la détection de fraude
    
    Query param: enabled (true/false)
    """
    try:
        service = SystemSettingsService(db)
        
        result = service.toggle_fraud_detection(
            enabled=enabled,
            admin_id=admin_user.id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"],
            "data": {
                "fraud_detection_enabled": enabled
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur toggle détection fraude: {str(e)}"
        )