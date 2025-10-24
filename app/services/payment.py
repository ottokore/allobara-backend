"""
Service de paiements AlloBara
Intégration avec Wave et autres moyens de paiement
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus, PaymentStatus
from app.models.admin import AdminWallet, DailyStats, TransactionType
from app.core.config import settings
from app.services.sms import SMSService

class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.sms_service = SMSService()
        # En mode démo, nous n'utilisons pas l'API Wave réelle
        self.demo_mode = settings.DEMO_MODE or True  # Pour l'instant toujours en démo
    
    async def initiate_wave_payment(
        self,
        subscription_id: int,
        phone_number: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Initier un paiement Wave
        """
        try:
            # Récupérer l'abonnement
            subscription = self.db.query(Subscription).filter(
                and_(
                    Subscription.id == subscription_id,
                    Subscription.user_id == user_id
                )
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "message": "Abonnement introuvable"
                }
            
            if subscription.payment_status == PaymentStatus.SUCCESS:
                return {
                    "success": False,
                    "message": "Cet abonnement est déjà payé"
                }
            
            # En mode démo
            if self.demo_mode:
                return await self._demo_wave_payment(subscription, phone_number)
            
            # TODO: Intégration réelle avec l'API Wave
            # Pour l'instant, retourner une réponse de démo
            return await self._demo_wave_payment(subscription, phone_number)
            
        except Exception as e:
            print(f"Erreur initiate_wave_payment: {e}")
            return {
                "success": False,
                "message": "Erreur lors de l'initiation du paiement"
            }
    
    async def _demo_wave_payment(
        self,
        subscription: Subscription,
        phone_number: str
    ) -> Dict[str, Any]:
        """
        Simuler un paiement Wave en mode démo
        """
        try:
            # Générer un ID de paiement fictif
            payment_id = f"WAVE_DEMO_{subscription.id}_{int(datetime.utcnow().timestamp())}"
            
            print(f"\n💳 DEMO PAIEMENT WAVE")
            print(f"📱 Numéro: {phone_number}")
            print(f"💰 Montant: {subscription.formatted_price}")
            print(f"📋 Plan: {subscription.plan_display_name}")
            print(f"🆔 Payment ID: {payment_id}")
            print(f"⏰ Expire dans: 30 minutes")
            print(f"✅ En mode démo - paiement automatiquement réussi dans 5 secondes\n")
            
            # Mettre à jour l'abonnement avec l'ID de paiement
            subscription.payment_reference = payment_id
            subscription.payment_status = PaymentStatus.PENDING
            self.db.commit()
            
            # Simuler la confirmation automatique après 5 secondes
            asyncio.create_task(self._auto_confirm_demo_payment(subscription.id, payment_id))
            
            return {
                "success": True,
                "data": {
                    "payment_id": payment_id,
                    "payment_url": f"https://demo.wave.com/pay/{payment_id}",
                    "amount": subscription.price,
                    "currency": "FCFA",
                    "expires_in": 1800,  # 30 minutes
                    "status": "pending",
                    "demo_mode": True
                }
            }
            
        except Exception as e:
            print(f"Erreur _demo_wave_payment: {e}")
            return {
                "success": False,
                "message": "Erreur simulation paiement"
            }
    
    async def _auto_confirm_demo_payment(self, subscription_id: int, payment_id: str):
        """
        Confirmer automatiquement un paiement démo après 5 secondes
        """
        try:
            # Attendre 5 secondes
            await asyncio.sleep(5)
            
            print(f"🔄 Auto-confirmation du paiement démo: {payment_id}")
            
            # Simuler webhook de confirmation
            webhook_data = {
                "transaction_id": payment_id,
                "status": "success",
                "amount": 0,  # Sera récupéré de l'abonnement
                "currency": "FCFA",
                "subscription_id": subscription_id,
                "provider_reference": f"WAVE_{payment_id}",
                "timestamp": datetime.utcnow()
            }
            
            await self.process_payment_webhook(webhook_data)
            
        except Exception as e:
            print(f"Erreur _auto_confirm_demo_payment: {e}")
    
    async def process_payment_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traiter un webhook de confirmation de paiement
        """
        try:
            subscription_id = webhook_data.get("subscription_id")
            transaction_status = webhook_data.get("status")
            
            if not subscription_id:
                return {
                    "success": False,
                    "message": "subscription_id manquant dans le webhook"
                }
            
            # Récupérer l'abonnement
            subscription = self.db.query(Subscription).filter(
                Subscription.id == subscription_id
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "message": "Abonnement introuvable"
                }
            
            if transaction_status.lower() in ["success", "completed", "paid"]:
                return await self._handle_successful_payment(subscription, webhook_data)
            else:
                return await self._handle_failed_payment(subscription, webhook_data)
                
        except Exception as e:
            print(f"Erreur process_payment_webhook: {e}")
            return {
                "success": False,
                "message": "Erreur lors du traitement du webhook"
            }
    
    async def _handle_successful_payment(
        self,
        subscription: Subscription,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Traiter un paiement réussi
        """
        try:
            # Activer l'abonnement
            subscription.payment_status = PaymentStatus.SUCCESS
            subscription.payment_date = datetime.utcnow()
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.activated_at = datetime.utcnow()
            subscription.payment_provider_response = json.dumps(webhook_data)
            
            if webhook_data.get("provider_reference"):
                subscription.payment_reference = webhook_data["provider_reference"]
            
            # Mettre à jour le wallet admin
            self._update_admin_wallet(subscription.price)
            
            # Mettre à jour les statistiques journalières
            self._update_daily_stats(subscription)
            
            # Traiter le parrainage si applicable
            if subscription.is_from_referral:
                await self._process_referral_bonus(subscription)
            
            self.db.commit()
            
            print(f"✅ Paiement confirmé pour l'abonnement {subscription.id}")
            print(f"💰 Montant: {subscription.formatted_price}")
            print(f"👤 Utilisateur: {subscription.user.full_name}")
            
            # Envoyer confirmation WhatsApp
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
                "message": "Paiement traité avec succès",
                "subscription_activated": True
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur _handle_successful_payment: {e}")
            return {
                "success": False,
                "message": "Erreur lors du traitement du paiement réussi"
            }
    
    async def _handle_failed_payment(
        self,
        subscription: Subscription,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Traiter un paiement échoué
        """
        try:
            subscription.payment_status = PaymentStatus.FAILED
            subscription.payment_provider_response = json.dumps(webhook_data)
            subscription.renewal_attempts += 1
            
            # Si trop de tentatives, marquer comme annulé
            if subscription.renewal_attempts >= subscription.max_renewal_attempts:
                subscription.status = SubscriptionStatus.CANCELLED
            
            self.db.commit()
            
            print(f"❌ Paiement échoué pour l'abonnement {subscription.id}")
            print(f"📋 Raison: {webhook_data.get('error_message', 'Non spécifiée')}")
            
            # Notifier l'utilisateur de l'échec
            user = subscription.user
            if user and user.phone:
                await self._notify_payment_failure(user, subscription, webhook_data)
            
            return {
                "success": True,
                "message": "Paiement échoué traité",
                "payment_failed": True
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur _handle_failed_payment: {e}")
            return {
                "success": False,
                "message": "Erreur lors du traitement du paiement échoué"
            }
    
    def _update_admin_wallet(self, amount: float):
        """
        Mettre à jour le wallet admin avec les revenus
        """
        try:
            wallet = self.db.query(AdminWallet).first()
            if not wallet:
                wallet = AdminWallet()
                self.db.add(wallet)
            
            wallet.add_revenue(amount, TransactionType.SUBSCRIPTION)
            print(f"💼 Wallet admin mis à jour: +{amount} FCFA")
            
        except Exception as e:
            print(f"Erreur _update_admin_wallet: {e}")
    
    def _update_daily_stats(self, subscription: Subscription):
        """
        Mettre à jour les statistiques journalières
        """
        try:
            today_stats = DailyStats.get_or_create_today(self.db)
            today_stats.increment_revenue(subscription.price, subscription.plan.value)
            
            print(f"📊 Stats journalières mises à jour")
            
        except Exception as e:
            print(f"Erreur _update_daily_stats: {e}")
    
    async def _process_referral_bonus(self, subscription: Subscription):
        """
        Traiter les bonus de parrainage
        """
        try:
            if not subscription.user.referred_by:
                return
            
            # Trouver le parrain
            sponsor = self.db.query(User).filter(
                User.referral_code == subscription.user.referred_by
            ).first()
            
            if not sponsor or not sponsor.subscription:
                return
            
            # Étendre l'abonnement du parrain d'un mois
            sponsor_sub = sponsor.subscription
            if sponsor_sub.is_active:
                # Ajouter 30 jours à la fin de l'abonnement
                sponsor_sub.end_date = sponsor_sub.end_date + timedelta(days=30)
                
                # Incrémenter le compteur de filleuls
                sponsor.referral_count = (sponsor.referral_count or 0) + 1
                
                print(f"🎁 Bonus parrainage: +1 mois pour {sponsor.full_name}")
                
                # Notifier le parrain
                if sponsor.phone:
                    message = f"""🎉 Félicitations {sponsor.full_name} !

Votre filleul {subscription.user.full_name} vient de souscrire un abonnement.

🎁 Votre récompense:
• +1 mois d'abonnement offert
• Nouvelle date d'expiration: {sponsor_sub.end_date.strftime("%d/%m/%Y")}

Merci de faire grandir AlloBara ! 🚀"""
                    
                    await self.sms_service.send_whatsapp_message(sponsor.phone, message)
            
        except Exception as e:
            print(f"Erreur _process_referral_bonus: {e}")
    
    async def _notify_payment_failure(
        self,
        user: User,
        subscription: Subscription,
        webhook_data: Dict[str, Any]
    ):
        """
        Notifier l'utilisateur d'un échec de paiement
        """
        try:
            error_msg = webhook_data.get("error_message", "Erreur inconnue")
            
            message = f"""❌ Paiement échoué - {user.full_name}

Votre paiement de {subscription.formatted_price} n'a pas pu être traité.

Raison: {error_msg}

Solutions:
• Vérifiez votre solde Wave
• Réessayez le paiement
• Contactez le support Wave

Votre profil reste visible pendant 24h pour régulariser."""
            
            await self.sms_service.send_whatsapp_message(user.phone, message)
            
        except Exception as e:
            print(f"Erreur _notify_payment_failure: {e}")
    
    async def verify_payment_status(
        self,
        payment_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Vérifier le statut d'un paiement
        """
        try:
            # Chercher l'abonnement avec cette référence de paiement
            subscription = self.db.query(Subscription).filter(
                and_(
                    Subscription.payment_reference == payment_id,
                    Subscription.user_id == user_id
                )
            ).first()
            
            if not subscription:
                return {
                    "success": False,
                    "transaction_verified": False,
                    "subscription_activated": False,
                    "user_notified": False,
                    "message": "Paiement introuvable"
                }
            
            is_verified = subscription.payment_status == PaymentStatus.SUCCESS
            is_activated = subscription.status == SubscriptionStatus.ACTIVE
            
            return {
                "success": True,
                "transaction_verified": is_verified,
                "subscription_activated": is_activated,
                "user_notified": True,  # On considère que c'est fait
                "message": "Paiement vérifié avec succès" if is_verified else "Paiement en attente",
                "payment_status": subscription.payment_status.value,
                "subscription_status": subscription.status.value
            }
            
        except Exception as e:
            print(f"Erreur verify_payment_status: {e}")
            return {
                "success": False,
                "transaction_verified": False,
                "subscription_activated": False,
                "user_notified": False,
                "message": "Erreur lors de la vérification"
            }
    
    async def simulate_payment_for_demo(
        self,
        subscription_id: int,
        admin_user_id: int
    ) -> Dict[str, Any]:
        """
        Simuler un paiement pour la démo (admin uniquement)
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
            
            # Simuler webhook de paiement
            webhook_data = {
                "transaction_id": f"DEMO_SIM_{subscription_id}_{int(datetime.utcnow().timestamp())}",
                "status": "success",
                "amount": subscription.price,
                "currency": "FCFA",
                "subscription_id": subscription_id,
                "provider_reference": f"DEMO_ADMIN_{admin_user_id}",
                "timestamp": datetime.utcnow()
            }
            
            result = await self.process_payment_webhook(webhook_data)
            
            return {
                **result,
                "message": f"Paiement simulé pour la démo: {subscription.formatted_price}",
                "demo_simulation": True
            }
            
        except Exception as e:
            print(f"Erreur simulate_payment_for_demo: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la simulation"
            }
    
    def get_payment_methods(self) -> List[Dict[str, Any]]:
        """
        Récupérer les méthodes de paiement disponibles
        """
        return [
            {
                "id": "wave",
                "name": "Wave",
                "description": "Paiement mobile Wave",
                "logo": "/images/wave-logo.png",
                "is_primary": True,
                "supported_countries": ["CI"],
                "fees": "Gratuit",
                "processing_time": "Instantané"
            },
            {
                "id": "mtn",
                "name": "MTN Mobile Money",
                "description": "Paiement MTN Money",
                "logo": "/images/mtn-logo.png",
                "is_primary": False,
                "supported_countries": ["CI"],
                "fees": "Frais opérateur",
                "processing_time": "1-2 minutes",
                "status": "coming_soon"
            },
            {
                "id": "orange",
                "name": "Orange Money",
                "description": "Paiement Orange Money",
                "logo": "/images/orange-logo.png",
                "is_primary": False,
                "supported_countries": ["CI"],
                "fees": "Frais opérateur",
                "processing_time": "1-2 minutes",
                "status": "coming_soon"
            },
            {
                "id": "moov",
                "name": "Moov Money",
                "description": "Paiement Moov Money",
                "logo": "/images/moov-logo.png",
                "is_primary": False,
                "supported_countries": ["CI"],
                "fees": "Frais opérateur", 
                "processing_time": "1-2 minutes",
                "status": "coming_soon"
            }
        ]
    
    def get_payment_statistics(self) -> Dict[str, Any]:
        """
        Statistiques des paiements pour l'admin
        """
        try:
            from sqlalchemy import func
            
            # Paiements par statut
            status_stats = self.db.query(
                Subscription.payment_status,
                func.count(Subscription.id).label('count'),
                func.sum(Subscription.price).label('total')
            ).group_by(Subscription.payment_status).all()
            
            # Paiements par méthode
            method_stats = self.db.query(
                Subscription.payment_method,
                func.count(Subscription.id).label('count'),
                func.sum(Subscription.price).label('total')
            ).group_by(Subscription.payment_method).all()
            
            # Paiements aujourd'hui
            today = datetime.utcnow().date()
            today_payments = self.db.query(
                func.count(Subscription.id).label('count'),
                func.sum(Subscription.price).label('total')
            ).filter(
                and_(
                    func.date(Subscription.payment_date) == today,
                    Subscription.payment_status == PaymentStatus.SUCCESS
                )
            ).first()
            
            return {
                "status_breakdown": {
                    str(status): {"count": count, "total": total or 0}
                    for status, count, total in status_stats
                },
                "method_breakdown": {
                    method or "unknown": {"count": count, "total": total or 0}
                    for method, count, total in method_stats
                },
                "today": {
                    "count": today_payments.count or 0,
                    "total": today_payments.total or 0,
                    "formatted": f"{int(today_payments.total or 0):,} FCFA".replace(",", " ")
                }
            }
            
        except Exception as e:
            print(f"Erreur get_payment_statistics: {e}")
            return {}