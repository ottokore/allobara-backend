"""
Service administrateur AlloBara
Gestion du dashboard, statistiques, wallet et retraits
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
import logging

from app.models.admin import AdminWallet, WithdrawalRequest, DailyStats, WithdrawalStatus, TransactionType, PaymentProvider
from app.models.user import User, UserRole
from app.models.subscription import Subscription, SubscriptionStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

class AdminService:
    """Service pour toutes les opérations admin"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================
    # DASHBOARD PRINCIPAL
    # =========================================
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Récupérer toutes les statistiques pour le dashboard admin
        Retourne les KPIs principaux
        """
        try:
            today = date.today()
            
            # Stats d'inscriptions
            registration_stats = self._get_registration_stats()
            
            # Stats de revenus
            revenue_stats = self._get_revenue_stats()
            
            # Stats du wallet
            wallet_stats = self._get_wallet_stats()
            
            # Stats générales
            general_stats = self._get_general_stats()
            
            # Activité récente
            recent_activity = self._get_recent_activity()
            
            return {
                "date": today.isoformat(),
                "registrations": registration_stats,
                "revenue": revenue_stats,
                "wallet": wallet_stats,
                "general": general_stats,
                "recent_activity": recent_activity,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur dashboard stats: {e}")
            return self._get_fallback_dashboard()
    
    def _get_registration_stats(self) -> Dict[str, Any]:
        """Statistiques d'inscriptions"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        last_month_start = today.replace(day=1) - timedelta(days=1)
        last_month_start = last_month_start.replace(day=1)
        
        # Inscriptions aujourd'hui
        today_count = self.db.query(User).filter(
            func.date(User.created_at) == today,
            User.role == UserRole.PROVIDER
        ).count()
        
        # Inscriptions hier (pour comparaison)
        yesterday_count = self.db.query(User).filter(
            func.date(User.created_at) == yesterday,
            User.role == UserRole.PROVIDER
        ).count()
        
        # Ce mois
        month_count = self.db.query(User).filter(
            func.date(User.created_at) >= today.replace(day=1),
            User.role == UserRole.PROVIDER
        ).count()
        
        # Mois dernier
        last_month_count = self.db.query(User).filter(
            and_(
                func.date(User.created_at) >= last_month_start,
                func.date(User.created_at) < today.replace(day=1)
            ),
            User.role == UserRole.PROVIDER
        ).count()
        
        # Total
        total_count = self.db.query(User).filter(
            User.role == UserRole.PROVIDER
        ).count()
        
        # Calcul des variations
        today_vs_yesterday = self._calculate_percentage_change(today_count, yesterday_count)
        month_vs_last_month = self._calculate_percentage_change(month_count, last_month_count)
        
        return {
            "today": today_count,
            "yesterday": yesterday_count,
            "this_month": month_count,
            "last_month": last_month_count,
            "total": total_count,
            "today_change": today_vs_yesterday,
            "month_change": month_vs_last_month
        }
    
    def _get_revenue_stats(self) -> Dict[str, Any]:
        """Statistiques de revenus"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        month_start = today.replace(day=1)
        last_month_start = month_start - timedelta(days=1)
        last_month_start = last_month_start.replace(day=1)
        
        # Revenus aujourd'hui - somme des paiements d'abonnements
        today_revenue = self.db.query(func.sum(Subscription.amount_paid)).filter(
            func.date(Subscription.paid_at) == today,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).scalar() or 0.0
        
        # Revenus hier
        yesterday_revenue = self.db.query(func.sum(Subscription.amount_paid)).filter(
            func.date(Subscription.paid_at) == yesterday,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).scalar() or 0.0
        
        # Ce mois
        month_revenue = self.db.query(func.sum(Subscription.amount_paid)).filter(
            func.date(Subscription.paid_at) >= month_start,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).scalar() or 0.0
        
        # Mois dernier
        last_month_revenue = self.db.query(func.sum(Subscription.amount_paid)).filter(
            and_(
                func.date(Subscription.paid_at) >= last_month_start,
                func.date(Subscription.paid_at) < month_start
            ),
            Subscription.status == SubscriptionStatus.ACTIVE
        ).scalar() or 0.0
        
        # Total
        total_revenue = self.db.query(func.sum(Subscription.amount_paid)).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).scalar() or 0.0
        
        # Variations
        today_change = self._calculate_percentage_change(today_revenue, yesterday_revenue)
        month_change = self._calculate_percentage_change(month_revenue, last_month_revenue)
        
        return {
            "today": today_revenue,
            "yesterday": yesterday_revenue,
            "this_month": month_revenue,
            "last_month": last_month_revenue,
            "total": total_revenue,
            "today_change": today_change,
            "month_change": month_change,
            "formatted": {
                "today": f"{int(today_revenue):,} FCFA".replace(",", " "),
                "this_month": f"{int(month_revenue):,} FCFA".replace(",", " "),
                "total": f"{int(total_revenue):,} FCFA".replace(",", " ")
            }
        }
    
    def _get_wallet_stats(self) -> Dict[str, Any]:
        """Statistiques du wallet admin"""
        wallet = self._get_or_create_admin_wallet()
        
        # Retraits en attente
        pending_withdrawals = self.db.query(WithdrawalRequest).filter(
            WithdrawalRequest.status == WithdrawalStatus.PENDING
        ).count()
        
        pending_amount = self.db.query(func.sum(WithdrawalRequest.amount)).filter(
            WithdrawalRequest.status == WithdrawalStatus.PENDING
        ).scalar() or 0.0
        
        return {
            "total_balance": wallet.total_balance,
            "available_balance": wallet.available_balance,
            "pending_balance": wallet.pending_balance,
            "withdrawn_balance": wallet.withdrawn_balance,
            "pending_withdrawals_count": pending_withdrawals,
            "pending_withdrawals_amount": pending_amount,
            "can_withdraw": wallet.can_withdraw,
            "formatted": {
                "total": wallet.formatted_total_balance,
                "available": wallet.formatted_available_balance,
                "pending": f"{int(pending_amount):,} FCFA".replace(",", " ")
            }
        }
    
    def _get_general_stats(self) -> Dict[str, Any]:
        """Statistiques générales"""
        # Utilisateurs actifs (connectés dans les 30 derniers jours)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users = self.db.query(User).filter(
            User.last_login >= thirty_days_ago,
            User.role == UserRole.PROVIDER,
            User.is_active == True
        ).count()
        
        # Abonnements actifs
        active_subscriptions = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        
        # Utilisateurs vérifiés
        verified_users = self.db.query(User).filter(
            User.is_verified == True,
            User.role == UserRole.PROVIDER
        ).count()
        
        # Taux de conversion (essai -> abonnement payé)
        trial_users = self.db.query(User).filter(
            User.role == UserRole.PROVIDER
        ).count()
        
        conversion_rate = (active_subscriptions / trial_users * 100) if trial_users > 0 else 0
        
        return {
            "active_users": active_users,
            "active_subscriptions": active_subscriptions,
            "verified_users": verified_users,
            "total_users": trial_users,
            "conversion_rate": round(conversion_rate, 1)
        }
    
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """Activité récente (10 derniers événements)"""
        activities = []
        
        # Nouvelles inscriptions (5 dernières)
        recent_users = self.db.query(User).filter(
            User.role == UserRole.PROVIDER
        ).order_by(desc(User.created_at)).limit(5).all()
        
        for user in recent_users:
            activities.append({
                "type": "registration",
                "message": f"Nouvel utilisateur: {user.display_name}",
                "timestamp": user.created_at.isoformat(),
                "user_id": user.id
            })
        
        # Nouveaux abonnements (5 derniers)
        recent_subscriptions = self.db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).order_by(desc(Subscription.paid_at)).limit(5).all()
        
        for sub in recent_subscriptions:
            if sub.user and sub.paid_at:
                activities.append({
                    "type": "subscription",
                    "message": f"Nouveau paiement: {sub.user.display_name} - {sub.plan}",
                    "timestamp": sub.paid_at.isoformat(),
                    "amount": sub.amount_paid,
                    "user_id": sub.user_id
                })
        
        # Trier par timestamp décroissant
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return activities[:10]  # Garder seulement les 10 plus récents
    
    # =========================================
    # GESTION DU WALLET
    # =========================================
    
    def get_wallet_balance(self) -> Dict[str, Any]:
        """Récupérer le solde du wallet admin"""
        wallet = self._get_or_create_admin_wallet()
        
        return {
            "total_balance": wallet.total_balance,
            "available_balance": wallet.available_balance,
            "pending_balance": wallet.pending_balance,
            "withdrawn_balance": wallet.withdrawn_balance,
            "formatted_total": wallet.formatted_total_balance,
            "formatted_available": wallet.formatted_available_balance,
            "can_withdraw": wallet.can_withdraw,
            "last_updated": wallet.last_updated.isoformat() if wallet.last_updated else None
        }
    
    def request_withdrawal(self, amount: float, provider: str, destination_number: str, 
                         destination_name: str = None, notes: str = None) -> Dict[str, Any]:
        """Demander un retrait d'argent"""
        try:
            # Vérifications
            if amount <= 0:
                return {"success": False, "error": "Le montant doit être positif"}
            
            wallet = self._get_or_create_admin_wallet()
            
            if amount > wallet.available_balance:
                return {
                    "success": False, 
                    "error": f"Solde insuffisant. Disponible: {wallet.formatted_available_balance}"
                }
            
            # Valider le provider
            try:
                payment_provider = PaymentProvider(provider.lower())
            except ValueError:
                return {"success": False, "error": "Provider de paiement invalide"}
            
            # Réserver le montant dans le wallet
            if not wallet.reserve_for_withdrawal(amount):
                return {"success": False, "error": "Impossible de réserver le montant"}
            
            # Créer la demande de retrait
            withdrawal = WithdrawalRequest(
                reference=WithdrawalRequest.generate_reference(),
                amount=amount,
                provider=payment_provider,
                destination_number=destination_number,
                destination_name=destination_name,
                notes=notes,
                status=WithdrawalStatus.PENDING
            )
            
            self.db.add(withdrawal)
            self.db.commit()
            
            logger.info(f"Demande de retrait créée: {withdrawal.reference} - {amount} FCFA")
            
            return {
                "success": True,
                "withdrawal_id": withdrawal.id,
                "reference": withdrawal.reference,
                "amount": amount,
                "formatted_amount": withdrawal.formatted_amount,
                "status": withdrawal.status_display,
                "message": f"Demande de retrait {withdrawal.reference} créée avec succès"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur demande de retrait: {e}")
            return {"success": False, "error": "Erreur lors de la demande de retrait"}
    
    def get_withdrawal_history(self, limit: int = 50, status: str = None) -> List[Dict[str, Any]]:
        """Historique des demandes de retrait"""
        try:
            query = self.db.query(WithdrawalRequest).order_by(desc(WithdrawalRequest.created_at))
            
            if status:
                try:
                    withdrawal_status = WithdrawalStatus(status)
                    query = query.filter(WithdrawalRequest.status == withdrawal_status)
                except ValueError:
                    pass  # Ignorer les statuts invalides
            
            withdrawals = query.limit(limit).all()
            
            return [
                {
                    "id": w.id,
                    "reference": w.reference,
                    "amount": w.amount,
                    "formatted_amount": w.formatted_amount,
                    "provider": w.provider.value,
                    "destination_number": w.destination_number,
                    "destination_name": w.destination_name,
                    "status": w.status.value,
                    "status_display": w.status_display,
                    "created_at": w.created_at.isoformat(),
                    "processed_at": w.processed_at.isoformat() if w.processed_at else None,
                    "completed_at": w.completed_at.isoformat() if w.completed_at else None,
                    "error_message": w.error_message,
                    "notes": w.notes,
                    "can_be_cancelled": w.can_be_cancelled,
                    "processing_time_minutes": w.processing_time_minutes
                }
                for w in withdrawals
            ]
            
        except Exception as e:
            logger.error(f"Erreur historique retraits: {e}")
            return []
    
    def simulate_withdrawal_success(self, withdrawal_id: int, provider_reference: str = None) -> Dict[str, Any]:
        """Simuler le succès d'un retrait (pour demo/test)"""
        try:
            withdrawal = self.db.query(WithdrawalRequest).filter(
                WithdrawalRequest.id == withdrawal_id
            ).first()
            
            if not withdrawal:
                return {"success": False, "error": "Demande de retrait introuvable"}
            
            if withdrawal.status != WithdrawalStatus.PENDING:
                return {"success": False, "error": "La demande n'est plus en attente"}
            
            # Finaliser le retrait
            ref = provider_reference or f"WAVE_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            withdrawal.complete(provider_reference=ref, net_amount=withdrawal.amount)
            
            # Mettre à jour le wallet
            wallet = self._get_or_create_admin_wallet()
            wallet.complete_withdrawal(withdrawal.amount)
            
            self.db.commit()
            
            logger.info(f"Retrait simulé avec succès: {withdrawal.reference}")
            
            return {
                "success": True,
                "message": f"Retrait {withdrawal.reference} terminé avec succès",
                "provider_reference": ref,
                "net_amount": withdrawal.amount
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur simulation retrait: {e}")
            return {"success": False, "error": "Erreur lors de la simulation"}
    
    # =========================================
    # STATISTIQUES DÉTAILLÉES
    # =========================================
    
    def get_registration_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Tendances d'inscriptions sur X jours"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Requête pour obtenir les inscriptions par jour
            daily_registrations = self.db.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                and_(
                    func.date(User.created_at) >= start_date,
                    func.date(User.created_at) <= end_date,
                    User.role == UserRole.PROVIDER
                )
            ).group_by(func.date(User.created_at)).all()
            
            # Créer un dictionnaire pour un accès rapide
            registration_dict = {str(item.date): item.count for item in daily_registrations}
            
            # Générer toutes les dates de la période
            trends = []
            current_date = start_date
            while current_date <= end_date:
                trends.append({
                    "date": current_date.isoformat(),
                    "formatted_date": current_date.strftime("%d/%m"),
                    "registrations": registration_dict.get(str(current_date), 0)
                })
                current_date += timedelta(days=1)
            
            return trends
            
        except Exception as e:
            logger.error(f"Erreur tendances inscriptions: {e}")
            return []
    
    def get_revenue_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Tendances de revenus sur X jours"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            daily_revenue = self.db.query(
                func.date(Subscription.paid_at).label('date'),
                func.sum(Subscription.amount_paid).label('revenue'),
                func.count(Subscription.id).label('count')
            ).filter(
                and_(
                    func.date(Subscription.paid_at) >= start_date,
                    func.date(Subscription.paid_at) <= end_date,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            ).group_by(func.date(Subscription.paid_at)).all()
            
            revenue_dict = {str(item.date): {"revenue": float(item.revenue), "count": item.count} for item in daily_revenue}
            
            trends = []
            current_date = start_date
            while current_date <= end_date:
                data = revenue_dict.get(str(current_date), {"revenue": 0.0, "count": 0})
                trends.append({
                    "date": current_date.isoformat(),
                    "formatted_date": current_date.strftime("%d/%m"),
                    "revenue": data["revenue"],
                    "formatted_revenue": f"{int(data['revenue']):,} FCFA".replace(",", " "),
                    "transactions": data["count"]
                })
                current_date += timedelta(days=1)
            
            return trends
            
        except Exception as e:
            logger.error(f"Erreur tendances revenus: {e}")
            return []
    
    # =========================================
    # GESTION DES UTILISATEURS
    # =========================================
    
    def get_users_list(self, page: int = 1, limit: int = 50, search: str = None, 
                      status: str = None) -> Dict[str, Any]:
        """Liste paginée des utilisateurs"""
        try:
            query = self.db.query(User).filter(User.role == UserRole.PROVIDER)
            
            # Recherche
            if search:
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        User.first_name.ilike(search_term),
                        User.last_name.ilike(search_term),
                        User.phone.ilike(search_term),
                        User.profession.ilike(search_term)
                    )
                )
            
            # Filtre par statut
            if status == "active":
                query = query.filter(User.is_active == True)
            elif status == "blocked":
                query = query.filter(User.is_blocked == True)
            elif status == "verified":
                query = query.filter(User.is_verified == True)
            
            # Total
            total = query.count()
            
            # Pagination
            offset = (page - 1) * limit
            users = query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
            
            users_data = []
            for user in users:
                users_data.append({
                    "id": user.id,
                    "full_name": user.full_name,
                    "display_name": user.display_name,
                    "phone": user.formatted_phone,
                    "profession": user.profession,
                    "city": user.city,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "is_blocked": user.is_blocked,
                    "has_subscription": user.has_active_subscription,
                    "profile_completion": user.profile_completion_percentage,
                    "created_at": user.created_at.isoformat(),
                    "last_login": user.last_login.isoformat() if user.last_login else None
                })
            
            return {
                "users": users_data,
                "pagination": {
                    "current_page": page,
                    "per_page": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
            
        except Exception as e:
            logger.error(f"Erreur liste utilisateurs: {e}")
            return {"users": [], "pagination": {"current_page": 1, "per_page": limit, "total": 0, "pages": 0}}
    
    def block_user(self, user_id: int, reason: str = None) -> Dict[str, Any]:
        """Bloquer un utilisateur"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {"success": False, "error": "Utilisateur introuvable"}
            
            if user.is_blocked:
                return {"success": False, "error": "Utilisateur déjà bloqué"}
            
            user.is_blocked = True
            user.blocked_reason = reason or "Bloqué par l'administrateur"
            user.is_active = False
            
            self.db.commit()
            
            logger.info(f"Utilisateur bloqué: {user.id} - {user.full_name}")
            
            return {
                "success": True,
                "message": f"Utilisateur {user.display_name} bloqué avec succès"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur blocage utilisateur: {e}")
            return {"success": False, "error": "Erreur lors du blocage"}
    
    def unblock_user(self, user_id: int) -> Dict[str, Any]:
        """Débloquer un utilisateur"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return {"success": False, "error": "Utilisateur introuvable"}
            
            if not user.is_blocked:
                return {"success": False, "error": "Utilisateur non bloqué"}
            
            user.is_blocked = False
            user.blocked_reason = None
            user.is_active = True
            
            self.db.commit()
            
            logger.info(f"Utilisateur débloqué: {user.id} - {user.full_name}")
            
            return {
                "success": True,
                "message": f"Utilisateur {user.display_name} débloqué avec succès"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur déblocage utilisateur: {e}")
            return {"success": False, "error": "Erreur lors du déblocage"}
    
    # =========================================
    # MÉTHODES UTILITAIRES PRIVÉES
    # =========================================
    
    def _get_or_create_admin_wallet(self) -> AdminWallet:
        """Récupérer ou créer le wallet admin"""
        wallet = self.db.query(AdminWallet).first()
        
        if not wallet:
            wallet = AdminWallet()
            self.db.add(wallet)
            self.db.commit()
            logger.info("Wallet admin créé")
        
        return wallet
    
    def _calculate_percentage_change(self, current: float, previous: float) -> float:
        """Calculer le pourcentage de variation"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return round(((current - previous) / previous) * 100, 1)
    
    def _get_fallback_dashboard(self) -> Dict[str, Any]:
        """Dashboard de fallback en cas d'erreur"""
        return {
            "date": date.today().isoformat(),
            "registrations": {
                "today": 0, "yesterday": 0, "this_month": 0, 
                "last_month": 0, "total": 0, "today_change": 0, "month_change": 0
            },
            "revenue": {
                "today": 0.0, "yesterday": 0.0, "this_month": 0.0, 
                "last_month": 0.0, "total": 0.0, "today_change": 0, "month_change": 0,
                "formatted": {"today": "0 FCFA", "this_month": "0 FCFA", "total": "0 FCFA"}
            },
            "wallet": {
                "total_balance": 0.0, "available_balance": 0.0, "pending_balance": 0.0,
                "pending_withdrawals_count": 0, "can_withdraw": False,
                "formatted": {"total": "0 FCFA", "available": "0 FCFA", "pending": "0 FCFA"}
            },
            "general": {
                "active_users": 0, "active_subscriptions": 0, "verified_users": 0,
                "total_users": 0, "conversion_rate": 0.0
            },
            "recent_activity": [],
            "last_updated": datetime.utcnow().isoformat(),
            "error": "Données de fallback - Erreur lors du chargement des statistiques"
        }
    
    # =========================================
    # MAINTENANCE ET TÂCHES
    # =========================================
    
    def update_daily_stats(self, target_date: date = None) -> Dict[str, Any]:
        """Mettre à jour les statistiques journalières"""
        try:
            if not target_date:
                target_date = date.today()
            
            # Récupérer ou créer l'entrée DailyStats
            stats = self.db.query(DailyStats).filter(DailyStats.date == target_date).first()
            
            if not stats:
                stats = DailyStats(date=target_date)
                self.db.add(stats)
            
            # Calculer les stats pour cette date
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            # Nouvelles inscriptions
            stats.new_users = self.db.query(User).filter(
                and_(
                    User.created_at >= start_datetime,
                    User.created_at <= end_datetime,
                    User.role == UserRole.PROVIDER
                )
            ).count()
            
            # Nouveaux abonnements et revenus
            subscriptions = self.db.query(Subscription).filter(
                and_(
                    Subscription.paid_at >= start_datetime,
                    Subscription.paid_at <= end_datetime,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            ).all()
            
            stats.new_subscriptions = len(subscriptions)
            stats.total_revenue = sum(sub.amount_paid for sub in subscriptions)
            stats.subscription_revenue = stats.total_revenue
            
            # Répartition par plan
            for sub in subscriptions:
                if sub.plan == "monthly":
                    stats.monthly_subscriptions += 1
                    stats.monthly_revenue += sub.amount_paid
                elif sub.plan == "quarterly":
                    stats.quarterly_subscriptions += 1
                    stats.quarterly_revenue += sub.amount_paid
                elif sub.plan == "biannual":
                    stats.biannual_subscriptions += 1
                    stats.biannual_revenue += sub.amount_paid
                elif sub.plan == "annual":
                    stats.annual_subscriptions += 1
                    stats.annual_revenue += sub.amount_paid
            
            # Mettre à jour le wallet admin avec les revenus du jour
            wallet = self._get_or_create_admin_wallet()
            wallet.today_revenue = stats.total_revenue
            wallet.total_balance += stats.total_revenue
            wallet.available_balance += stats.total_revenue
            
            self.db.commit()
            
            logger.info(f"Statistiques mises à jour pour {target_date}: {stats.new_users} inscriptions, {stats.total_revenue} FCFA")
            
            return {
                "success": True,
                "date": target_date.isoformat(),
                "new_users": stats.new_users,
                "new_subscriptions": stats.new_subscriptions,
                "total_revenue": stats.total_revenue,
                "formatted_revenue": f"{int(stats.total_revenue):,} FCFA".replace(",", " ")
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur mise à jour stats journalières: {e}")
            return {"success": False, "error": "Erreur lors de la mise à jour des statistiques"}
    
    def get_system_health(self) -> Dict[str, Any]:
        """Vérifier la santé du système"""
        try:
            # Test de base de données
            db_test = self.db.execute("SELECT 1").fetchone()
            db_healthy = db_test[0] == 1
            
            # Nombre d'utilisateurs
            total_users = self.db.query(User).count()
            
            # Nombre d'abonnements actifs
            active_subs = self.db.query(Subscription).filter(
                Subscription.status == SubscriptionStatus.ACTIVE
            ).count()
            
            # Wallet status
            wallet = self._get_or_create_admin_wallet()
            wallet_healthy = wallet.total_balance >= 0
            
            # Retraits en attente
            pending_withdrawals = self.db.query(WithdrawalRequest).filter(
                WithdrawalRequest.status == WithdrawalStatus.PENDING
            ).count()
            
            overall_health = db_healthy and wallet_healthy
            
            return {
                "overall_health": "healthy" if overall_health else "degraded",
                "database": {
                    "status": "healthy" if db_healthy else "error",
                    "total_users": total_users,
                    "active_subscriptions": active_subs
                },
                "wallet": {
                    "status": "healthy" if wallet_healthy else "error",
                    "balance": wallet.total_balance,
                    "pending_withdrawals": pending_withdrawals
                },
                "last_check": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur vérification santé système: {e}")
            return {
                "overall_health": "error",
                "database": {"status": "error"},
                "wallet": {"status": "error"},
                "error": str(e),
                "last_check": datetime.utcnow().isoformat()
            }