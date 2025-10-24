"""
Endpoints Admin - Détection de fraude
Voir les fraudes, gérer les appareils suspects
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps.auth import get_current_admin_user
from app.models.user import User
from app.services.fraud_detection_service import FraudDetectionService

router = APIRouter()

# =========================================
# SCHÉMAS DE REQUÊTE
# =========================================

class BlockDeviceSchema(BaseModel):
    device_id: int
    reason: str

class UnblockDeviceSchema(BaseModel):
    device_id: int

# =========================================
# ENDPOINTS - LOGS DE FRAUDE
# =========================================

@router.get("/logs")
async def get_fraud_logs(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None, description="low, medium, high, critical")
):
    """
    Récupérer les logs de fraude récents
    
    Query params:
    - limit: Nombre de résultats (max 200)
    - severity: Filtrer par sévérité (optionnel)
    """
    try:
        service = FraudDetectionService(db)
        
        logs = service.get_recent_fraud_logs(limit=limit, severity=severity)
        
        return {
            "success": True,
            "data": logs,
            "count": len(logs)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération logs: {str(e)}"
        )

@router.get("/stats")
async def get_fraud_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=365)
):
    """
    Statistiques de fraude sur une période
    
    Query param:
    - days: Nombre de jours (1-365)
    """
    try:
        service = FraudDetectionService(db)
        
        stats = service.get_fraud_stats(days=days)
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur statistiques fraude: {str(e)}"
        )

# =========================================
# ENDPOINTS - APPAREILS SUSPECTS
# =========================================

@router.get("/devices/suspicious")
async def get_suspicious_devices(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Récupérer les appareils suspects
    
    Query param:
    - limit: Nombre de résultats (max 200)
    """
    try:
        service = FraudDetectionService(db)
        
        devices = service.get_suspicious_devices(limit=limit)
        
        return {
            "success": True,
            "data": devices,
            "count": len(devices)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération appareils: {str(e)}"
        )

@router.post("/devices/block")
async def block_device(
    request: BlockDeviceSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Bloquer un appareil manuellement
    
    Body:
    {
        "device_id": 123,
        "reason": "Abus détecté manuellement"
    }
    """
    try:
        service = FraudDetectionService(db)
        
        result = service.block_device(
            device_id=request.device_id,
            reason=request.reason,
            admin_id=admin_user.id
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur blocage appareil: {str(e)}"
        )

@router.post("/devices/unblock")
async def unblock_device(
    request: UnblockDeviceSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Débloquer un appareil
    
    Body:
    {
        "device_id": 123
    }
    """
    try:
        service = FraudDetectionService(db)
        
        result = service.unblock_device(device_id=request.device_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "message": result["message"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur déblocage appareil: {str(e)}"
        )

@router.get("/devices/{device_id}")
async def get_device_details(
    device_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Détails d'un appareil spécifique
    """
    try:
        from app.models.device_fingerprint import DeviceFingerprint
        
        device = db.query(DeviceFingerprint).filter(
            DeviceFingerprint.id == device_id
        ).first()
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail="Appareil introuvable"
            )
        
        # Récupérer les logs de fraude associés
        service = FraudDetectionService(db)
        fraud_logs = service.get_recent_fraud_logs(limit=20)
        device_logs = [log for log in fraud_logs if log.get("device_id") == device_id]
        
        return {
            "success": True,
            "data": {
                "device": device.to_dict(),
                "fraud_logs": device_logs
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur détails appareil: {str(e)}"
        )

# =========================================
# ENDPOINTS - DASHBOARD FRAUDE
# =========================================

@router.get("/dashboard")
async def get_fraud_dashboard(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Dashboard récapitulatif de la fraude
    """
    try:
        service = FraudDetectionService(db)
        
        # Stats des 7 derniers jours
        stats = service.get_fraud_stats(days=7)
        
        # Appareils suspects
        suspicious_devices = service.get_suspicious_devices(limit=10)
        
        # Logs récents critiques
        from app.models.fraud_log import FraudLog
        critical_logs = db.query(FraudLog).filter(
            FraudLog.severity == "critical"
        ).order_by(FraudLog.detected_at.desc()).limit(5).all()
        
        return {
            "success": True,
            "data": {
                "stats_7_days": stats,
                "suspicious_devices": suspicious_devices,
                "critical_alerts": [log.to_dict() for log in critical_logs],
                "summary": {
                    "total_detections": stats.get("total_detections", 0),
                    "auto_blocked": stats.get("auto_blocked", 0),
                    "pending_review": stats.get("pending_review", 0),
                    "suspicious_devices_count": len(suspicious_devices)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur dashboard fraude: {str(e)}"
        )