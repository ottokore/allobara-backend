# backend/app/api/endpoints/quotes.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional
import logging

# Configuration du logger
logger = logging.getLogger(__name__)

router = APIRouter()

class QuoteRequestSchema(BaseModel):
    provider_id: str
    provider_name: str
    provider_profession: str
    provider_phone: str
    description: str
    client_first_name: str
    client_last_name: str
    client_phone: str
    request_date: datetime

    @validator('description')
    def validate_description(cls, v):
        if len(v.strip()) < 20:
            raise ValueError('La description doit contenir au moins 20 caractères')
        return v.strip()

    @validator('provider_phone', 'client_phone')
    def validate_phone(cls, v):
        # Validation basique du numéro de téléphone
        if not v.startswith('+'):
            raise ValueError('Le numéro doit commencer par un indicatif pays (+)')
        # Enlever le + et vérifier que le reste ne contient que des chiffres
        digits = v[1:].replace(' ', '')
        if not digits.isdigit() or len(digits) < 8:
            raise ValueError('Format de numéro de téléphone invalide')
        return v

    @validator('client_first_name', 'client_last_name', 'provider_name')
    def validate_names(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Le nom doit contenir au moins 2 caractères')
        return v.strip()

class QuoteResponseSchema(BaseModel):
    success: bool
    message: str
    quote_id: Optional[str] = None

@router.post("/send", response_model=QuoteResponseSchema)
async def send_quote_request(
    quote_data: QuoteRequestSchema,
    background_tasks: BackgroundTasks
):
    """
    Envoie une demande de devis au prestataire via WhatsApp
    - Génère un PDF professionnel avec les détails
    - Envoie le PDF par WhatsApp au prestataire
    - Retourne le statut d'envoi
    """
    try:
        logger.info(f"Nouvelle demande de devis pour {quote_data.provider_name}")
        
        # Valider les données reçues
        if not quote_data.provider_phone or not quote_data.client_phone:
            raise HTTPException(
                status_code=400,
                detail="Les numéros de téléphone sont requis"
            )

        # Générer un ID unique pour cette demande
        from uuid import uuid4
        quote_id = str(uuid4())
        
        # Ajouter la génération et envoi en tâche de fond
        background_tasks.add_task(
            process_quote_request,
            quote_data.dict(),
            quote_id
        )
        
        logger.info(f"Demande de devis {quote_id} mise en file d'attente")
        
        return QuoteResponseSchema(
            success=True,
            message="Demande de devis en cours d'envoi",
            quote_id=quote_id
        )

    except ValueError as e:
        logger.warning(f"Données invalides: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de la demande: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne du serveur"
        )

@router.post("/test", response_model=dict)
async def test_quote_generation():
    """
    Teste la génération de PDF de devis (mode développement)
    """
    try:
        # Données de test
        test_data = {
            "provider_name": "Jean Test",
            "provider_profession": "Plombier",
            "provider_phone": "+225 07 09 18 86 92",
            "client_first_name": "Marie",
            "client_last_name": "Kouassi",
            "client_phone": "+225 05 04 03 02 01",
            "description": "Test de génération de PDF pour demande de devis",
            "request_date": datetime.now()
        }
        
        # Simuler la génération PDF
        pdf_generated = await generate_quote_pdf(test_data)
        
        return {
            "success": True,
            "message": "Test de génération PDF réussi",
            "pdf_size": len(pdf_generated) if pdf_generated else 0
        }
        
    except Exception as e:
        logger.error(f"Erreur test génération PDF: {e}")
        return {
            "success": False,
            "message": f"Erreur: {str(e)}"
        }

async def process_quote_request(quote_data: dict, quote_id: str):
    """
    Traite la demande de devis en arrière-plan
    1. Génère le PDF
    2. Envoie via WhatsApp
    """
    try:
        logger.info(f"Traitement demande {quote_id}...")
        
        # Étape 1: Générer le PDF
        logger.info("Génération du PDF...")
        from app.services.pdf_generator import generate_quote_pdf
        pdf_bytes = await generate_quote_pdf(quote_data)
        
        if not pdf_bytes:
            raise Exception("Échec de la génération du PDF")
        
        logger.info(f"PDF généré ({len(pdf_bytes)} bytes)")
        
        # Étape 2: Envoyer via WhatsApp au prestataire
        logger.info("Envoi via WhatsApp au prestataire...")
        from app.services.whatsapp_service import send_whatsapp_with_pdf, send_client_notification
        
        whatsapp_sent = await send_whatsapp_with_pdf(
            to_number=quote_data['provider_phone'],
            pdf_data=pdf_bytes,
            client_name=f"{quote_data['client_first_name']} {quote_data['client_last_name']}",
            description=quote_data['description'],
            provider_name=quote_data['provider_name']
        )
        
        if whatsapp_sent:
            logger.info(f"PDF envoyé au prestataire pour {quote_id}")
            
            # Étape 3: Notifier le client
            client_notified = await send_client_notification(
                client_phone=quote_data['client_phone'],
                provider_name=quote_data['provider_name'],
                provider_profession=quote_data['provider_profession']
            )
            
            if client_notified:
                logger.info(f"Client notifié pour {quote_id}")
            else:
                logger.warning(f"Échec notification client pour {quote_id}")
            
            logger.info(f"Demande {quote_id} traitée avec succès")
        else:
            logger.error(f"Échec d'envoi WhatsApp pour {quote_id}")
            
    except Exception as e:
        logger.error(f"Erreur traitement demande {quote_id}: {e}")

async def generate_quote_pdf(quote_data: dict) -> bytes:
    """
    Génère un PDF professionnel pour la demande de devis
    """
    try:
        from app.services.pdf_generator import generate_quote_pdf as gen_pdf
        return await gen_pdf(quote_data)
    except ImportError:
        logger.warning("Service PDF non disponible, utilisation du mock")
        # Fallback en cas de problème d'import
        mock_pdf = b"%PDF-1.4 Mock PDF Content for quote request"
        return mock_pdf
    except Exception as e:
        logger.error(f"Erreur génération PDF: {e}")
        raise

async def send_whatsapp_with_pdf(
    to_number: str, 
    pdf_data: bytes, 
    client_name: str, 
    description: str,
    provider_name: str = "Prestataire"
) -> bool:
    """
    Envoie le PDF de devis via WhatsApp Business API (Twilio)
    """
    try:
        from app.services.whatsapp_service import send_whatsapp_with_pdf as send_wa
        return await send_wa(
            to_number=to_number,
            pdf_data=pdf_data,
            client_name=client_name,
            description=description,
            provider_name=provider_name
        )
    except ImportError:
        logger.warning("Service WhatsApp non disponible, simulation d'envoi")
        # Fallback en cas de problème d'import
        logger.info(f"SIMULATION: Envoi WhatsApp vers {to_number} avec PDF ({len(pdf_data)} bytes)")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi WhatsApp: {e}")
        return False