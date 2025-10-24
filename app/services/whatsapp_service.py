# backend/app/services/whatsapp_service.py
import logging
import base64
from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
import os

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Service d'envoi WhatsApp via Twilio Business API
    """
    
    def __init__(self):
        self.client = None
        self.from_whatsapp = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialise le client Twilio"""
        try:
            # Utiliser directement os.getenv au lieu de settings
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            self.from_whatsapp = f"whatsapp:{os.getenv('TWILIO_PHONE_NUMBER')}"
            
            if not all([account_sid, auth_token, self.from_whatsapp]):
                logger.warning("Configuration Twilio incomplète")
                return
            
            self.client = Client(account_sid, auth_token)
            logger.info("Client Twilio WhatsApp initialisé")
            
        except Exception as e:
            logger.error(f"Erreur initialisation Twilio: {e}")
            self.client = None
    
    async def send_quote_pdf(
        self,
        to_number: str,
        pdf_data: bytes,
        client_name: str,
        description: str,
        provider_name: str
    ) -> bool:
        """
        Envoie un PDF de devis via WhatsApp
        """
        try:
            if not self.client:
                logger.error("Client Twilio non initialisé")
                return False
            
            # Formatter le numéro de téléphone
            to_whatsapp = self._format_whatsapp_number(to_number)
            
            # Message d'accompagnement
            message_body = self._create_quote_message(
                client_name, description, provider_name
            )
            
            # Encoder le PDF en base64 pour l'envoi
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            
            # Envoyer le message avec le PDF
            message = self.client.messages.create(
                from_=self.from_whatsapp,
                to=to_whatsapp,
                body=message_body,
                media_url=[f"data:application/pdf;base64,{pdf_base64}"]
            )
            
            logger.info(f"WhatsApp envoyé avec succès: {message.sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Erreur Twilio: {e}")
            return False
        except Exception as e:
            logger.error(f"Erreur envoi WhatsApp: {e}")
            return False
    
    async def send_simple_message(self, to_number: str, message: str) -> bool:
        """
        Envoie un message WhatsApp simple (sans fichier)
        """
        try:
            if not self.client:
                return False
            
            to_whatsapp = self._format_whatsapp_number(to_number)
            
            message = self.client.messages.create(
                from_=self.from_whatsapp,
                to=to_whatsapp,
                body=message
            )
            
            logger.info(f"Message WhatsApp simple envoyé: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur envoi message simple: {e}")
            return False
    
    def _format_whatsapp_number(self, phone_number: str) -> str:
        """
        Formate le numéro pour WhatsApp
        Exemple: +225070918692 -> whatsapp:+225070918692
        """
        # Nettoyer le numéro
        clean_number = phone_number.replace(' ', '').replace('-', '')
        
        # S'assurer qu'il commence par +
        if not clean_number.startswith('+'):
            clean_number = '+' + clean_number
        
        return f"whatsapp:{clean_number}"
    
    def _create_quote_message(
        self, 
        client_name: str, 
        description: str, 
        provider_name: str
    ) -> str:
        """
        Crée le message d'accompagnement pour le PDF de devis
        """
        # Tronquer la description si elle est trop longue
        short_description = description[:150] + "..." if len(description) > 150 else description
        
        message = f"""📋 **NOUVELLE DEMANDE DE DEVIS - AlloBara**

Bonjour {provider_name},

Vous avez reçu une nouvelle demande de devis via AlloBara.

👤 **Client:** {client_name}
📝 **Description:** {short_description}

Vous trouverez tous les détails dans le document PDF ci-joint.

🎯 **Que faire maintenant ?**
1. Consultez le PDF pour les détails complets
2. Contactez directement le client pour discuter
3. Proposez votre devis et planifiez l'intervention

Bonne prestation !
L'équipe AlloBara 🔧"""

        return message
    
    async def send_notification_to_client(
        self,
        client_phone: str,
        provider_name: str,
        provider_profession: str
    ) -> bool:
        """
        Envoie une notification au client confirmant l'envoi de sa demande
        """
        message = f"""✅ **Demande envoyée - AlloBara**

Bonjour,

Votre demande de devis a été envoyée avec succès à :

👤 **{provider_name}**
🔧 **{provider_profession}**

Le prestataire va vous contacter directement pour discuter des détails et vous proposer un devis.

Merci de faire confiance à AlloBara !"""

        return await self.send_simple_message(client_phone, message)
    
    def is_configured(self) -> bool:
        """
        Vérifie si le service WhatsApp est correctement configuré
        """
        return self.client is not None
    
    async def test_connection(self) -> dict:
        """
        Teste la connexion WhatsApp Business API
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "message": "Client Twilio non configuré"
                }
            
            # Test avec un message vers le numéro de test Twilio
            test_number = "whatsapp:+15551234567"  # Numéro de test Twilio
            
            message = self.client.messages.create(
                from_=self.from_whatsapp,
                to=test_number,
                body="Test de connexion AlloBara WhatsApp Service"
            )
            
            return {
                "success": True,
                "message": "Connexion WhatsApp OK",
                "test_message_sid": message.sid
            }
            
        except TwilioException as e:
            return {
                "success": False,
                "message": f"Erreur Twilio: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur test: {str(e)}"
            }

# Instance globale du service
whatsapp_service = WhatsAppService()

async def send_whatsapp_with_pdf(
    to_number: str,
    pdf_data: bytes,
    client_name: str,
    description: str,
    provider_name: str = "Prestataire"
) -> bool:
    """
    Envoie un PDF de devis via WhatsApp Business API (Twilio)
    """
    try:
        if not whatsapp_service.client:
            logger.error("Client Twilio non initialisé")
            return False
        
        return await whatsapp_service.send_quote_pdf(
            to_number=to_number,
            pdf_data=pdf_data,
            client_name=client_name,
            description=description,
            provider_name=provider_name
        )
    except Exception as e:
        logger.error(f"Erreur envoi WhatsApp: {e}")
        return False

async def send_client_notification(
    client_phone: str,
    provider_name: str,
    provider_profession: str
) -> bool:
    """
    Fonction wrapper pour notifier le client
    """
    return await whatsapp_service.send_notification_to_client(
        client_phone=client_phone,
        provider_name=provider_name,
        provider_profession=provider_profession
    )

async def send_client_notification(
    client_phone: str,
    provider_name: str,
    provider_profession: str
) -> bool:
    """
    Fonction wrapper pour notifier le client
    """
    return await whatsapp_service.send_notification_to_client(
        client_phone=client_phone,
        provider_name=provider_name,
        provider_profession=provider_profession
    )