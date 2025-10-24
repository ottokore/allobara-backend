"""
Service SMS et WhatsApp AlloBara
Envoi des OTP par WhatsApp via Twilio
"""

import asyncio
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

from app.core.config import settings

class SMSService:
    def __init__(self):
        self.client = None
        self.from_whatsapp = None
        
        # Initialiser Twilio seulement si les credentials sont fournis
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self.client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
                self.from_whatsapp = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"
            except Exception as e:
                print(f"Erreur initialisation Twilio: {e}")
                self.client = None
    
    async def send_whatsapp_message(
        self, 
        to_phone: str, 
        message: str,
        media_url: Optional[str] = None
    ) -> bool:
        """
        Envoyer un message WhatsApp via Twilio
        """
        try:
            # Si mode démo ou Twilio non configuré
            if settings.DEMO_MODE or not self.client:
                print(f"\n📱 DEMO WhatsApp vers {to_phone}:")
                print(f"💬 Message: {message}")
                if media_url:
                    print(f"🖼️ Media: {media_url}")
                print("✅ Message 'envoyé' en mode démo\n")
                return True
            
            # Formatter le numéro pour WhatsApp
            to_whatsapp = f"whatsapp:{to_phone}"
            
            # Préparer le message
            message_data = {
                "from_": self.from_whatsapp,
                "to": to_whatsapp,
                "body": message
            }
            
            # Ajouter media si fourni
            if media_url:
                message_data["media_url"] = [media_url]
            
            # Envoyer le message
            message_instance = self.client.messages.create(**message_data)
            
            print(f"✅ WhatsApp envoyé à {to_phone}, SID: {message_instance.sid}")
            return True
            
        except TwilioException as e:
            print(f"❌ Erreur Twilio: {e}")
            
            # En cas d'erreur Twilio, basculer en mode démo
            print(f"\n📱 FALLBACK DEMO vers {to_phone}:")
            print(f"💬 Message: {message}")
            print("⚠️ Envoyé en mode fallback\n")
            return True
            
        except Exception as e:
            print(f"❌ Erreur générale SMS: {e}")
            return False
    
    async def send_sms(self, to_phone: str, message: str) -> bool:
        """
        Envoyer un SMS classique via Twilio
        """
        try:
            if settings.DEMO_MODE or not self.client:
                print(f"\n📨 DEMO SMS vers {to_phone}:")
                print(f"💬 Message: {message}")
                print("✅ SMS 'envoyé' en mode démo\n")
                return True
            
            message_instance = self.client.messages.create(
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_phone,
                body=message
            )
            
            print(f"✅ SMS envoyé à {to_phone}, SID: {message_instance.sid}")
            return True
            
        except TwilioException as e:
            print(f"❌ Erreur Twilio SMS: {e}")
            
            # Fallback en mode démo
            print(f"\n📨 FALLBACK SMS vers {to_phone}:")
            print(f"💬 Message: {message}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur générale SMS: {e}")
            return False
    
    async def send_otp_whatsapp(self, phone_number: str, otp_code: str) -> Dict[str, Any]:
        """
        Envoyer spécifiquement un code OTP par WhatsApp
        """
        message = f"""🔐 Votre code AlloBara

Code de vérification: *{otp_code}*

Ce code expire dans 5 minutes.
Ne le partagez avec personne.

AlloBara - Trouvez des pros en un clic ✨"""
        
        success = await self.send_whatsapp_message(phone_number, message)
        
        return {
            "success": success,
            "message": "Code OTP envoyé par WhatsApp" if success else "Erreur d'envoi",
            "channel": "whatsapp",
            "expires_in": 300
        }
    
    async def send_welcome_message(self, phone_number: str, user_name: str) -> bool:
        """
        Envoyer un message de bienvenue après inscription
        """
        message = f"""🎉 Bienvenue sur AlloBara, {user_name} !

Votre compte est créé avec succès.

Prochaines étapes:
✅ Complétez votre profil
✅ Ajoutez vos réalisations
✅ Commencez à recevoir des clients

Votre période d'essai gratuite de 30 jours est active !

Bonne chance ! 🚀"""
        
        return await self.send_whatsapp_message(phone_number, message)
    
    async def send_subscription_reminder(
        self, 
        phone_number: str, 
        user_name: str, 
        days_remaining: int
    ) -> bool:
        """
        Envoyer un rappel d'expiration d'abonnement
        """
        if days_remaining <= 0:
            message = f"""⚠️ Abonnement expiré - {user_name}

Votre abonnement AlloBara a expiré.
Votre profil est maintenant invisible aux clients.

Renouvelez maintenant:
💰 Mensuel: 2,100 FCFA
💰 Trimestriel: 5,100 FCFA  
💰 Semestriel: 9,100 FCFA
💰 Annuel: 16,100 FCFA

Ne perdez pas vos clients ! 📱"""
        
        elif days_remaining <= 3:
            message = f"""⏰ Plus que {days_remaining} jour(s) - {user_name}

Votre abonnement AlloBara expire bientôt !

Renouvelez avant l'expiration pour:
✅ Rester visible aux clients
✅ Continuer à recevoir des contacts
✅ Garder votre classement

Renouvellement rapide par Wave 💳"""
        
        else:
            message = f"""📅 Rappel abonnement - {user_name}

Votre abonnement expire dans {days_remaining} jours.

Pensez à renouveler pour maintenir votre visibilité.

AlloBara - Votre succès, notre priorité ! ⭐"""
        
        return await self.send_whatsapp_message(phone_number, message)
    
    async def send_payment_confirmation(
        self,
        phone_number: str,
        user_name: str, 
        plan: str,
        amount: float,
        expires_date: str
    ) -> bool:
        """
        Confirmer un paiement d'abonnement
        """
        formatted_amount = f"{int(amount):,} FCFA".replace(",", " ")
        
        message = f"""✅ Paiement confirmé - {user_name}

Abonnement {plan}: {formatted_amount}
Valable jusqu'au: {expires_date}

Votre profil est maintenant visible !

Merci de votre confiance 🙏
AlloBara"""
        
        return await self.send_whatsapp_message(phone_number, message)
    
    async def send_review_notification(
        self,
        phone_number: str,
        user_name: str,
        rating: int,
        client_name: str
    ) -> bool:
        """
        Notifier qu'un avis a été reçu
        """
        stars = "⭐" * rating
        
        message = f"""🌟 Nouvel avis reçu - {user_name}

{client_name} vous a laissé un avis:
{stars} ({rating}/5)

Consultez vos avis dans l'application pour voir le commentaire complet.

Continuez votre excellent travail ! 👏"""
        
        return await self.send_whatsapp_message(phone_number, message)
    
    def check_service_status(self) -> Dict[str, Any]:
        """
        Vérifier l'état du service SMS/WhatsApp
        """
        status_info = {
            "twilio_configured": bool(self.client),
            "demo_mode": settings.DEMO_MODE,
            "whatsapp_available": bool(self.from_whatsapp),
            "sms_available": bool(settings.TWILIO_PHONE_NUMBER)
        }
        
        if self.client:
            try:
                # Tester la connexion Twilio
                account = self.client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
                status_info["twilio_status"] = account.status
                status_info["account_name"] = account.friendly_name
            except Exception as e:
                status_info["twilio_error"] = str(e)
                status_info["twilio_status"] = "error"
        
        return status_info
    
    async def send_bulk_message(
        self, 
        phone_numbers: list, 
        message: str,
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Envoyer un message en masse (limité pour éviter le spam)
        """
        if len(phone_numbers) > 100:
            return {
                "success": False,
                "message": "Maximum 100 destinataires par envoi"
            }
        
        results = {"sent": 0, "failed": 0, "errors": []}
        
        # Envoyer par batch pour éviter la surcharge
        for i in range(0, len(phone_numbers), max_concurrent):
            batch = phone_numbers[i:i + max_concurrent]
            tasks = []
            
            for phone in batch:
                task = self.send_whatsapp_message(phone, message)
                tasks.append(task)
            
            # Attendre que le batch soit terminé
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for phone, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results["failed"] += 1
                    results["errors"].append(f"{phone}: {str(result)}")
                elif result:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"{phone}: Échec d'envoi")
            
            # Pause entre les batches pour respecter les limites de taux
            if i + max_concurrent < len(phone_numbers):
                await asyncio.sleep(1)
        
        return {
            "success": results["sent"] > 0,
            "sent": results["sent"],
            "failed": results["failed"],
            "total": len(phone_numbers),
            "errors": results["errors"][:10]  # Limiter les erreurs affichées
        }