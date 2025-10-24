"""
Endpoints abonnements AlloBara
Routes pour plans, paiements, renouvellement
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.database import get_db
from app.services.subscription import SubscriptionService
from app.services.payment import PaymentService
from app.schemas.subscription import (
    SubscriptionCreateRequest, SubscriptionRenewRequest, PaymentInitiationRequest,
    SubscriptionCancelRequest, SubscriptionPlanResponse, SubscriptionStatusResponse,
    PaymentResponse, SubscriptionAnalyticsResponse, ReferralStatsResponse,
    PaymentWebhookData, PaymentVerificationResponse, SubscriptionStatsResponse,
    AdminSubscriptionResponse
)
from app.api.deps.auth import get_current_user, get_current_admin_user
from app.models.user import User
from app.core.config import settings

# Router pour les endpoints d'abonnements
router = APIRouter()

# =========================================
# ROUTES PUBLIQUES
# =========================================

@router.get("/plans", response_model=List[SubscriptionPlanResponse])
async def get_subscription_plans():
    """
    Récupérer tous les plans d'abonnement disponibles
    """
    from app.services.subscription import SubscriptionService
    service = SubscriptionService(db=None)  # Pas besoin de DB pour les plans statiques
    
    # Plans avec nouveaux prix (+100 FCFA)
    plans = [
        {
            "id": "monthly",
            "name": "Mensuel",
            "duration_months": 1,
            "price": 2100,  # +100 FCFA
            "original_price": 2000,
            "description": "Abonnement mensuel",
            "features": ["Profil visible", "Portfolio illimité", "Contact direct"],
            "savings": 0,
            "is_popular": False,
            "is_best_value": False
        },
        {
            "id": "quarterly",
            "name": "Trimestriel",
            "duration_months": 3,
            "price": 5100,  # +100 FCFA
            "original_price": 5000,
            "description": "Abonnement trimestriel - Économisez 1200 FCFA",
            "features": ["Tous les avantages mensuel", "Économie de 1200 FCFA", "Support prioritaire"],
            "savings": 1200,
            "is_popular": False,
            "is_best_value": False
        },
        {
            "id": "biannual",
            "name": "Semestriel",
            "duration_months": 6,
            "price": 9100,  # +100 FCFA
            "original_price": 9000,
            "description": "Abonnement semestriel - Économisez 3500 FCFA",
            "features": ["Tous les avantages précédents", "Badge Premium", "Priorité recherches"],
            "savings": 3500,
            "is_popular": True,
            "is_best_value": False
        },
        {
            "id": "annual",
            "name": "Annuel",
            "duration_months": 12,
            "price": 16100,  # +100 FCFA
            "original_price": 16000,
            "description": "Abonnement annuel - Économisez 9100 FCFA",
            "features": ["Support VIP", "Formations gratuites", "Badge Elite"],
            "savings": 9100,
            "is_popular": False,
            "is_best_value": True
        }
    ]
    
    return [SubscriptionPlanResponse(**plan) for plan in plans]

@router.get("/plans/{plan_id}")
async def get_plan_details(plan_id: str):
    """
    Détails d'un plan spécifique
    """
    from app.services.subscription import SubscriptionService
    service = SubscriptionService(db=None)
    
    plans_data = {
        "monthly": {"id": "monthly", "name": "Mensuel", "duration_months": 1, "price": 2100, "original_price": 2000},
        "quarterly": {"id": "quarterly", "name": "Trimestriel", "duration_months": 3, "price": 5100, "original_price": 5000},
        "biannual": {"id": "biannual", "name": "Semestriel", "duration_months": 6, "price": 9100, "original_price": 9000},
        "annual": {"id": "annual", "name": "Annuel", "duration_months": 12, "price": 16100, "original_price": 16000}
    }
    
    plan = plans_data.get(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan d'abonnement introuvable"
        )
    
    plan_details = {
        **plan,
        "description": f"Abonnement {plan['name'].lower()}",
        "features": ["Profil visible", "Portfolio illimité"],
        "savings": 0,
        "is_popular": plan_id == "biannual",
        "is_best_value": plan_id == "annual"
    }
    
    return SubscriptionPlanResponse(**plan_details)

# =========================================
# ROUTES AUTHENTIFIÉES
# =========================================

@router.get("/me/status", response_model=SubscriptionStatusResponse)
async def get_my_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer le statut de mon abonnement
    """
    service = SubscriptionService(db)
    status_data = service.get_user_subscription_status(current_user.id)
    
    return SubscriptionStatusResponse(**status_data)

@router.post("/create")
async def create_subscription(
    request: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Créer un nouvel abonnement
    """
    service = SubscriptionService(db)
    result = await service.create_subscription(
        current_user.id,
        request.plan,
        request.payment_method.value,
        request.referral_code
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.post("/payment/initiate", response_model=PaymentResponse)
async def initiate_payment(
    request: PaymentInitiationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initier un paiement Wave pour l'abonnement
    """
    payment_service = PaymentService(db)
    result = await payment_service.initiate_wave_payment(
        request.subscription_id,
        request.phone_number,
        current_user.id
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return PaymentResponse(**result["data"])

@router.post("/renew")
async def renew_subscription(
    request: SubscriptionRenewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Renouveler mon abonnement
    """
    service = SubscriptionService(db)
    result = await service.renew_subscription(
        current_user.id,
        request.new_plan
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.post("/cancel")
async def cancel_subscription(
    request: SubscriptionCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Annuler mon abonnement
    """
    service = SubscriptionService(db)
    result = service.cancel_subscription(current_user.id, request.reason)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.get("/me/analytics", response_model=SubscriptionAnalyticsResponse)
async def get_subscription_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analytics détaillés de mon abonnement
    """
    service = SubscriptionService(db)
    analytics = service.get_subscription_analytics(current_user.id)
    
    if "error" in analytics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=analytics["error"]
        )
    
    return SubscriptionAnalyticsResponse(**analytics)

@router.get("/me/history")
async def get_subscription_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Historique de mes abonnements
    """
    # Pour l'instant, un utilisateur n'a qu'un abonnement
    # Cette route sera étendue si on permet plusieurs abonnements
    service = SubscriptionService(db)
    status_data = service.get_user_subscription_status(current_user.id)
    
    if not status_data.get("has_subscription"):
        return {"history": [], "total": 0}
    
    return {
        "history": [status_data],
        "total": 1
    }

# =========================================
# ROUTES PARRAINAGE
# =========================================

@router.get("/me/referral", response_model=ReferralStatsResponse)
async def get_referral_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Statistiques de mon parrainage
    """
    service = SubscriptionService(db)
    stats = service.get_referral_stats(current_user.id)
    
    if "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=stats["error"]
        )
    
    return ReferralStatsResponse(**stats)

@router.get("/referral/validate/{code}")
async def validate_referral_code(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Valider un code de parrainage
    """
    if not code.startswith('ALL') or len(code) != 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de code de parrainage invalide"
        )
    
    # Chercher l'utilisateur avec ce code
    user = db.query(User).filter(User.referral_code == code).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Code de parrainage introuvable"
        )
    
    return {
        "valid": True,
        "sponsor_name": user.full_name,
        "sponsor_profession": user.profession,
        "discount_amount": 500,  # 500 FCFA de réduction
        "message": f"Code valide ! Vous bénéficierez de 500 FCFA de réduction grâce à {user.full_name}"
    }

# =========================================
# WEBHOOKS PAIEMENT
# =========================================

@router.post("/webhook/payment")
async def payment_webhook(
    webhook_data: PaymentWebhookData,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook pour les confirmations de paiement Wave
    """
    try:
        payment_service = PaymentService(db)
        
        # Traiter le webhook en arrière-plan
        background_tasks.add_task(
            payment_service.process_payment_webhook,
            webhook_data.dict()
        )
        
        return {"status": "received", "message": "Webhook traité"}
        
    except Exception as e:
        print(f"Erreur payment_webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du traitement du webhook"
        )

@router.post("/payment/verify/{payment_id}", response_model=PaymentVerificationResponse)
async def verify_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Vérifier le statut d'un paiement
    """
    payment_service = PaymentService(db)
    result = await payment_service.verify_payment_status(payment_id, current_user.id)
    
    return PaymentVerificationResponse(**result)

# =========================================
# ROUTES ADMIN
# =========================================

@router.get("/admin/stats")
async def admin_get_subscription_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Statistiques globales des abonnements pour l'admin
    """
    try:
        from sqlalchemy import func
        from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionPlan
        
        # Statistiques de base
        total_subs = db.query(Subscription).count()
        active_subs = db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        trial_subs = db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.TRIAL
        ).count()
        expired_subs = db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.EXPIRED
        ).count()
        
        # Par plan
        plan_stats = db.query(
            Subscription.plan,
            func.count(Subscription.id).label('count'),
            func.sum(Subscription.price).label('revenue')
        ).group_by(Subscription.plan).all()
        
        plan_data = {
            "monthly_count": 0, "quarterly_count": 0, 
            "biannual_count": 0, "annual_count": 0,
            "monthly_revenue": 0, "quarterly_revenue": 0,
            "biannual_revenue": 0, "annual_revenue": 0
        }
        
        for plan, count, revenue in plan_stats:
            plan_data[f"{plan.value}_count"] = count
            plan_data[f"{plan.value}_revenue"] = revenue or 0
        
        total_revenue = sum([
            plan_data["monthly_revenue"],
            plan_data["quarterly_revenue"],
            plan_data["biannual_revenue"], 
            plan_data["annual_revenue"]
        ])
        
        return {
            "total_subscriptions": total_subs,
            "active_subscriptions": active_subs,
            "trial_subscriptions": trial_subs,
            "expired_subscriptions": expired_subs,
            "total_revenue": total_revenue,
            "formatted_revenue": f"{int(total_revenue):,} FCFA".replace(",", " "),
            **plan_data
        }
        
    except Exception as e:
        print(f"Erreur admin_get_subscription_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )

@router.get("/admin/expiring")
async def admin_get_expiring_subscriptions(
    days: int = Query(7, ge=1, le=30, description="Jours avant expiration"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Abonnements qui expirent dans X jours
    """
    try:
        from datetime import datetime, timedelta
        from app.models.subscription import Subscription, SubscriptionStatus
        
        target_date = datetime.utcnow() + timedelta(days=days)
        
        expiring_subs = db.query(Subscription).join(User).filter(
            and_(
                Subscription.end_date <= target_date,
                Subscription.status == SubscriptionStatus.ACTIVE,
                User.is_active == True
            )
        ).all()
        
        results = []
        for sub in expiring_subs:
            results.append({
                "subscription_id": sub.id,
                "user_id": sub.user_id,
                "user_name": sub.user.full_name,
                "user_phone": sub.user.phone,
                "plan": sub.plan.value,
                "days_remaining": sub.days_remaining,
                "end_date": sub.end_date.isoformat(),
                "warning_sent": sub.expiry_warning_sent
            })
        
        return {
            "expiring_subscriptions": results,
            "total": len(results),
            "days_threshold": days
        }
        
    except Exception as e:
        print(f"Erreur admin_get_expiring_subscriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération"
        )

@router.post("/admin/check-expirations")
async def admin_check_expirations(
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Vérifier et traiter les abonnements qui expirent
    """
    service = SubscriptionService(db)
    
    # Exécuter en arrière-plan
    background_tasks.add_task(service.check_expiring_subscriptions)
    
    return {
        "message": "Vérification des expirations lancée en arrière-plan",
        "status": "processing"
    }

@router.post("/admin/{user_id}/create-trial")
async def admin_create_trial(
    user_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Créer une période d'essai pour un utilisateur (admin uniquement)
    """
    service = SubscriptionService(db)
    result = service.create_trial_subscription(user_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.post("/admin/{subscription_id}/activate")
async def admin_activate_subscription(
    subscription_id: int,
    payment_reference: str = Query(..., description="Référence de paiement"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Activer manuellement un abonnement (admin)
    """
    service = SubscriptionService(db)
    result = await service.activate_subscription_after_payment(
        subscription_id,
        f"ADMIN_ACTIVATION_{payment_reference}"
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

# =========================================
# ROUTES UTILITAIRES
# =========================================

@router.get("/calculator")
async def subscription_calculator(
    plan: str = Query(..., description="Plan à calculer"),
    months: int = Query(1, ge=1, le=24, description="Nombre de mois")
):
    """
    Calculateur d'économies pour les plans
    """
    try:
        # Prix des plans avec nouveaux tarifs (+100 FCFA)
        prices = {
            "monthly": 2100,
            "quarterly": 5100,
            "biannual": 9100,
            "annual": 16100
        }
        
        if plan not in prices:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Plan invalide"
            )
        
        base_monthly_price = prices["monthly"]
        plan_price = prices[plan]
        
        # Calculer selon le nombre de mois demandé
        if plan == "monthly":
            total_cost = base_monthly_price * months
            savings = 0
        elif plan == "quarterly" and months >= 3:
            cycles = months // 3
            remaining_months = months % 3
            total_cost = (cycles * prices["quarterly"]) + (remaining_months * base_monthly_price)
            equivalent_monthly_cost = months * base_monthly_price
            savings = equivalent_monthly_cost - total_cost
        elif plan == "biannual" and months >= 6:
            cycles = months // 6
            remaining_months = months % 6
            total_cost = (cycles * prices["biannual"]) + (remaining_months * base_monthly_price)
            equivalent_monthly_cost = months * base_monthly_price
            savings = equivalent_monthly_cost - total_cost
        elif plan == "annual" and months >= 12:
            cycles = months // 12
            remaining_months = months % 12
            total_cost = (cycles * prices["annual"]) + (remaining_months * base_monthly_price)
            equivalent_monthly_cost = months * base_monthly_price
            savings = equivalent_monthly_cost - total_cost
        else:
            total_cost = base_monthly_price * months
            savings = 0
        
        savings_percentage = (savings / (months * base_monthly_price) * 100) if months > 0 else 0
        
        return {
            "plan": plan,
            "months": months,
            "total_cost": total_cost,
            "equivalent_monthly_cost": months * base_monthly_price,
            "savings": savings,
            "savings_percentage": round(savings_percentage, 1),
            "cost_per_month": round(total_cost / months, 0),
            "formatted_total": f"{int(total_cost):,} FCFA".replace(",", " "),
            "formatted_savings": f"{int(savings):,} FCFA".replace(",", " ")
        }
        
    except Exception as e:
        print(f"Erreur subscription_calculator: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du calcul"
        )

@router.get("/trial/info")
async def get_trial_info():
    """
    Informations sur la période d'essai gratuite
    """
    return {
        "duration_days": settings.FREE_TRIAL_DAYS,
        "description": "Période d'essai gratuite pour tous les nouveaux prestataires",
        "features": [
            "Profil visible pendant 30 jours",
            "Accès complet à toutes les fonctionnalités",
            "Portfolio illimité",
            "Contact direct avec les clients",
            "Support client standard"
        ],
        "what_happens_after": [
            "Votre profil devient invisible aux clients",
            "Vous gardez accès en lecture seule",
            "Vous pouvez réactiver en souscrivant un abonnement",
            "Vos données sont conservées"
        ],
        "upgrade_benefits": [
            "Visibilité continue",
            "Fonctionnalités premium",
            "Support prioritaire",
            "Statistiques avancées"
        ]
    }