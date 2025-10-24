"""
Endpoints Webhook pour CinetPay
Reçoit et traite les notifications de paiement
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, status
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
import hashlib
import hmac

from app.db.database import get_db
from app.schemas.payment import CinetPayWebhookData
from app.services.cinetpay_service import CinetPayService
from app.services.subscription_service import SubscriptionService
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.core.config import settings


router = APIRouter()
logger = logging.getLogger(__name__)


# =========================================
# WEBHOOK CINETPAY
# =========================================

@router.post("/cinetpay")
async def cinetpay_webhook(
    webhook_data: CinetPayWebhookData,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook principal pour les notifications CinetPay
    Appelé automatiquement par CinetPay lors d'un paiement
    
    Args:
        webhook_data: Données du webhook
        background_tasks: Tâches en arrière-plan
        request: Requête FastAPI
        db: Session de base de données
    
    Returns:
        Confirmation de réception
    """
    
    logger.info(f"🔔 Webhook CinetPay reçu: {webhook_data.dict()}")
    
    try:
        # 1. Vérifier que le site_id correspond
        cinetpay_service = CinetPayService(db)
        
        if webhook_data.cpm_site_id != cinetpay_service.site_id:
            logger.error(f"❌ Site ID invalide: {webhook_data.cpm_site_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Site ID invalide"
            )
        
        # 2. Récupérer notre transaction_id (stocké dans cpm_custom)
        transaction_id = webhook_data.cpm_custom
        
        if not transaction_id:
            logger.error("❌ Transaction ID manquant dans le webhook")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction ID manquant"
            )
        
        logger.info(f"📝 Traitement webhook pour transaction: {transaction_id}")
        
        # 3. Traiter le webhook via le service
        result = cinetpay_service.process_webhook(webhook_data.dict())
        
        if not result["success"]:
            logger.error(f"❌ Erreur traitement webhook: {result['message']}")
            return {
                "status": "error",
                "message": result["message"]
            }
        
        # 4. Si paiement réussi, activer l'abonnement en arrière-plan
        if result.get("status") == "success":
            logger.info(f"✅ Paiement réussi, activation de l'abonnement...")
            background_tasks.add_task(
                activate_subscription_from_payment,
                payment_id=result["payment_id"],
                db=db
            )
        
        logger.info(f"✅ Webhook traité avec succès: {transaction_id}")
        
        # CinetPay attend cette réponse
        return {
            "status": "received",
            "code": "00",
            "message": "Webhook traité avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur webhook CinetPay: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement: {str(e)}"
        )


# =========================================
# VÉRIFICATION MANUELLE
# =========================================

@router.post("/cinetpay/verify/{transaction_id}")
async def manual_verify_cinetpay(
    transaction_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Vérification manuelle d'un paiement CinetPay
    Utile pour le développement ou en cas de problème de webhook
    
    Args:
        transaction_id: ID de transaction AlloBara
        background_tasks: Tâches en arrière-plan
        db: Session de base de données
    
    Returns:
        Statut de la vérification
    """
    
    logger.info(f"🔍 Vérification manuelle demandée: {transaction_id}")
    
    try:
        cinetpay_service = CinetPayService(db)
        
        # Vérifier le statut auprès de CinetPay
        result = cinetpay_service.check_payment_status(transaction_id)
        
        if not result["success"]:
            return {
                "success": False,
                "message": result["message"]
            }
        
        # Récupérer le paiement
        payment = Payment.get_by_transaction_id(db, transaction_id)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Paiement non trouvé"
            )
        
        # Si le paiement est accepté et pas encore marqué comme success
        if result["status"] == "ACCEPTED" and payment.status != "success":
            logger.info(f"✅ Paiement confirmé, mise à jour...")
            
            # Marquer comme success
            payment.mark_as_success(
                cinetpay_transaction_id=result.get("operator_id")
            )
            db.commit()
            
            # Activer l'abonnement en arrière-plan
            background_tasks.add_task(
                activate_subscription_from_payment,
                payment_id=payment.id,
                db=db
            )
            
            return {
                "success": True,
                "message": "Paiement confirmé et abonnement en cours d'activation",
                "status": "success",
                "payment_id": payment.id
            }
        
        return {
            "success": True,
            "message": f"Statut: {result['status']}",
            "status": result["status"],
            "details": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur vérification manuelle: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )


# =========================================
# TEST DU WEBHOOK
# =========================================

@router.get("/cinetpay/test")
async def test_webhook_endpoint():
    """
    Test de disponibilité du webhook
    
    Returns:
        Confirmation que le webhook est accessible
    """
    return {
        "success": True,
        "message": "Webhook CinetPay opérationnel",
        "endpoint": "/api/v1/webhooks/cinetpay",
        "methods": ["POST"]
    }


@router.post("/cinetpay/test")
async def test_webhook_post():
    """
    Test POST du webhook
    
    Returns:
        Confirmation de réception
    """
    return {
        "success": True,
        "message": "Webhook CinetPay peut recevoir des requêtes POST",
        "timestamp": "2025-01-24T10:00:00Z"
    }


# =========================================
# TÂCHE D'ACTIVATION D'ABONNEMENT
# =========================================

async def activate_subscription_from_payment(payment_id: int, db: Session):
    """
    Active l'abonnement après un paiement réussi
    Exécuté en arrière-plan
    
    Args:
        payment_id: ID du paiement
        db: Session de base de données
    """
    try:
        logger.info(f"🔄 Activation abonnement pour paiement #{payment_id}")
        
        # Récupérer le paiement
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment:
            logger.error(f"❌ Paiement #{payment_id} non trouvé")
            return
        
        if payment.status != "success":
            logger.warning(f"⚠️ Paiement #{payment_id} pas en statut success")
            return
        
        # Récupérer l'utilisateur
        user = payment.user
        
        if not user:
            logger.error(f"❌ Utilisateur non trouvé pour paiement #{payment_id}")
            return
        
        # Si un subscription_id existe déjà, l'utiliser
        if payment.subscription_id:
            subscription = db.query(Subscription).filter(
                Subscription.id == payment.subscription_id
            ).first()
            
            if subscription:
                logger.info(f"📦 Abonnement #{subscription.id} trouvé, activation...")
                
                # Activer via le service
                subscription_service = SubscriptionService(db)
                result = subscription_service.activate_subscription_from_payment(
                    payment_id=payment.id,
                    plan=subscription.plan
                )
                
                if result["success"]:
                    logger.info(f"✅ Abonnement #{subscription.id} activé avec succès")
                    
                    # Mettre à jour le statut utilisateur
                    user.subscription_status = "active"
                    user.is_visible = True
                    db.commit()
                else:
                    logger.error(f"❌ Échec activation: {result['message']}")
        else:
            logger.warning(f"⚠️ Pas de subscription_id pour paiement #{payment_id}")
            # On pourrait créer un nouvel abonnement ici si nécessaire
        
    except Exception as e:
        logger.error(f"❌ Erreur activation abonnement: {str(e)}")
        db.rollback()


# =========================================
# LOGS ET DEBUGGING
# =========================================

@router.get("/cinetpay/logs/{transaction_id}")
async def get_webhook_logs(
    transaction_id: str,
    db: Session = Depends(get_db)
):
    """
    Récupère les logs webhook d'une transaction
    Utile pour le debugging
    
    Args:
        transaction_id: ID de transaction
        db: Session de base de données
    
    Returns:
        Logs du webhook si disponibles
    """
    try:
        payment = Payment.get_by_transaction_id(db, transaction_id)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction non trouvée"
            )
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "webhook_received": payment.webhook_received,
            "webhook_received_at": payment.webhook_received_at.isoformat() if payment.webhook_received_at else None,
            "webhook_data": payment.webhook_data,
            "status": payment.status.value if payment.status else None,
            "provider_response": payment.provider_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )
