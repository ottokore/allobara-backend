"""
Service abonnements AlloBara
Gestion des plans, période d'essai gratuite, paiements
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.user import User
from app.models.subscription import (
    Subscription, SubscriptionPlan, SubscriptionStatus, PaymentStatus
)
from app.models.admin import AdminWallet, DailyStats
from app.core.config import settings
from app.services.payment import PaymentService
from app.services.cinetpay_service import CinetPayService
from app.services.sms import SMSService

class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
        self.payment_service = PaymentService()
        self.sms_service = SMSService()
        self.cinetpay_service = CinetPayService(db)  # 🆕 AJOUT
    
    def create_trial_subscription(self, user_id: int) -> Dict[str, Any]:
        """
        Créer un abonnement d'essai gratuit de 30 jours
        """
        try:
            # Vérifier si l'utilisateur a déjà un abonnement
            existing_sub = self.db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if existing_sub:
                return {
                    "success": False,
                    "message": "L'utilisateur a déjà un abonnement"
                }
            
            # Calculer les dates d'essai
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=settings.FREE_TRIAL_DAYS)
            
            # Créer l'abonnement d'essai
            trial_subscription = Subscription(
                user_id=user_id,
                plan=SubscriptionPlan.MONTHLY,  # Plan par défaut pour l'essai
                status=SubscriptionStatus.TRIAL,
                price=0.0,
                start_date=start_date,
                end_date=end_date,
                trial_start_date=start_date,
                trial_end_date=end_date,
                payment_status=PaymentStatus.SUCCESS,  # Essai = "payé"
                auto_renewal=False
            )
            
            self.db.add(trial_subscription)
            self.db.commit()
            self.db.refresh(trial_subscription)
            
            return {
                "success": True,
                "message": "Période d'essai gratuite activée",
                "data": {
                    "subscription_id": trial_subscription.id,
                    "plan": trial_subscription.plan.value,
                    "status": trial_subscription.status.value,
                    "days_remaining": trial_subscription.days_remaining,
                    "end_date": trial_subscription.end_date.isoformat(),
                    "is_trial": True
                }
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur create_trial_subscription: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la création de la période d'essai"
            }
    
    def get_subscription_plans(self) -> List[Dict]:
        """
        Récupérer tous les plans d'abonnement avec nouveaux prix
        """
        plans = [
            {
                "id": "monthly",
                "name": "Mensuel",
                "duration_months": 1,
                "price": 2100,  # +100 FCFA
                "original_price": 2100,
                "description": "Parfait pour commencer",
                "features": [
                    "Profil visible 30 jours",
                    "Portfolio illimité", 
                    "Contact direct clients",
                    "Support client"
                ],
                "savings": 0,
                "is_popular": False
            },
            {
                "id": "quarterly",
                "name": "Trimestriel", 
                "duration_months": 3,
                "price": 5100,  # +100 FCFA
                "original_price": 6300,  # 3 x 2100
                "description": "Économisez 19%",
                "features": [
                    "Profil visible 3 mois",
                    "Portfolio illimité",
                    "Contact direct clients", 
                    "Support prioritaire",
                    "Statistiques détaillées"
                ],
                "savings": 1200,
                "is_popular": False
            },
            {
                "id": "biannual",
                "name": "Semestriel",
                "duration_months": 6, 
                "price": 9100,  # +100 FCFA
                "original_price": 12600,  # 6 x 2100
                "description": "Économisez 28%",
                "features": [
                    "Profil visible 6 mois",
                    "Portfolio illimité",
                    "Contact direct clients",
                    "Support prioritaire", 
                    "Statistiques avancées",
                    "Badge prestataire expérimenté"
                ],
                "savings": 3500,
                "is_popular": True
            },
            {
                "id": "annual",
                "name": "Annuel",
                "duration_months": 12,
                "price": 16100,  # +100 FCFA
                "original_price": 25200,  # 12 x 2100
                "description": "Meilleure offre - Économisez 36%",
                "features": [
                    "Profil visible 1 an",
                    "Portfolio illimité",
                    "Contact direct clients",
                    "Support VIP",
                    "Statistiques complètes", 
                    "Badge prestataire premium",
                    "Formation en ligne gratuite",
                    "Mise en avant occasionnelle"
                ],
                "savings": 9100,
                "is_popular": False,
                "is_best_value": True
            }
        ]
        
        return plans
    
    def get_user_subscription_status(self, user_id: int) -> Dict[str, Any]:
        """
        Récupérer le statut d'abonnement d'un utilisateur
        """
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if not subscription:
                return {
                    "has_subscription": False,
                    "status": "none",
                    "message": "Aucun abonnement"
                }
            
            return {
                "has_subscription": True,
                "subscription_id": subscription.id,
                "plan": subscription.plan.value,
                "plan_display": subscription.plan_display_name,
                "status": subscription.status.value,
                "status_display": subscription.status_display_name,
                "is_active": subscription.is_active,
                "is_trial": subscription.is_trial,
                "price": subscription.price,
                "formatted_price": subscription.formatted_price,
                "days_remaining": subscription.days_remaining,
                "hours_remaining": subscription.hours_remaining,
                "is_expiring_soon": subscription.is_expiring_soon,
                "is_expiring_today": subscription.is_expiring_today,
                "start_date": subscription.start_date.isoformat(),
                "end_date": subscription.end_date.isoformat(),
                "progress_percentage": subscription.progress_percentage,
                "auto_renewal": subscription.auto_renewal,
                "can_renew": subscription.can_renew(),
                "payment_status": subscription.payment_status.value,
                "savings_vs_monthly": subscription.savings_vs_monthly
            }
            
        except Exception as e:
            print(f"Erreur get_user_subscription_status: {e}")
            return {
                "has_subscription": False,
                "status": "error",
                "message": "Erreur lors de la récupération"
            }
    
    async def create_subscription(
        self,
        user_id: int,
        plan: SubscriptionPlan,
        payment_method: str = "wave",
        referral_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Créer un nouvel abonnement payant
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    "success": False,
                    "message": "Utilisateur introuvable"
                }
            
            # Récupérer le prix du plan
            plan_price = Subscription.get_plan_price(plan)
            if plan_price == 0:
                return {
                    "success": False,
                    "message": "Plan d'abonnement invalide"
                }
            
            # Appliquer la réduction de parrainage si applicable
            discount = 0
            if referral_code and plan == SubscriptionPlan.MONTHLY:
                discount = 500  # 500 FCFA de réduction pour le premier abonnement
            
            final_price = max(0, plan_price - discount)
            
            # Calculer les dates
            start_date = datetime.utcnow()
            duration_months = {
                SubscriptionPlan.MONTHLY: 1,
                SubscriptionPlan.QUARTERLY: 3,
                SubscriptionPlan.BIANNUAL: 6,
                SubscriptionPlan.ANNUAL: 12
            }[plan]
            
            end_date = start_date + timedelta(days=duration_months * 30)
            
            # Créer l'abonnement
            new_subscription = Subscription(
                user_id=user_id,
                plan=plan,
                status=SubscriptionStatus.PENDING,
                price=final_price,
                original_price=plan_price,
                discount_amount=discount,
                start_date=start_date,
                end_date=end_date,
                payment_method=payment_method,
                payment_status=PaymentStatus.PENDING,
                is_from_referral=bool(referral_code),
                referral_discount=discount
            )
            
            # Gérer l'abonnement existant
            existing_sub = self.db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if existing_sub:
                # Supprimer l'ancien abonnement ou le marquer comme remplacé
                self.db.delete(existing_sub)
            
            self.db.add(new_subscription)
            self.db.commit()
            self.db.refresh(new_subscription)
            
            return {
                "success": True,
                "message": "Abonnement créé, en attente de paiement",
                "data": {
                    "subscription_id": new_subscription.id,
                    "plan": plan.value,
                    "price": final_price,
                    "discount": discount,
                    "payment_method": payment_method,
                    "payment_required": final_price > 0
                }
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur create_subscription: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la création de l'abonnement"
            }
    
    async def activate_subscription_after_payment(
        self,
        subscription_id: int,
        payment_reference: str
    ) -> Dict[str, Any]:
        """
        Activer un abonnement après paiement réussi
        """
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.id == subscription_id
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "message": "Abonnement introuvable"
                }
            
            # Activer l'abonnement
            subscription.activate(payment_reference)
            
            # Mettre à jour le wallet admin
            self._update_admin_wallet(subscription.price, "subscription")
            
            # Mettre à jour les statistiques journalières
            self._update_daily_stats(subscription)
            
            self.db.commit()
            
            # Envoyer confirmation par WhatsApp
            user = subscription.user
            if user and user.phone:
                await self.sms_service.send_payment_confirmation(
                    user.phone,
                    user.full_name,
                    subscription.plan_display_name,
                    subscription.price,
                    subscription.end_date.strftime("%d/%m/%Y")
                )
            
            return {
                "success": True,
                "message": "Abonnement activé avec succès",
                "data": subscription.to_dict()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur activate_subscription_after_payment: {e}")
            return {
                "success": False,
                "message": "Erreur lors de l'activation"
            }
    
    def _update_admin_wallet(self, amount: float, transaction_type: str):
        """
        Mettre à jour le wallet admin avec les revenus
        """
        try:
            wallet = self.db.query(AdminWallet).first()
            if not wallet:
                wallet = AdminWallet()
                self.db.add(wallet)
            
            wallet.add_revenue(amount, transaction_type)
            
        except Exception as e:
            print(f"Erreur _update_admin_wallet: {e}")
    
    def _update_daily_stats(self, subscription: Subscription):
        """
        Mettre à jour les statistiques journalières
        """
        try:
            today_stats = DailyStats.get_or_create_today(self.db)
            today_stats.increment_revenue(subscription.price, subscription.plan.value)
            
        except Exception as e:
            print(f"Erreur _update_daily_stats: {e}")
    
    async def renew_subscription(
        self,
        user_id: int,
        new_plan: Optional[SubscriptionPlan] = None
    ) -> Dict[str, Any]:
        """
        Renouveler un abonnement existant
        """
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "message": "Aucun abonnement à renouveler"
                }
            
            if not subscription.can_renew():
                return {
                    "success": False,
                    "message": "Abonnement non renouvelable"
                }
            
            # Utiliser le nouveau plan ou garder l'actuel
            plan_to_use = new_plan or subscription.plan
            subscription.renew(plan_to_use)
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Abonnement renouvelé",
                "data": subscription.to_dict()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur renew_subscription: {e}")
            return {
                "success": False,
                "message": "Erreur lors du renouvellement"
            }
    
    async def check_expiring_subscriptions(self) -> Dict[str, Any]:
        """
        Vérifier les abonnements qui expirent bientôt
        Job à exécuter quotidiennement
        """
        try:
            # Abonnements qui expirent dans 7 jours
            warning_date = datetime.utcnow() + timedelta(days=7)
            expiring_subscriptions = self.db.query(Subscription).join(User).filter(
                and_(
                    Subscription.end_date <= warning_date,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.expiry_warning_sent == False,
                    User.is_active == True
                )
            ).all()
            
            notifications_sent = 0
            
            for subscription in expiring_subscriptions:
                user = subscription.user
                if user and user.phone:
                    # Envoyer rappel WhatsApp
                    success = await self.sms_service.send_subscription_reminder(
                        user.phone,
                        user.full_name,
                        subscription.days_remaining
                    )
                    
                    if success:
                        subscription.mark_expiry_warning_sent()
                        notifications_sent += 1
            
            # Abonnements expirés aujourd'hui
            expired_today = self.db.query(Subscription).filter(
                and_(
                    Subscription.is_expired == True,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                    Subscription.expiry_notification_sent == False
                )
            ).all()
            
            for subscription in expired_today:
                # Marquer comme expiré
                subscription.status = SubscriptionStatus.EXPIRED
                subscription.mark_expiry_notification_sent()
                
                # Envoyer notification d'expiration
                user = subscription.user
                if user and user.phone:
                    await self.sms_service.send_subscription_reminder(
                        user.phone,
                        user.full_name,
                        0  # 0 jours = expiré
                    )
            
            self.db.commit()
            
            return {
                "success": True,
                "expiring_warnings_sent": notifications_sent,
                "expired_today": len(expired_today),
                "message": f"Vérification terminée: {notifications_sent} rappels envoyés"
            }
            
        except Exception as e:
            print(f"Erreur check_expiring_subscriptions: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la vérification"
            }
    
    def cancel_subscription(self, user_id: int, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Annuler un abonnement
        """
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "message": "Aucun abonnement à annuler"
                }
            
            # Annuler l'abonnement
            subscription.cancel()
            if reason:
                subscription.notes = f"Annulé: {reason}"
            
            self.db.commit()
            
            return {
                "success": True,
                "message": "Abonnement annulé",
                "cancelled_at": subscription.cancelled_at.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur cancel_subscription: {e}")
            return {
                "success": False,
                "message": "Erreur lors de l'annulation"
            }
    
    def get_subscription_analytics(self, user_id: int) -> Dict[str, Any]:
        """
        Analytics de l'abonnement pour l'utilisateur
        """
        try:
            subscription = self.db.query(Subscription).filter(
                Subscription.user_id == user_id
            ).first()
            
            if not subscription:
                return {"error": "Aucun abonnement"}
            
            user = subscription.user
            
            # Calculer les métriques
            days_active = (datetime.utcnow() - subscription.start_date).days
            avg_views_per_day = user.profile_views / max(1, days_active)
            avg_contacts_per_day = user.total_contacts / max(1, days_active)
            
            # ROI approximatif
            estimated_earnings = user.total_contacts * (user.daily_rate or user.monthly_rate or 0) * 0.1
            roi_percentage = (estimated_earnings / subscription.price * 100) if subscription.price > 0 else 0
            
            return {
                "subscription": subscription.to_dict(),
                "analytics": {
                    "days_active": days_active,
                    "profile_views": user.profile_views,
                    "total_contacts": user.total_contacts,
                    "avg_views_per_day": round(avg_views_per_day, 1),
                    "avg_contacts_per_day": round(avg_contacts_per_day, 1),
                    "estimated_roi_percentage": round(roi_percentage, 1)
                },
                "recommendations": self._get_subscription_recommendations(subscription, user)
            }
            
        except Exception as e:
            print(f"Erreur get_subscription_analytics: {e}")
            return {"error": "Erreur lors du calcul des analytics"}
    
    def _get_subscription_recommendations(self, subscription: Subscription, user: User) -> List[str]:
        """
        Recommandations personnalisées basées sur l'usage
        """
        recommendations = []
        
        if subscription.is_expiring_soon:
            if user.total_contacts > 10:
                recommendations.append("Vous recevez beaucoup de contacts ! Pensez à un plan plus long pour économiser.")
            recommendations.append("Renouvelez avant l'expiration pour ne pas perdre votre visibilité.")
        
        if subscription.plan == SubscriptionPlan.MONTHLY and user.total_contacts > 5:
            recommendations.append("Avec votre activité, un plan trimestriel vous ferait économiser 1,200 FCFA.")
        
        if user.profile_completion_percentage < 80:
            recommendations.append("Complétez votre profil pour attirer plus de clients.")
        
        if user.rating_count == 0:
            recommendations.append("Encouragez vos clients à laisser des avis pour améliorer votre visibilité.")
        
        if not user.profile_picture:
            recommendations.append("Ajoutez une photo de profil pour inspirer confiance.")
        
        return recommendations
    
    def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Statistiques de parrainage d'un utilisateur
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "Utilisateur introuvable"}
            
            # Compter les filleuls
            referred_users = self.db.query(User).filter(
                User.referred_by == user.referral_code
            ).all()
            
            # Compter ceux qui ont payé
            paid_referrals = 0
            for referred in referred_users:
                if referred.subscription and referred.subscription.payment_status == PaymentStatus.SUCCESS:
                    paid_referrals += 1
            
            # Calcul des bonus obtenus
            bonus_months = paid_referrals  # 1 mois par filleul qui paie
            
            return {
                "referral_code": user.referral_code,
                "total_invitations": len(referred_users),
                "paid_referrals": paid_referrals,
                "bonus_months_earned": bonus_months,
                "potential_next_bonus": 1 if len(referred_users) > paid_referrals else 0
            }
            
        except Exception as e:
            print(f"Erreur get_referral_stats: {e}")
            return {"error": "Erreur lors du calcul"}

    except Exception as e:
            print(f"Erreur get_referral_stats: {e}")
            return {"error": "Erreur lors du calcul"}  # ← Tu avais oublié ce return !
    
    # 🆕 NOUVELLE MÉTHODE
    async def initiate_payment_with_cinetpay(
        self,
        user_id: int,
        plan: SubscriptionPlan,
        customer_name: str,
        customer_phone: str
    ) -> Dict[str, Any]:
        """
        Initier un paiement CinetPay pour un abonnement
        🆕 NOUVELLE MÉTHODE
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    "success": False,
                    "message": "Utilisateur introuvable"
                }
            
            # Récupérer le prix du plan
            from app.models.subscription import Subscription as SubModel
            plan_price = SubModel.get_plan_price(plan)
            
            if plan_price == 0:
                return {
                    "success": False,
                    "message": "Plan d'abonnement invalide"
                }
            
            # Créer l'abonnement en attente
            subscription_result = await self.create_subscription(
                user_id=user_id,
                plan=plan,
                payment_method="cinetpay"
            )
            
            if not subscription_result["success"]:
                return subscription_result
            
            subscription_id = subscription_result["data"]["subscription_id"]
            
            # Initier le paiement CinetPay
            payment_result = self.cinetpay_service.initiate_payment(
                user_id=user_id,
                amount=plan_price,
                customer_name=customer_name,
                customer_phone=customer_phone,
                description=f"Abonnement {plan.value} AlloBara",
                subscription_id=subscription_id
            )
            
            if payment_result["success"]:
                return {
                    "success": True,
                    "message": "Paiement initialisé",
                    "payment_url": payment_result["payment_url"],
                    "transaction_id": payment_result["transaction_id"],
                    "subscription_id": subscription_id,
                    "amount": plan_price
                }
            else:
                return payment_result
                
        except Exception as e:
            self.db.rollback()
            print(f"Erreur initiate_payment_with_cinetpay: {e}")
            return {
                "success": False,
                "message": f"Erreur lors de l'initialisation: {str(e)}"
            }

    