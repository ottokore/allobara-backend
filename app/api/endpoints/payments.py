"""
Endpoints API pour les paiements d'abonnement AlloBara
CinetPay uniquement - Gère tous les opérateurs mobiles
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime

from app.db.database import get_db
from app.api.deps.auth import get_current_user
from app.models.user import User
from app.models.payment import Payment
from app.models.subscription import Subscription, SubscriptionPlan
from app.schemas.payment import (
    PaymentInitRequest,
    PaymentInitResponse,
    PaymentVerificationRequest,
    PaymentVerificationResponse,
    PaymentStatusResponse,
    SubscriptionPlansResponse,
    SubscriptionPlan as SubscriptionPlanSchema,
    PaymentOperatorsResponse,
    PaymentOperator,
    PaymentHistoryResponse
)
from app.services.cinetpay_service import CinetPayService
from app.services.subscription_service import SubscriptionService
from app.services.audit import AuditService


router = APIRouter()


# =========================================
# INITIALISATION DE PAIEMENT
# =========================================

@router.post("/initialize", response_model=PaymentInitResponse)
async def initialize_payment(
    request: PaymentInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initialiser un paiement d'abonnement via CinetPay
    
    Supporte tous les opérateurs: Orange Money, MTN Money, Wave, Moov Money
    
    Args:
        request: Données du paiement (plan, téléphone, opérateur)
        current_user: Utilisateur authentifié
        db: Session de base de données
    
    Returns:
        URL de paiement CinetPay et informations de transaction
    """
    try:
        # Vérifier si l'utilisateur a déjà un abonnement actif
        subscription_service = SubscriptionService(db)
        active_sub = subscription_service.get_user_subscription(current_user.id)
        
        if active_sub and active_sub.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous avez déjà un abonnement actif"
            )
        
        # Mapper le plan vers l'enum
        plan_mapping = {
            "monthly": SubscriptionPlan.MONTHLY,
            "quarterly": SubscriptionPlan.QUARTERLY,
            "biannual": SubscriptionPlan.BIANNUAL,
            "annual": SubscriptionPlan.ANNUAL
        }
        
        plan_enum = plan_mapping.get(request.subscription_plan)
        if not plan_enum:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plan d'abonnement invalide"
            )
        
        # Initialiser le paiement via CinetPay
        customer_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
        if not customer_name:
            customer_name = f"User {current_user.id}"
        
        payment_response = await subscription_service.initiate_payment_with_cinetpay(
            user_id=current_user.id,
            plan=plan_enum,
            customer_name=customer_name,
            customer_phone=request.phone_number
        )
        
        if not payment_response["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=payment_response["message"]
            )
        
        # Audit log
        await AuditService.log_action(
            db=db,
            user_id=current_user.id,
            action="payment_initialized",
            details={
                "plan": request.subscription_plan,
                "amount": payment_response["amount"],
                "operator": request.operator,
                "transaction_id": payment_response["transaction_id"]
            }
        )
        
        return PaymentInitResponse(
            success=True,
            message="Paiement CinetPay initialisé avec succès",
            payment_url=payment_response["payment_url"],
            transaction_id=payment_response["transaction_id"],
            amount=payment_response["amount"],
            currency=payment_response.get("currency", "XOF")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'initialisation: {str(e)}"
        )


# =========================================
# VÉRIFICATION DE PAIEMENT
# =========================================

@router.post("/verify", response_model=PaymentVerificationResponse)
async def verify_payment(
    request: PaymentVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Vérifier le statut d'un paiement auprès de CinetPay
    
    Args:
        request: Transaction ID à vérifier
        current_user: Utilisateur authentifié
        db: Session de base de données
    
    Returns:
        Statut du paiement et informations
    """
    try:
        # Vérifier que le paiement appartient à l'utilisateur
        payment = Payment.get_by_transaction_id(db, request.transaction_id)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction non trouvée"
            )
        
        if payment.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cette transaction ne vous appartient pas"
            )
        
        # Vérifier auprès de CinetPay
        cinetpay_service = CinetPayService(db)
        result = cinetpay_service.check_payment_status(request.transaction_id)
        
        if not result["success"]:
            return PaymentVerificationResponse(
                success=False,
                status="error",
                message=result["message"]
            )
        
        # Mettre à jour le statut du paiement si nécessaire
        payment_status = result["status"]
        
        if payment_status == "ACCEPTED" and payment.status != "success":
            payment.mark_as_success()
            db.commit()
            
            # Audit log
            await AuditService.log_action(
                db=db,
                user_id=current_user.id,
                action="payment_verified",
                details={
                    "transaction_id": request.transaction_id,
                    "status": "success"
                }
            )
        
        return PaymentVerificationResponse(
            success=True,
            status="success" if payment_status == "ACCEPTED" else "pending",
            message=f"Paiement {payment_status}",
            amount=result.get("amount"),
            currency=result.get("currency"),
            payment_method=result.get("payment_method"),
            operator_id=result.get("operator_id"),
            payment_date=result.get("payment_date")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de vérification: {str(e)}"
        )


# =========================================
# STATUT D'ABONNEMENT
# =========================================

@router.get("/status", response_model=PaymentStatusResponse)
async def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer le statut de l'abonnement actuel
    
    Args:
        current_user: Utilisateur authentifié
        db: Session de base de données
    
    Returns:
        Informations sur l'abonnement actif (si existant)
    """
    try:
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active"
        ).first()
        
        if subscription:
            days_remaining = (subscription.end_date.date() - datetime.now().date()).days
            
            return PaymentStatusResponse(
                success=True,
                has_subscription=True,
                subscription={
                    "id": subscription.id,
                    "plan": subscription.plan.value if hasattr(subscription.plan, 'value') else subscription.plan,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )


# =========================================
# HISTORIQUE DES PAIEMENTS
# =========================================

@router.get("/history", response_model=List[PaymentHistoryResponse])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """
    Récupérer l'historique des paiements de l'utilisateur
    
    Args:
        current_user: Utilisateur authentifié
        db: Session de base de données
        limit: Nombre maximum de résultats
        offset: Décalage pour la pagination
    
    Returns:
        Liste des paiements de l'utilisateur
    """
    try:
        payments = db.query(Payment).filter(
            Payment.user_id == current_user.id
        ).order_by(
            Payment.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            PaymentHistoryResponse(
                id=payment.id,
                transaction_id=payment.transaction_id,
                amount=int(payment.amount),
                currency=payment.currency,
                status=payment.status.value if hasattr(payment.status, 'value') else payment.status,
                operator=payment.payment_method.value if payment.payment_method else None,
                description=payment.description,
                created_at=payment.created_at.isoformat(),
                completed_at=payment.completed_at.isoformat() if payment.completed_at else None,
                formatted_amount=payment.formatted_amount
            )
            for payment in payments
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )


# =========================================
# PLANS D'ABONNEMENT
# =========================================

@router.get("/plans", response_model=SubscriptionPlansResponse)
async def get_subscription_plans():
    """
    Liste des plans d'abonnement disponibles
    
    Returns:
        Liste des plans avec détails et prix
    """
    plans = [
        SubscriptionPlanSchema(
            id="monthly",
            name="Mensuel",
            duration_days=30,
            amount=2100,
            currency="FCFA",
            description="Abonnement mensuel - Parfait pour commencer",
            features=[
                "Profil visible dans les recherches",
                "Portfolio illimité",
                "Réception d'appels clients"
            ]
        ),
        SubscriptionPlanSchema(
            id="quarterly",
            name="Trimestriel",
            duration_days=90,
            amount=5100,
            currency="FCFA",
            description="3 mois d'abonnement - Économisez 1200 FCFA",
            features=[
                "Tous les avantages du plan mensuel",
                "Économie de 1200 FCFA",
                "Support prioritaire"
            ],
            savings=1200
        ),
        SubscriptionPlanSchema(
            id="biannual",
            name="Semestriel",
            duration_days=180,
            amount=9100,
            currency="FCFA",
            description="6 mois d'abonnement - Économisez 3500 FCFA",
            features=[
                "Tous les avantages précédents",
                "Économie de 3500 FCFA",
                "Badge 'Prestataire Premium'",
                "Priorité dans les recherches"
            ],
            savings=3500,
            popular=True
        ),
        SubscriptionPlanSchema(
            id="annual",
            name="Annuel",
            duration_days=365,
            amount=16100,
            currency="FCFA",
            description="12 mois d'abonnement - Économisez 9100 FCFA",
            features=[
                "Tous les avantages précédents",
                "Économie de 9100 FCFA",
                "Support VIP 24/7",
                "Accès aux formations gratuites",
                "Badge 'Prestataire Elite'"
            ],
            savings=9100,
            best_value=True
        )
    ]
    
    return SubscriptionPlansResponse(
        success=True,
        plans=plans
    )


# =========================================
# OPÉRATEURS DE PAIEMENT
# =========================================

@router.get("/operators", response_model=PaymentOperatorsResponse)
async def get_payment_operators():
    """
    Liste des opérateurs mobiles supportés par CinetPay
    
    Returns:
        Liste des opérateurs disponibles
    """
    operators = [
        PaymentOperator(
            id="orange",
            name="Orange Money",
            channel="MOBILE_MONEY",
            color="#FF6600",
            icon="🟠",
            enabled=True
        ),
        PaymentOperator(
            id="mtn",
            name="MTN Mobile Money",
            channel="MOBILE_MONEY",
            color="#FFCC00",
            icon="🟡",
            enabled=True
        ),
        PaymentOperator(
            id="wave",
            name="Wave",
            channel="WALLET",
            color="#00A3FF",
            icon="🟣",
            enabled=True
        ),
        PaymentOperator(
            id="moov",
            name="Moov Money",
            channel="MOBILE_MONEY",
            color="#0066CC",
            icon="🔵",
            enabled=True
        )
    ]
    
    return PaymentOperatorsResponse(
        success=True,
        operators=operators
    )


# =========================================
# ANNULATION D'ABONNEMENT
# =========================================

@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Annuler l'abonnement actuel
    L'abonnement restera actif jusqu'à la date d'expiration
    
    Args:
        current_user: Utilisateur authentifié
        db: Session de base de données
    
    Returns:
        Confirmation de l'annulation
    """
    try:
        subscription = db.query(Subscription).filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active"
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Aucun abonnement actif à annuler"
            )
        
        # Marquer comme annulé
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
                "plan": subscription.plan.value if hasattr(subscription.plan, 'value') else subscription.plan,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur: {str(e)}"
        )
