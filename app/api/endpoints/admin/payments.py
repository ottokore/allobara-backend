"""
Endpoints Admin - Gestion des paiements
Voir les transactions CinetPay, statistiques
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.db.database import get_db
from app.api.deps.auth import get_current_admin_user
from app.models.user import User
from app.models.payment import Payment, PaymentStatus
from app.services.cinetpay_service import CinetPayService

router = APIRouter()

# =========================================
# ENDPOINTS - LISTE DES PAIEMENTS
# =========================================

@router.get("/")
async def get_all_payments(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="pending, success, failed")
):
    """
    Liste de tous les paiements avec pagination
    
    Query params:
    - page: Numéro de page (défaut: 1)
    - per_page: Résultats par page (défaut: 20, max: 100)
    - status: Filtrer par statut (optionnel)
    """
    try:
        offset = (page - 1) * per_page
        
        # Query de base
        query = db.query(Payment)
        
        # Filtre par statut
        if status:
            try:
                payment_status = PaymentStatus(status)
                query = query.filter(Payment.status == payment_status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Statut invalide. Valeurs possibles: pending, success, failed, cancelled, expired"
                )
        
        # Total
        total = query.count()
        
        # Récupérer les paiements
        payments = query.order_by(
            Payment.created_at.desc()
        ).offset(offset).limit(per_page).all()
        
        payments_data = []
        for payment in payments:
            payments_data.append({
                **payment.to_dict(),
                "user": {
                    "id": payment.user.id,
                    "name": f"{payment.user.first_name} {payment.user.last_name}",
                    "phone": payment.user.phone
                } if payment.user else None
            })
        
        return {
            "success": True,
            "data": payments_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération paiements: {str(e)}"
        )

@router.get("/{payment_id}")
async def get_payment_details(
    payment_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Détails complets d'un paiement
    """
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment:
            raise HTTPException(
                status_code=404,
                detail="Paiement introuvable"
            )
        
        # Informations utilisateur
        user_info = None
        if payment.user:
            user_info = {
                "id": payment.user.id,
                "name": f"{payment.user.first_name} {payment.user.last_name}",
                "phone": payment.user.phone,
                "email": payment.user.email,
                "city": payment.user.city
            }
        
        # Informations abonnement
        subscription_info = None
        if payment.subscription:
            subscription_info = {
                "id": payment.subscription.id,
                "plan": payment.subscription.plan.value,
                "status": payment.subscription.status.value,
                "end_date": payment.subscription.end_date.isoformat()
            }
        
        return {
            "success": True,
            "data": {
                "payment": payment.to_dict(),
                "user": user_info,
                "subscription": subscription_info,
                "provider_response": payment.provider_response,
                "webhook_data": payment.webhook_data
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur détails paiement: {str(e)}"
        )

# =========================================
# ENDPOINTS - STATISTIQUES
# =========================================

@router.get("/stats/summary")
async def get_payments_summary(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365)
):
    """
    Résumé des paiements sur une période
    
    Query param:
    - days: Nombre de jours (défaut: 30)
    """
    try:
        from sqlalchemy import func
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total des paiements réussis
        total_success = db.query(
            func.sum(Payment.amount)
        ).filter(
            Payment.status == PaymentStatus.SUCCESS,
            Payment.created_at >= start_date
        ).scalar() or 0
        
        # Nombre de paiements par statut
        stats_by_status = db.query(
            Payment.status,
            func.count(Payment.id),
            func.sum(Payment.amount)
        ).filter(
            Payment.created_at >= start_date
        ).group_by(Payment.status).all()
        
        # Nombre de paiements par méthode
        stats_by_method = db.query(
            Payment.payment_method,
            func.count(Payment.id)
        ).filter(
            Payment.created_at >= start_date,
            Payment.status == PaymentStatus.SUCCESS
        ).group_by(Payment.payment_method).all()
        
        # Évolution quotidienne
        daily_payments = db.query(
            func.date(Payment.created_at).label('date'),
            func.count(Payment.id).label('count'),
            func.sum(Payment.amount).label('amount')
        ).filter(
            Payment.created_at >= start_date,
            Payment.status == PaymentStatus.SUCCESS
        ).group_by(func.date(Payment.created_at)).all()
        
        return {
            "success": True,
            "data": {
                "period_days": days,
                "total_revenue": float(total_success),
                "by_status": [
                    {
                        "status": status.value,
                        "count": count,
                        "amount": float(amount or 0)
                    }
                    for status, count, amount in stats_by_status
                ],
                "by_method": [
                    {
                        "method": method.value if method else "unknown",
                        "count": count
                    }
                    for method, count in stats_by_method
                ],
                "daily": [
                    {
                        "date": date.isoformat(),
                        "count": count,
                        "amount": float(amount or 0)
                    }
                    for date, count, amount in daily_payments
                ]
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur statistiques paiements: {str(e)}"
        )

@router.get("/stats/recent")
async def get_recent_payments(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Paiements réussis récents
    
    Query param:
    - limit: Nombre de résultats (défaut: 10, max: 50)
    """
    try:
        payments = db.query(Payment).filter(
            Payment.status == PaymentStatus.SUCCESS
        ).order_by(
            Payment.completed_at.desc()
        ).limit(limit).all()
        
        payments_data = []
        for payment in payments:
            payments_data.append({
                "id": payment.id,
                "transaction_id": payment.transaction_id,
                "amount": payment.amount,
                "formatted_amount": payment.formatted_amount,
                "payment_method": payment.payment_method.value if payment.payment_method else None,
                "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
                "user": {
                    "id": payment.user.id,
                    "name": f"{payment.user.first_name} {payment.user.last_name}",
                    "phone": payment.user.phone
                } if payment.user else None
            })
        
        return {
            "success": True,
            "data": payments_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur paiements récents: {str(e)}"
        )

# =========================================
# ENDPOINTS - VÉRIFICATION
# =========================================

@router.post("/{transaction_id}/verify")
async def verify_payment(
    transaction_id: str,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Vérifier le statut d'un paiement auprès de CinetPay
    """
    try:
        service = CinetPayService(db)
        
        result = service.check_payment_status(transaction_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur vérification paiement: {str(e)}"
        )

# =========================================
# ENDPOINTS - DASHBOARD
# =========================================

@router.get("/dashboard/overview")
async def get_payments_dashboard(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Dashboard récapitulatif des paiements
    """
    try:
        from sqlalchemy import func
        
        # Aujourd'hui
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_revenue = db.query(
            func.sum(Payment.amount)
        ).filter(
            Payment.status == PaymentStatus.SUCCESS,
            Payment.created_at >= today_start
        ).scalar() or 0
        
        today_count = db.query(
            func.count(Payment.id)
        ).filter(
            Payment.status == PaymentStatus.SUCCESS,
            Payment.created_at >= today_start
        ).scalar() or 0
        
        # Ce mois
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        month_revenue = db.query(
            func.sum(Payment.amount)
        ).filter(
            Payment.status == PaymentStatus.SUCCESS,
            Payment.created_at >= month_start
        ).scalar() or 0
        
        # Paiements en attente
        pending_count = db.query(
            func.count(Payment.id)
        ).filter(
            Payment.status == PaymentStatus.PENDING
        ).scalar() or 0
        
        # Taux de succès (30 derniers jours)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        total_attempts = db.query(func.count(Payment.id)).filter(
            Payment.created_at >= thirty_days_ago
        ).scalar() or 0
        
        successful_payments = db.query(func.count(Payment.id)).filter(
            Payment.created_at >= thirty_days_ago,
            Payment.status == PaymentStatus.SUCCESS
        ).scalar() or 0
        
        success_rate = (successful_payments / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "success": True,
            "data": {
                "today": {
                    "revenue": float(today_revenue),
                    "count": today_count
                },
                "this_month": {
                    "revenue": float(month_revenue)
                },
                "pending": {
                    "count": pending_count
                },
                "success_rate": {
                    "percentage": round(success_rate, 1),
                    "period": "30 derniers jours"
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur dashboard paiements: {str(e)}"
        )