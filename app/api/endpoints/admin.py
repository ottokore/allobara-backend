# app/api/endpoints/admin.py

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps.auth import get_current_admin_user
from app.models.user import User
from app.models.subscription import Subscription
from app.models.admin import AdminWallet, WithdrawalRequest, DailyStats
from app.services.admin_service import AdminService
from app.services.user import UserService
from app.services.audit import AuditService
from app.core.config import settings

router = APIRouter()
security = HTTPBearer()

# Schémas de requête
class WithdrawalRequestSchema(BaseModel):
    amount: int
    wave_phone: str
    description: Optional[str] = None

class UserActionSchema(BaseModel):
    user_id: int
    action: str  # "block", "unblock", "activate_trial"
    reason: Optional[str] = None

class SimulatePaymentSchema(BaseModel):
    user_id: int
    amount: int
    plan: str

# ========== DASHBOARD & STATS ==========

@router.get("/dashboard")
async def get_admin_dashboard(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Dashboard principal avec toutes les métriques importantes
    """
    try:
        # Statistiques d'aujourd'hui
        today = date.today()
        today_stats = await AdminService.get_daily_stats(db, today)
        
        # Statistiques de ce mois
        month_start = date.today().replace(day=1)
        month_stats = await AdminService.get_period_stats(db, month_start, today)
        
        # Statistiques totales
        total_stats = await AdminService.get_total_stats(db)
        
        # Solde du wallet
        wallet = await AdminService.get_admin_wallet(db)
        
        # Utilisateurs récents (7 derniers jours)
        recent_users = await AdminService.get_recent_registrations(db, days=7, limit=10)
        
        # Paiements récents
        recent_payments = await AdminService.get_recent_payments(db, limit=10)
        
        # Demandes de retrait en attente
        pending_withdrawals = await AdminService.get_pending_withdrawals(db)
        
        dashboard_data = {
            # Statistiques du jour
            "today": {
                "new_registrations": today_stats.get("new_registrations", 0),
                "revenue": today_stats.get("revenue", 0),
                "new_subscriptions": today_stats.get("new_subscriptions", 0)
            },
            
            # Statistiques du mois
            "this_month": {
                "new_registrations": month_stats.get("new_registrations", 0),
                "revenue": month_stats.get("revenue", 0),
                "new_subscriptions": month_stats.get("new_subscriptions", 0)
            },
            
            # Statistiques totales
            "total": {
                "users": total_stats.get("total_users", 0),
                "active_subscribers": total_stats.get("active_subscribers", 0),
                "total_revenue": total_stats.get("total_revenue", 0),
                "categories": total_stats.get("total_categories", 0)
            },
            
            # Wallet admin
            "wallet": {
                "available_balance": wallet.available_balance if wallet else 0,
                "pending_balance": wallet.pending_balance if wallet else 0,
                "total_withdrawn": wallet.total_withdrawn if wallet else 0,
                "pending_withdrawals": len(pending_withdrawals)
            },
            
            # Activité récente
            "recent_activity": {
                "new_users": [
                    {
                        "id": user.id,
                        "name": f"{user.first_name} {user.last_name}",
                        "phone": user.phone_number,
                        "category": user.business_category,
                        "city": user.city,
                        "created_at": user.created_at.isoformat(),
                        "subscription_status": user.subscription_status
                    }
                    for user in recent_users
                ],
                "recent_payments": recent_payments
            }
        }
        
        return {
            "success": True,
            "data": dashboard_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur dashboard: {str(e)}")

@router.get("/stats/registrations")
async def get_registration_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    period: str = Query("30d", description="7d, 30d, 90d, 1y")
):
    """
    Statistiques détaillées des inscriptions
    """
    try:
        end_date = date.today()
        
        if period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        else:
            raise HTTPException(status_code=400, detail="Période invalide")
        
        # Statistiques par jour
        daily_stats = await AdminService.get_registration_trend(db, start_date, end_date)
        
        # Top catégories
        top_categories = await AdminService.get_top_categories(db, start_date, end_date)
        
        # Top villes
        top_cities = await AdminService.get_top_cities(db, start_date, end_date)
        
        return {
            "success": True,
            "data": {
                "period": period,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily_registrations": daily_stats,
                "top_categories": top_categories,
                "top_cities": top_cities
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur stats inscriptions: {str(e)}")

@router.get("/stats/revenue")
async def get_revenue_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    period: str = Query("30d", description="7d, 30d, 90d, 1y")
):
    """
    Statistiques détaillées des revenus
    """
    try:
        end_date = date.today()
        
        if period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        elif period == "1y":
            start_date = end_date - timedelta(days=365)
        else:
            raise HTTPException(status_code=400, detail="Période invalide")
        
        # Revenus par jour
        daily_revenue = await AdminService.get_revenue_trend(db, start_date, end_date)
        
        # Répartition par plan d'abonnement
        plan_breakdown = await AdminService.get_revenue_by_plan(db, start_date, end_date)
        
        # Revenus par ville
        city_revenue = await AdminService.get_revenue_by_city(db, start_date, end_date)
        
        return {
            "success": True,
            "data": {
                "period": period,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily_revenue": daily_revenue,
                "revenue_by_plan": plan_breakdown,
                "revenue_by_city": city_revenue,
                "total_period": sum(day["amount"] for day in daily_revenue)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur stats revenus: {str(e)}")

# ========== GESTION DES UTILISATEURS ==========

@router.get("/users")
async def get_all_users(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = Query(None, description="all, active, inactive, pending")
):
    """
    Liste de tous les utilisateurs avec pagination et filtres
    """
    try:
        offset = (page - 1) * per_page
        
        query = db.query(User)
        
        # Filtre par recherche
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (User.first_name.ilike(search_term)) |
                (User.last_name.ilike(search_term)) |
                (User.phone_number.ilike(search_term)) |
                (User.city.ilike(search_term)) |
                (User.business_category.ilike(search_term))
            )
        
        # Filtre par statut
        if status and status != "all":
            if status == "active":
                query = query.filter(User.subscription_status == "active")
            elif status == "inactive":
                query = query.filter(User.is_active == False)
            elif status == "pending":
                query = query.filter(User.subscription_status == "pending")
        
        total = query.count()
        users = query.order_by(User.created_at.desc()).offset(offset).limit(per_page).all()
        
        users_data = []
        for user in users:
            # Récupérer l'abonnement actuel
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user.id,
                Subscription.is_active == True
            ).first()
            
            users_data.append({
                "id": user.id,
                "name": f"{user.first_name} {user.last_name}",
                "phone": user.phone_number,
                "email": user.email,
                "category": user.business_category,
                "city": user.city,
                "commune": user.commune,
                "country": user.country,
                "created_at": user.created_at.isoformat(),
                "is_active": user.is_active,
                "subscription_status": user.subscription_status,
                "subscription": {
                    "plan": subscription.plan if subscription else None,
                    "end_date": subscription.end_date.isoformat() if subscription else None,
                    "amount": subscription.amount if subscription else None
                } if subscription else None,
                "average_rating": user.average_rating,
                "reviews_count": user.reviews_count,
                "is_sponsored": user.is_sponsored
            })
        
        return {
            "success": True,
            "data": users_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur récupération utilisateurs: {str(e)}")

@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Détails complets d'un utilisateur
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Historique des abonnements
        subscriptions = db.query(Subscription).filter(
            Subscription.user_id == user_id
        ).order_by(Subscription.created_at.desc()).all()
        
        # Portfolio
        portfolio = await UserService.get_user_portfolio(db, user_id)
        
        user_data = {
            "id": user.id,
            "personal_info": {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "birth_date": user.birth_date.isoformat() if user.birth_date else None,
                "phone_number": user.phone_number,
                "email": user.email,
                "gender": user.gender
            },
            "business_info": {
                "category": user.business_category,
                "experience_years": user.experience_years,
                "description": user.description,
                "daily_rate": user.daily_rate,
                "monthly_rate": user.monthly_rate
            },
            "location": {
                "country": user.country,
                "city": user.city,
                "commune": user.commune,
                "latitude": user.latitude,
                "longitude": user.longitude
            },
            "account_info": {
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "is_active": user.is_active,
                "subscription_status": user.subscription_status,
                "is_verified": user.is_verified,
                "is_sponsored": user.is_sponsored
            },
            "ratings": {
                "average_rating": user.average_rating,
                "reviews_count": user.reviews_count
            },
            "subscriptions_history": [
                {
                    "id": sub.id,
                    "plan": sub.plan,
                    "amount": sub.amount,
                    "start_date": sub.start_date.isoformat(),
                    "end_date": sub.end_date.isoformat(),
                    "is_active": sub.is_active,
                    "transaction_id": sub.transaction_id,
                    "created_at": sub.created_at.isoformat()
                }
                for sub in subscriptions
            ],
            "portfolio": portfolio
        }
        
        return {
            "success": True,
            "data": user_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur détails utilisateur: {str(e)}")

@router.post("/users/action")
async def user_action(
    request: UserActionSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Actions administratives sur un utilisateur
    """
    try:
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        if request.action == "block":
            user.is_active = False
            user.subscription_status = "blocked"
            action_message = "Utilisateur bloqué"
            
        elif request.action == "unblock":
            user.is_active = True
            # Vérifier s'il a un abonnement valide
            active_sub = db.query(Subscription).filter(
                Subscription.user_id == request.user_id,
                Subscription.is_active == True,
                Subscription.end_date > datetime.utcnow()
            ).first()
            user.subscription_status = "active" if active_sub else "pending"
            action_message = "Utilisateur débloqué"
            
        elif request.action == "activate_trial":
            # Activer période d'essai
            from app.services.subscription import SubscriptionService
            trial_sub = await SubscriptionService.create_trial_subscription(
                user_id=request.user_id,
                db=db
            )
            user.subscription_status = "active"
            action_message = "Période d'essai activée"
            
        else:
            raise HTTPException(status_code=400, detail="Action non reconnue")
        
        user.updated_at = datetime.utcnow()
        db.commit()
        
        # Log d'audit
        await AuditService.log_action(
            db=db,
            user_id=admin_user.id,
            action=f"admin_user_{request.action}",
            details={
                "target_user_id": request.user_id,
                "reason": request.reason,
                "admin_user": f"{admin_user.first_name} {admin_user.last_name}"
            }
        )
        
        return {
            "success": True,
            "message": action_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur action utilisateur: {str(e)}")

# ========== GESTION FINANCIÈRE ==========

@router.get("/wallet/balance")
async def get_wallet_balance(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Solde du wallet administrateur
    """
    try:
        wallet = await AdminService.get_admin_wallet(db)
        
        # Historique des 10 dernières transactions
        recent_transactions = await AdminService.get_recent_transactions(db, limit=10)
        
        return {
            "success": True,
            "data": {
                "available_balance": wallet.available_balance if wallet else 0,
                "pending_balance": wallet.pending_balance if wallet else 0,
                "total_earned": wallet.total_earned if wallet else 0,
                "total_withdrawn": wallet.total_withdrawn if wallet else 0,
                "last_updated": wallet.updated_at.isoformat() if wallet and wallet.updated_at else None,
                "recent_transactions": recent_transactions
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur wallet: {str(e)}")

@router.post("/wallet/withdraw")
async def request_withdrawal(
    request: WithdrawalRequestSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Demander un retrait vers Wave
    """
    try:
        wallet = await AdminService.get_admin_wallet(db)
        
        if not wallet or wallet.available_balance < request.amount:
            raise HTTPException(
                status_code=400,
                detail="Solde insuffisant"
            )
        
        # Minimum de retrait
        if request.amount < 1000:
            raise HTTPException(
                status_code=400,
                detail="Montant minimum de retrait: 1000 FCFA"
            )
        
        withdrawal = await AdminService.create_withdrawal_request(
            db=db,
            amount=request.amount,
            wave_phone=request.wave_phone,
            description=request.description,
            requested_by_id=admin_user.id
        )
        
        return {
            "success": True,
            "message": "Demande de retrait créée",
            "withdrawal_id": withdrawal.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur retrait: {str(e)}")

@router.get("/wallet/withdrawals")
async def get_withdrawal_history(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="pending, completed, failed")
):
    """
    Historique des retraits
    """
    try:
        withdrawals = await AdminService.get_withdrawals(db, status_filter=status)
        
        withdrawals_data = [
            {
                "id": w.id,
                "amount": w.amount,
                "wave_phone": w.wave_phone,
                "status": w.status,
                "description": w.description,
                "requested_at": w.created_at.isoformat(),
                "processed_at": w.processed_at.isoformat() if w.processed_at else None,
                "wave_transaction_id": w.wave_transaction_id,
                "failure_reason": w.failure_reason
            }
            for w in withdrawals
        ]
        
        return {
            "success": True,
            "data": withdrawals_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur historique retraits: {str(e)}")

# ========== OUTILS DE DÉVELOPPEMENT ==========

@router.post("/simulate/payment")
async def simulate_payment(
    request: SimulatePaymentSchema,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Simuler un paiement pour un utilisateur (mode développement)
    """
    try:
        if not settings.DEBUG:
            raise HTTPException(
                status_code=403,
                detail="Fonction disponible uniquement en mode développement"
            )
        
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        # Créer l'abonnement
        from app.services.subscription import SubscriptionService
        subscription = await SubscriptionService.activate_subscription(
            user_id=request.user_id,
            plan=request.plan,
            transaction_id=f"SIMULATE_{datetime.now().timestamp()}",
            db=db
        )
        
        # Mettre à jour le statut
        user.subscription_status = "active"
        user.updated_at = datetime.utcnow()
        
        # Mettre à jour le wallet
        await AdminService.update_wallet_balance(db, request.amount)
        await AdminService.update_daily_stats(db, revenue=request.amount)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Paiement simulé pour {user.first_name} {user.last_name}",
            "subscription_id": subscription.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur simulation: {str(e)}")

@router.post("/stats/update-daily")
async def update_daily_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
    date_str: Optional[str] = Query(None, description="YYYY-MM-DD format")
):
    """
    Mettre à jour les statistiques quotidiennes (tâche cron)
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        
        if background_tasks:
            background_tasks.add_task(
                AdminService.calculate_daily_stats,
                db,
                target_date
            )
            message = "Mise à jour des stats programmée"
        else:
            await AdminService.calculate_daily_stats(db, target_date)
            message = "Statistiques mises à jour"
        
        return {
            "success": True,
            "message": message,
            "date": target_date.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur mise à jour stats: {str(e)}")

@router.get("/system/health")
async def system_health(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Vérification de l'état du système
    """
    try:
        # Test base de données
        db_test = db.execute("SELECT 1").scalar()
        
        # Statistiques système
        total_users = db.query(User).count()
        active_subs = db.query(Subscription).filter(
            Subscription.is_active == True,
            Subscription.end_date > datetime.utcnow()
        ).count()
        
        return {
            "success": True,
            "system_status": "healthy",
            "database": "connected" if db_test else "disconnected",
            "stats": {
                "total_users": total_users,
                "active_subscriptions": active_subs,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "system_status": "unhealthy",
            "error": str(e)
        }