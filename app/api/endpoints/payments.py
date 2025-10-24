# backend/app/api/endpoints/payments.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Dict, Any, List, Optional
import json
from datetime import datetime, timedelta
from pydantic import BaseModel, validator

from app.db.database import get_db
from app.api.deps.auth import get_current_user
from app.models.user import User
from app.models.subscription import Subscription
from app.services.payment import PaymentService
from app.services.subscription import SubscriptionService
from app.services.cinetpay_service import CinetPayService
from app.services.admin_service import AdminService
from app.services.audit import AuditService
from app.core.config import settings

router = APIRouter()
security = HTTPBearer()

# =========================================
# SCHÉMAS PYDANTIC LOCAUX
# =========================================

class PaymentInitRequest(BaseModel):
    subscription_plan: str  # "monthly", "quarterly", "biannual", "annual"
    phone_number: str
    operator: str = "wave"  # "wave", "orange_money", "mtn_money", "moov"
    payment_provider: str = "wave"  # 🆕 "wave" ou "cinetpay"
    
    @validator('subscription_plan')
    def validate_plan(cls, v):
        valid_plans = ["monthly", "quarterly", "biannual", "annual"]
        if v not in valid_plans:
            raise ValueError(f"Plan invalide. Doit être un de: {valid_plans}")
        return v
    
    @validator('payment_provider')
    def validate_provider(cls, v):
        valid_providers = ["wave", "cinetpay"]
        if v not in valid_providers:
            raise ValueError(f"Provider invalide. Doit être: wave ou cinetpay")
        return v

class PaymentVerificationRequest(BaseModel):
    transaction_id: str
    payment_reference: str

class WebhookRequest(BaseModel):
    transaction_id: str
    status: str
    amount: int
    currency: str = "XOF"
    user_phone: str
    reference: str
    timestamp: str
    signature: str

class PaymentStatusResponse(BaseModel):
    success: bool
    has_subscription: bool
    subscription: Optional[Dict[str, Any]] = None
    message: str

# =========================================
# ENDPOINTS
# =========================================

@router.post("/initialize", response_model=Dict[str, Any])
async def initialize_payment(
    request: PaymentInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialiser un paiement pour l'abonnement avec nouveaux prix (+100 FCFA)
    Supporte Wave et CinetPay
    """
    try:
        # Vérification si utilisateur a déjà un abonnement actif
        active_subscription = SubscriptionService(db).get_user_subscription(current_user.id)
        if active_subscription and active_subscription.get("is_active"):
            raise HTTPException(
                status_code=400,
                detail="Vous avez déjà un abonnement actif"
            )
        
        # Calcul du montant avec les nouveaux prix (+100 FCFA)
        amounts = {
            "monthly": 2100,
            "quarterly": 5100,
            "biannual": 9100,
            "annual": 16100
        }
        amount = amounts[request.subscription_plan]
        
        # 🆕 ROUTER VERS LE BON PROVIDER
        if request.payment_provider == "cinetpay":
            # Utiliser CinetPay
            from app.models.subscription import SubscriptionPlan
            
            subscription_service = SubscriptionService(db)
            plan_enum = SubscriptionPlan(request.subscription_plan)
            
            payment_response = await subscription_service.initiate_payment_with_cinetpay(
                user_id=current_user.id,
                plan=plan_enum,
                customer_name=f"{current_user.first_name} {current_user.last_name}",
                customer_phone=request.phone_number
            )
            
            if not payment_response["success"]:
                raise HTTPException(status_code=400, detail=payment_response["message"])
            
            return {
                "success": True,
                "message": "Paiement CinetPay initialisé avec succès",
                "provider": "cinetpay",
                "payment_url": payment_response["payment_url"],
                "transaction_id": payment_response["transaction_id"],
                "amount": payment_response["amount"]
            }
        
        else:
            # Utiliser Wave (code existant)
            payment_response = await PaymentService.initialize_payment(
                user_id=current_user.id,
                amount=amount,
                phone_number=request.phone_number,
                operator=request.operator,
                subscription_plan=request.subscription_plan,
                db=db
            )
            
            # Audit log
            await AuditService.log_action(
                db=db,
                user_id=current_user.id,
                action="payment_initialized",
                details={
                    "plan": request.subscription_plan,
                    "amount": amount,
                    "operator": request.operator,
                    "provider": "wave",
                    "transaction_id": payment_response.get("transaction_id")
                }
            )
            
            return {
                "success": True,
                "message": "Paiement Wave initialisé avec succès",
                "provider": "wave",
                "data": payment_response
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'initialisation: {str(e)}")

@router.post("/verify")
async def verify_payment(
    request: PaymentVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Vérifier le statut d'un paiement
    """
    try:
        verification = await PaymentService.verify_payment(
            transaction_id=request.transaction_id,
            payment_reference=request.payment_reference,
            user_id=current_user.id,
            db=db
        )
        
        if verification["status"] == "success":
            # Activation de l'abonnement
            subscription = await SubscriptionService.activate_subscription(
                user_id=current_user.id,
                plan=verification["subscription_plan"],
                transaction_id=request.transaction_id,
                db=db
            )
            
            # Mise à jour du statut utilisateur
            current_user.subscription_status = "active"
            current_user.updated_at = datetime.utcnow()
            db.commit()
            
            # Audit log
            await AuditService.log_action(
                db=db,
                user_id=current_user.id,
                action="payment_completed",
                details={
                    "transaction_id": request.transaction_id,
                    "plan": verification["subscription_plan"],
                    "amount": verification["amount"]
                }
            )
            
            return {
                "success": True,
                "message": "Paiement confirmé et abonnement activé",
                "subscription": {
                    "id": subscription.id,
                    "plan": subscription.plan,
                    "status": "active",
                    "end_date": subscription.end_date.isoformat()
                }
            }
        
        return {
            "success": False,
            "message": f"Paiement {verification['status']}",
            "data": verification
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de vérification: {str(e)}")

@router.post("/webhook")
async def payment_webhook(
    request: WebhookRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    raw_request: Request = None
):
    """
    Webhook pour les notifications de paiement Wave
    """
    try:
        # Vérification de la signature (sécurité)
        if not PaymentService.verify_webhook_signature(
            payload=await raw_request.body(),
            signature=request.signature
        ):
            raise HTTPException(status_code=400, detail="Signature invalide")
        
        # Traitement du webhook en arrière-plan
        background_tasks.add_task(
            process_payment_webhook,
            request.dict(),
            db
        )
        
        return {"status": "received"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur webhook: {str(e)}")

async def process_payment_webhook(webhook_data: dict, db: Session):
    """
    Traitement asynchrone du webhook
    """
    try:
        transaction_id = webhook_data["transaction_id"]
        status = webhook_data["status"]
        amount = webhook_data["amount"]
        user_phone = webhook_data["user_phone"]
        
        # Recherche de l'utilisateur par téléphone
        user = db.query(User).filter(User.phone_number == user_phone).first()
        if not user:
            print(f"Utilisateur non trouvé pour le téléphone: {user_phone}")
            return
        
        if status == "successful":
            # Détermination du plan basé sur le montant avec nouveaux prix
            plan_mapping = {
                2100: "monthly",    # +100 FCFA
                5100: "quarterly",  # +100 FCFA
                9100: "biannual",   # +100 FCFA
                16100: "annual"     # +100 FCFA
            }
            plan = plan_mapping.get(amount)
            
            if not plan:
                print(f"Plan non reconnu pour le montant: {amount}")
                return
            
            # Activation de l'abonnement
            subscription = await SubscriptionService.activate_subscription(
                user_id=user.id,
                plan=plan,
                transaction_id=transaction_id,
                db=db
            )
            
            # Mise à jour du statut utilisateur
            user.subscription_status = "active"
            user.updated_at = datetime.utcnow()
            
            # Mise à jour du wallet admin
            await AdminService.update_wallet_balance(db, amount)
            await AdminService.update_daily_stats(db, revenue=amount)
            
            db.commit()
            
            # Audit log
            await AuditService.log_action(
                db=db,
                user_id=user.id,
                action="webhook_payment_success",
                details={
                    "transaction_id": transaction_id,
                    "plan": plan,
                    "amount": amount
                }
            )
            
            print(f"Abonnement activé pour l'utilisateur {user.id} - Plan: {plan}")
            
        else:
            # Échec du paiement
            await AuditService.log_action(
                db=db,
                user_id=user.id,
                action="webhook_payment_failed",
                details={
                    "transaction_id": transaction_id,
                    "status": status,
                    "amount": amount
                }
            )
            
            print(f"Paiement échoué pour l'utilisateur {user.id} - Status: {status}")
            
    except Exception as e:
        print(f"Erreur lors du traitement du webhook: {e}")

@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """
    Historique des paiements de l'utilisateur
    """
    try:
        subscriptions = db.query(Subscription).filter(
            Subscription.user_id == current_user.id
        ).order_by(Subscription.created_at.desc()).offset(offset).limit(limit).all()
        
        history = []
        for sub in subscriptions:
            history.append({
                "id": sub.id,
                "plan": sub.plan,
                "amount": sub.amount,
                "start_date": sub.start_date.isoformat(),
                "end_date": sub.end_date.isoformat(),
                "status": "active" if sub.is_active else "expired",
                "transaction_id": sub.transaction_id,
                "created_at": sub.created_at.isoformat()
            })
        
        return {
            "success": True,
            "data": history,
            "total": len(history)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération: {str(e)}")

@router.get("/subscription-status", response_model=PaymentStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Statut actuel de l'abonnement
    """
    try:
        subscription = SubscriptionService.get_active_subscription(db, current_user.id)
        
        if subscription:
            days_remaining = (subscription.end_date.date() - datetime.now().date()).days
            return PaymentStatusResponse(
                success=True,
                has_subscription=True,
                subscription={
                    "id": subscription.id,
                    "plan": subscription.plan,
                    "start_date": subscription.start_date.isoformat(),
                    "end_date": subscription.end_date.isoformat(),
                    "days_remaining": days_remaining,
                    "status": "active" if days_remaining > 0 else "expiring_soon",
                    "amount": subscription.amount
                },
                message="Abonnement actif"
            )
        
        return PaymentStatusResponse(
            success=True,
            has_subscription=False,
            subscription=None,
            message="Aucun abonnement actif"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la vérification: {str(e)}")

@router.get("/plans")
async def get_subscription_plans():
    """
    Liste des plans d'abonnement disponibles avec les nouveaux prix (+100 FCFA)
    """
    plans = [
        {
            "id": "monthly",
            "name": "Mensuel",
            "duration_days": 30,
            "amount": 2100,  # +100 FCFA
            "currency": "FCFA",
            "description": "Abonnement mensuel - Parfait pour commencer",
            "features": [
                "Profil visible dans les recherches",
                "Portfolio illimité",
                "Réception d'appels clients"
            ]
        },
        {
            "id": "quarterly", 
            "name": "Trimestriel",
            "duration_days": 90,
            "amount": 5100,  # +100 FCFA
            "currency": "FCFA",
            "description": "3 mois d'abonnement - Économisez 1200 FCFA",
            "features": [
                "Tous les avantages du plan mensuel",
                "Économie de 1200 FCFA",
                "Support prioritaire"
            ],
            "savings": 1200
        },
        {
            "id": "biannual",
            "name": "Semestriel", 
            "duration_days": 180,
            "amount": 9100,  # +100 FCFA
            "currency": "FCFA",
            "description": "6 mois d'abonnement - Économisez 3500 FCFA",
            "features": [
                "Tous les avantages précédents",
                "Économie de 3500 FCFA",
                "Badge 'Prestataire Premium'",
                "Priorité dans les recherches"
            ],
            "savings": 3500,
            "popular": True
        },
        {
            "id": "annual",
            "name": "Annuel",
            "duration_days": 365,
            "amount": 16100,  # +100 FCFA
            "currency": "FCFA", 
            "description": "12 mois d'abonnement - Économisez 9100 FCFA",
            "features": [
                "Tous les avantages précédents",
                "Économie de 9100 FCFA",
                "Support VIP 24/7",
                "Accès aux formations gratuites",
                "Badge 'Prestataire Elite'"
            ],
            "savings": 9100,
            "best_value": True
        }
    ]
    
    return {
        "success": True,
        "plans": plans
    }

@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Annuler l'abonnement actuel (désactivation à la fin de la période)
    """
    try:
        subscription = SubscriptionService.get_active_subscription(db, current_user.id)
        
        if not subscription:
            raise HTTPException(
                status_code=400,
                detail="Aucun abonnement actif à annuler"
            )
        
        # Marquer comme annulé (sera désactivé automatiquement à l'expiration)
        subscription.is_cancelled = True
        subscription.cancelled_at = datetime.utcnow()
        db.commit()
        
        # Audit log
        await AuditService.log_action(
            db=db,
            user_id=current_user.id,
            action="subscription_cancelled",
            details={
                "subscription_id": subscription.id,
                "plan": subscription.plan,
                "end_date": subscription.end_date.isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Abonnement annulé. Il restera actif jusqu'à la date d'expiration.",
            "expires_at": subscription.end_date.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'annulation: {str(e)}")

@router.post("/cinetpay/webhook")
async def cinetpay_webhook(
    webhook_data: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook pour les notifications de paiement CinetPay
    """
    try:
        cinetpay_service = CinetPayService(db)
        
        # Traiter le webhook
        result = cinetpay_service.process_webhook(webhook_data)
        
        if result["success"] and result.get("status") == "success":
            # Paiement réussi - activer l'abonnement en arrière-plan
            background_tasks.add_task(
                activate_subscription_from_cinetpay,
                result["payment_id"],
                db
            )
        
        return {"status": "received"}
        
    except Exception as e:
        print(f"Erreur webhook CinetPay: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur webhook: {str(e)}")

async def activate_subscription_from_cinetpay(payment_id: int, db: Session):
    """Activer l'abonnement après un paiement CinetPay réussi"""
    try:
        from app.models.payment import Payment
        
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment or not payment.subscription_id:
            return
        
        # Activer l'abonnement
        subscription_service = SubscriptionService(db)
        
        from app.models.subscription import SubscriptionPlan, Subscription
        subscription = db.query(Subscription).filter(
            Subscription.id == payment.subscription_id
        ).first()
        
        if subscription:
            result = subscription_service.activate_subscription_from_payment(
                payment_id=payment.id,
                plan=subscription.plan
            )
            
            if result["success"]:
                print(f"✅ Abonnement activé pour le paiement {payment_id}")
            
    except Exception as e:
        print(f"❌ Erreur activation abonnement CinetPay: {e}")

@router.get("/methods")
async def get_payment_methods():
    """
    Méthodes de paiement disponibles
    """
    methods = [
        {
            "id": "wave",
            "name": "Wave",
            "description": "Paiement mobile Wave",
            "logo": "/static/wave_logo.png",
            "enabled": True
        },
        {
            "id": "orange_money",
            "name": "Orange Money", 
            "description": "Paiement mobile Orange Money",
            "logo": "/static/orange_money_logo.png",
            "enabled": False  # À activer plus tard
        },
        {
            "id": "mtn_money",
            "name": "MTN Money",
            "description": "Paiement mobile MTN Money", 
            "logo": "/static/mtn_money_logo.png",
            "enabled": False  # À activer plus tard
        }
    ]
    return {
        "success": True,
        "methods": methods
    }