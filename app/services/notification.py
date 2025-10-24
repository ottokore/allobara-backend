"""
Service de notifications AlloBara
Gestion des notifications multi-canaux (SMS, WhatsApp, Push, In-App)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.models.notification import (
    Notification, NotificationType, NotificationChannel, 
    NotificationStatus, NotificationPriority
)
from app.models.user import User
from app.services.sms import SMSService
from app.core.config import settings

class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.sms_service = SMSService()
    
    # =========================================
    # CRÉATION DE NOTIFICATIONS
    # =========================================
    
    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        channels: List[str],
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Créer une nouvelle notification
        """
        try:
            # Vérifier que l'utilisateur existe
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Utilisateur introuvable"}
            
            # Créer la notification
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                message=message,
                channels=channels,
                priority=priority,
                **kwargs
            )
            
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)
            
            # Envoyer immédiatement si pas programmée
            if not notification.scheduled_at:
                await self._send_notification(notification)
            
            return {
                "success": True,
                "notification_id": notification.id,
                "message": "Notification créée avec succès"
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur create_notification: {e}")
            return {"success": False, "message": "Erreur lors de la création"}
    
    async def create_welcome_notification(self, user_id: int, user_name: str) -> Dict[str, Any]:
        """
        Notification de bienvenue pour nouveau prestataire
        """
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.WELCOME,
            title=f"🎉 Bienvenue sur AlloBara, {user_name} !",
            message="Votre compte est créé avec succès. Complétez votre profil pour attirer plus de clients.",
            channels=["whatsapp", "in_app"],
            priority=NotificationPriority.NORMAL,
            action_text="Compléter mon profil",
            action_url="/profile/setup"
        )
    
    async def create_subscription_expiring_notification(
        self, 
        user_id: int, 
        days_remaining: int
    ) -> Dict[str, Any]:
        """
        Notification d'expiration d'abonnement
        """
        if days_remaining <= 0:
            title = "⚠️ Abonnement expiré"
            message = "Votre abonnement AlloBara a expiré. Renouvelez pour rester visible aux clients."
            priority = NotificationPriority.URGENT
        elif days_remaining <= 3:
            title = f"⏰ Plus que {days_remaining} jour(s)"
            message = f"Votre abonnement expire dans {days_remaining} jour(s). Renouvelez maintenant !"
            priority = NotificationPriority.HIGH
        else:
            title = f"📅 Expiration dans {days_remaining} jours"
            message = f"Pensez à renouveler votre abonnement qui expire dans {days_remaining} jours."
            priority = NotificationPriority.NORMAL
        
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRING,
            title=title,
            message=message,
            channels=["whatsapp", "sms", "in_app"],
            priority=priority,
            action_text="Renouveler",
            action_url="/subscription/renew"
        )
    
    async def create_payment_failed_notification(
        self, 
        user_id: int, 
        amount: float,
        error_reason: str = None
    ) -> Dict[str, Any]:
        """
        Notification d'échec de paiement
        """
        formatted_amount = f"{int(amount):,} FCFA".replace(",", " ")
        
        message = f"Votre paiement de {formatted_amount} n'a pas pu être traité."
        if error_reason:
            message += f" Raison: {error_reason}"
        message += " Réessayez ou contactez le support."
        
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.PAYMENT_FAILED,
            title="❌ Paiement échoué",
            message=message,
            channels=["whatsapp", "sms", "in_app"],
            priority=NotificationPriority.HIGH,
            action_text="Réessayer",
            action_url="/subscription/payment"
        )
    
    async def create_review_received_notification(
        self,
        user_id: int,
        rating: int,
        client_name: str,
        comment: str = None
    ) -> Dict[str, Any]:
        """
        Notification de nouvel avis reçu
        """
        stars = "⭐" * rating
        
        message = f"{client_name} vous a laissé un avis : {stars} ({rating}/5)"
        if comment and len(comment) > 0:
            # Tronquer le commentaire pour la notification
            short_comment = comment[:50] + "..." if len(comment) > 50 else comment
            message += f"\n\"{short_comment}\""
        
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.REVIEW_RECEIVED,
            title="🌟 Nouvel avis reçu !",
            message=message,
            channels=["whatsapp", "in_app"],
            priority=NotificationPriority.NORMAL,
            action_text="Voir l'avis",
            action_url="/reviews"
        )
    
    async def create_referral_bonus_notification(
        self,
        user_id: int,
        referral_name: str,
        bonus_months: int
    ) -> Dict[str, Any]:
        """
        Notification de bonus de parrainage
        """
        return await self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.REFERRAL_BONUS,
            title="🎁 Bonus de parrainage !",
            message=f"Félicitations ! {referral_name} s'est inscrit. Vous gagnez {bonus_months} mois d'abonnement offert.",
            channels=["whatsapp", "in_app"],
            priority=NotificationPriority.NORMAL,
            action_text="Voir mes filleuls",
            action_url="/referrals"
        )
    
    # =========================================
    # ENVOI DE NOTIFICATIONS
    # =========================================
    
    async def _send_notification(self, notification: Notification) -> bool:
        """
        Envoyer une notification sur tous ses canaux
        """
        try:
            user = notification.user
            if not user:
                notification.mark_as_failed("Utilisateur introuvable")
                self.db.commit()
                return False
            
            send_tasks = []
            
            # Envoyer sur chaque canal configuré
            for channel_str in notification.channels:
                try:
                    channel = NotificationChannel(channel_str)
                    
                    if channel == NotificationChannel.WHATSAPP and user.phone:
                        task = self._send_whatsapp(notification, user.phone)
                        send_tasks.append(("whatsapp", task))
                    
                    elif channel == NotificationChannel.SMS and user.phone:
                        task = self._send_sms(notification, user.phone)
                        send_tasks.append(("sms", task))
                    
                    elif channel == NotificationChannel.IN_APP:
                        # Notification in-app est automatiquement "envoyée"
                        notification.status = NotificationStatus.SENT
                        notification.sent_at = datetime.utcnow()
                    
                    elif channel == NotificationChannel.PUSH:
                        # TODO: Implémenter push notifications
                        notification.push_sent = True
                
                except ValueError:
                    print(f"Canal invalide: {channel_str}")
                    continue
            
            # Attendre tous les envois
            if send_tasks:
                results = await asyncio.gather(
                    *[task for _, task in send_tasks],
                    return_exceptions=True
                )
                
                # Traiter les résultats
                for i, (channel_name, result) in enumerate(zip([name for name, _ in send_tasks], results)):
                    if isinstance(result, Exception):
                        print(f"Erreur envoi {channel_name}: {result}")
                    elif result:
                        if channel_name == "whatsapp":
                            notification.mark_as_sent(NotificationChannel.WHATSAPP)
                        elif channel_name == "sms":
                            notification.mark_as_sent(NotificationChannel.SMS)
            
            self.db.commit()
            return True
            
        except Exception as e:
            print(f"Erreur _send_notification: {e}")
            notification.mark_as_failed(str(e))
            self.db.commit()
            return False
    
    async def _send_whatsapp(self, notification: Notification, phone: str) -> bool:
        """
        Envoyer une notification par WhatsApp
        """
        try:
            # Construire le message
            message = f"*{notification.title}*\n\n{notification.message}"
            
            if notification.action_text and notification.action_url:
                message += f"\n\n👉 {notification.action_text}: {notification.action_url}"
            
            success = await self.sms_service.send_whatsapp_message(phone, message)
            
            if success:
                notification.whatsapp_sent = True
                notification.whatsapp_delivered = True  # Assumé livré pour WhatsApp
            
            return success
            
        except Exception as e:
            print(f"Erreur _send_whatsapp: {e}")
            return False
    
    async def _send_sms(self, notification: Notification, phone: str) -> bool:
        """
        Envoyer une notification par SMS
        """
        try:
            # Message SMS plus concis
            message = f"{notification.title}\n\n{notification.message}"
            
            # Tronquer si trop long (160 caractères max)
            if len(message) > 160:
                message = message[:157] + "..."
            
            success = await self.sms_service.send_sms(phone, message)
            
            if success:
                notification.sms_sent = True
                notification.sms_delivered = True  # Assumé livré
            
            return success
            
        except Exception as e:
            print(f"Erreur _send_sms: {e}")
            return False
    
    # =========================================
    # GESTION DES NOTIFICATIONS
    # =========================================
    
    def get_user_notifications(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """
        Récupérer les notifications d'un utilisateur
        """
        try:
            query = self.db.query(Notification).filter(
                Notification.user_id == user_id
            )
            
            if unread_only:
                query = query.filter(Notification.in_app_read == False)
            
            # Total
            total = query.count()
            
            # Pagination
            offset = (page - 1) * limit
            notifications = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit).all()
            
            # Convertir en dictionnaire
            notifications_data = [notif.to_dict() for notif in notifications]
            
            # Statistiques
            unread_count = self.db.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.in_app_read == False
                )
            ).count()
            
            return {
                "notifications": notifications_data,
                "total": total,
                "unread_count": unread_count,
                "page": page,
                "limit": limit,
                "has_next": len(notifications) == limit
            }
            
        except Exception as e:
            print(f"Erreur get_user_notifications: {e}")
            return {
                "notifications": [],
                "total": 0,
                "unread_count": 0,
                "page": page,
                "limit": limit,
                "has_next": False
            }
    
    def mark_notification_as_read(self, notification_id: int, user_id: int) -> Dict[str, Any]:
        """
        Marquer une notification comme lue
        """
        try:
            notification = self.db.query(Notification).filter(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            ).first()
            
            if not notification:
                return {"success": False, "message": "Notification introuvable"}
            
            if not notification.is_read:
                notification.mark_as_read()
                self.db.commit()
            
            return {"success": True, "message": "Notification marquée comme lue"}
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur mark_notification_as_read: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}
    
    def mark_all_notifications_as_read(self, user_id: int) -> Dict[str, Any]:
        """
        Marquer toutes les notifications comme lues
        """
        try:
            count = self.db.query(Notification).filter(
                and_(
                    Notification.user_id == user_id,
                    Notification.in_app_read == False
                )
            ).update({
                Notification.in_app_read: True,
                Notification.read_at: datetime.utcnow(),
                Notification.status: NotificationStatus.READ
            })
            
            self.db.commit()
            
            return {
                "success": True,
                "message": f"{count} notifications marquées comme lues"
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur mark_all_notifications_as_read: {e}")
            return {"success": False, "message": "Erreur lors de la mise à jour"}
    
    def delete_notification(self, notification_id: int, user_id: int) -> Dict[str, Any]:
        """
        Supprimer une notification
        """
        try:
            notification = self.db.query(Notification).filter(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            ).first()
            
            if not notification:
                return {"success": False, "message": "Notification introuvable"}
            
            self.db.delete(notification)
            self.db.commit()
            
            return {"success": True, "message": "Notification supprimée"}
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur delete_notification: {e}")
            return {"success": False, "message": "Erreur lors de la suppression"}
    
    # =========================================
    # NOTIFICATIONS PROGRAMMÉES
    # =========================================
    
    async def process_scheduled_notifications(self) -> Dict[str, Any]:
        """
        Traiter les notifications programmées (job à exécuter régulièrement)
        """
        try:
            # Récupérer les notifications prêtes à être envoyées
            now = datetime.utcnow()
            
            notifications = self.db.query(Notification).filter(
                and_(
                    Notification.status == NotificationStatus.PENDING,
                    or_(
                        Notification.scheduled_at.is_(None),
                        Notification.scheduled_at <= now
                    ),
                    or_(
                        Notification.expires_at.is_(None),
                        Notification.expires_at > now
                    )
                )
            ).limit(50).all()  # Traiter par batch de 50
            
            sent_count = 0
            failed_count = 0
            
            for notification in notifications:
                success = await self._send_notification(notification)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            
            return {
                "success": True,
                "processed": len(notifications),
                "sent": sent_count,
                "failed": failed_count
            }
            
        except Exception as e:
            print(f"Erreur process_scheduled_notifications: {e}")
            return {"success": False, "error": str(e)}
    
    async def cleanup_old_notifications(self, days_old: int = 30) -> Dict[str, Any]:
        """
        Nettoyer les anciennes notifications lues
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted_count = self.db.query(Notification).filter(
                and_(
                    Notification.status == NotificationStatus.READ,
                    Notification.read_at < cutoff_date
                )
            ).delete()
            
            self.db.commit()
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"{deleted_count} anciennes notifications supprimées"
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur cleanup_old_notifications: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================
    # NOTIFICATIONS EN MASSE
    # =========================================
    
    async def send_bulk_notification(
        self,
        user_ids: List[int],
        notification_type: NotificationType,
        title: str,
        message: str,
        channels: List[str],
        priority: NotificationPriority = NotificationPriority.NORMAL
    ) -> Dict[str, Any]:
        """
        Envoyer une notification à plusieurs utilisateurs
        """
        try:
            if len(user_ids) > 1000:
                return {"success": False, "message": "Maximum 1000 utilisateurs par envoi"}
            
            notifications_created = 0
            
            for user_id in user_ids:
                try:
                    result = await self.create_notification(
                        user_id=user_id,
                        notification_type=notification_type,
                        title=title,
                        message=message,
                        channels=channels,
                        priority=priority
                    )
                    
                    if result["success"]:
                        notifications_created += 1
                    
                except Exception as e:
                    print(f"Erreur notification utilisateur {user_id}: {e}")
                    continue
            
            return {
                "success": True,
                "total_users": len(user_ids),
                "notifications_created": notifications_created,
                "message": f"{notifications_created} notifications créées"
            }
            
        except Exception as e:
            print(f"Erreur send_bulk_notification: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================================
    # STATISTIQUES
    # =========================================
    
    def get_notification_stats(self, user_id: int = None) -> Dict[str, Any]:
        """
        Statistiques des notifications
        """
        try:
            query = self.db.query(Notification)
            if user_id:
                query = query.filter(Notification.user_id == user_id)
            
            # Stats générales
            total = query.count()
            sent = query.filter(Notification.status != NotificationStatus.PENDING).count()
            read = query.filter(Notification.status == NotificationStatus.READ).count()
            failed = query.filter(Notification.status == NotificationStatus.FAILED).count()
            
            # Par type
            type_stats = {}
            for notif_type in NotificationType:
                count = query.filter(Notification.type == notif_type).count()
                if count > 0:
                    type_stats[notif_type.value] = count
            
            # Par canal
            channel_stats = {
                "whatsapp": query.filter(Notification.whatsapp_sent == True).count(),
                "sms": query.filter(Notification.sms_sent == True).count(),
                "in_app": total,  # Toutes les notifications sont in-app
                "push": query.filter(Notification.push_sent == True).count()
            }
            
            # Taux de lecture
            read_rate = (read / sent * 100) if sent > 0 else 0
            
            return {
                "total_notifications": total,
                "sent_notifications": sent,
                "read_notifications": read,
                "failed_notifications": failed,
                "read_rate_percentage": round(read_rate, 1),
                "type_breakdown": type_stats,
                "channel_stats": channel_stats
            }
            
        except Exception as e:
            print(f"Erreur get_notification_stats: {e}")
            return {}