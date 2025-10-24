"""
Service d'intégration CinetPay AlloBara
Gestion des paiements pour les abonnements
"""

import requests
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime

from app.models.payment import Payment, PaymentStatus, PaymentProvider
from app.core.config import settings

class CinetPayService:
    """Service de paiement CinetPay"""
    
    # URLs de l'API CinetPay
    SANDBOX_URL = "https://api-checkout.cinetpay.com/v2/payment"
    PRODUCTION_URL = "https://api-checkout.cinetpay.com/v2/payment"
    
    def __init__(self, db: Session):
        self.db = db
        
        # Clés API (à configurer dans .env)
        self.api_key = getattr(settings, 'CINETPAY_API_KEY', None)
        self.site_id = getattr(settings, 'CINETPAY_SITE_ID', None)
        self.secret_key = getattr(settings, 'CINETPAY_SECRET_KEY', None)
        
        # Mode sandbox ou production
        self.is_sandbox = getattr(settings, 'CINETPAY_SANDBOX', True)
        self.base_url = self.SANDBOX_URL if self.is_sandbox else self.PRODUCTION_URL
    
    # =========================================
    # INITIALISATION DE PAIEMENT
    # =========================================
    
    def initiate_payment(
        self,
        user_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        description: str = "Abonnement AlloBara",
        subscription_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Initialiser un paiement CinetPay
        
        Args:
            user_id: ID de l'utilisateur
            amount: Montant en FCFA
            customer_name: Nom du client
            customer_phone: Téléphone du client
            description: Description du paiement
            subscription_id: ID de l'abonnement (optionnel)
        
        Returns:
            Dict avec success, payment_url, transaction_id
        """
        
        # Vérifier la configuration
        if not self.api_key or not self.site_id:
            return {
                "success": False,
                "message": "CinetPay non configuré. Ajoutez CINETPAY_API_KEY et CINETPAY_SITE_ID dans .env"
            }
        
        try:
            # 1. Créer le paiement dans notre base
            payment = Payment.create_payment(
                self.db,
                user_id=user_id,
                amount=amount,
                customer_phone=customer_phone,
                customer_name=customer_name,
                description=description,
                subscription_id=subscription_id,
                provider=PaymentProvider.CINETPAY
            )
            
            # 2. Préparer les données pour CinetPay
            payload = {
                "apikey": self.api_key,
                "site_id": self.site_id,
                "transaction_id": payment.transaction_id,
                "amount": int(amount),
                "currency": "XOF",
                "description": description,
                "customer_name": customer_name,
                "customer_surname": customer_name,
                "customer_email": f"{customer_phone}@allobara.ci",  # Email fictif si pas fourni
                "customer_phone_number": customer_phone,
                "customer_address": "Abidjan, Côte d'Ivoire",
                "customer_city": "Abidjan",
                "customer_country": "CI",
                "customer_state": "CI",
                "customer_zip_code": "00225",
                "notify_url": f"{self._get_base_app_url()}/api/v1/webhooks/cinetpay",
                "return_url": f"{self._get_base_app_url()}/payment/success",
                "channels": "ALL",  # Tous les moyens de paiement
                "metadata": f"user_id:{user_id},subscription_id:{subscription_id or 0}"
            }
            
            # 3. Appeler l'API CinetPay
            response = requests.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response_data = response.json()
            
            # 4. Traiter la réponse
            if response.status_code == 200 and response_data.get("code") == "201":
                # Succès - récupérer le lien de paiement
                payment_url = response_data["data"]["payment_url"]
                payment_token = response_data["data"]["payment_token"]
                
                # Mettre à jour le paiement
                payment.set_cinetpay_data(payment_token, payment_url)
                payment.provider_response = response_data
                self.db.commit()
                
                return {
                    "success": True,
                    "message": "Paiement initialisé avec succès",
                    "payment_url": payment_url,
                    "transaction_id": payment.transaction_id,
                    "amount": amount,
                    "currency": "XOF"
                }
            else:
                # Erreur CinetPay
                error_message = response_data.get("message", "Erreur inconnue")
                payment.mark_as_failed(error_message=error_message)
                payment.provider_response = response_data
                self.db.commit()
                
                return {
                    "success": False,
                    "message": f"Erreur CinetPay: {error_message}",
                    "error_code": response_data.get("code")
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "message": "Timeout lors de la connexion à CinetPay"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Erreur de connexion: {str(e)}"
            }
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"Erreur interne: {str(e)}"
            }
    
    # =========================================
    # VÉRIFICATION DE PAIEMENT
    # =========================================
    
    def check_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """
        Vérifier le statut d'un paiement auprès de CinetPay
        
        Args:
            transaction_id: ID de transaction AlloBara
        
        Returns:
            Dict avec success, status, details
        """
        
        if not self.api_key or not self.site_id:
            return {
                "success": False,
                "message": "CinetPay non configuré"
            }
        
        try:
            # URL de vérification
            check_url = f"{self.base_url}/check"
            
            payload = {
                "apikey": self.api_key,
                "site_id": self.site_id,
                "transaction_id": transaction_id
            }
            
            response = requests.post(
                check_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("code") == "00":
                payment_data = response_data["data"]
                payment_status = payment_data.get("payment_status")
                
                return {
                    "success": True,
                    "status": payment_status,
                    "amount": payment_data.get("amount"),
                    "currency": payment_data.get("currency"),
                    "payment_method": payment_data.get("payment_method"),
                    "operator_id": payment_data.get("operator_id"),
                    "payment_date": payment_data.get("payment_date"),
                    "metadata": payment_data.get("metadata")
                }
            else:
                return {
                    "success": False,
                    "message": response_data.get("message", "Impossible de vérifier le paiement")
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de la vérification: {str(e)}"
            }
    
    # =========================================
    # TRAITEMENT WEBHOOK
    # =========================================
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traiter une notification webhook de CinetPay
        
        Args:
            webhook_data: Données reçues du webhook
        
        Returns:
            Dict avec success et message
        """
        
        try:
            # Extraire les données importantes
            cpm_trans_id = webhook_data.get("cpm_trans_id")  # ID CinetPay
            transaction_id = webhook_data.get("cpm_custom")   # Notre ID
            payment_status = webhook_data.get("cpm_result")   # ACCEPTED, REFUSED, etc.
            amount = webhook_data.get("cpm_amount")
            
            # Récupérer le paiement
            payment = Payment.get_by_transaction_id(self.db, transaction_id)
            
            if not payment:
                return {
                    "success": False,
                    "message": f"Paiement introuvable: {transaction_id}"
                }
            
            # Mettre à jour le webhook
            payment.update_from_webhook(webhook_data)
            
            # Traiter selon le statut
            if payment_status == "00":  # Succès
                payment.mark_as_success(cinetpay_transaction_id=cpm_trans_id)
                self.db.commit()
                
                return {
                    "success": True,
                    "message": "Paiement confirmé",
                    "payment_id": payment.id,
                    "status": "success"
                }
            else:  # Échec
                error_message = webhook_data.get("cpm_error_message", "Paiement refusé")
                payment.mark_as_failed(error_message=error_message)
                self.db.commit()
                
                return {
                    "success": True,
                    "message": "Paiement échoué enregistré",
                    "payment_id": payment.id,
                    "status": "failed"
                }
                
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"Erreur lors du traitement webhook: {str(e)}"
            }
    
    # =========================================
    # MÉTHODES UTILITAIRES
    # =========================================
    
    def _get_base_app_url(self) -> str:
        """Obtenir l'URL de base de l'application"""
        # En production, récupérer depuis settings
        base_url = getattr(settings, 'APP_BASE_URL', None)
        
        if base_url:
            return base_url
        
        # Par défaut en développement
        if settings.ENVIRONMENT == "development":
            return "http://localhost:8000"
        else:
            return "https://api.allobara.ci"
    
    def get_payment_by_id(self, payment_id: int) -> Optional[Dict[str, Any]]:
        """Récupérer un paiement par son ID"""
        try:
            payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
            
            if payment:
                return payment.to_dict()
            
            return None
            
        except Exception as e:
            print(f"❌ Erreur get_payment_by_id: {e}")
            return None
    
    def get_user_payments(self, user_id: int, limit: int = 10) -> list:
        """Récupérer l'historique des paiements d'un utilisateur"""
        try:
            payments = self.db.query(Payment).filter(
                Payment.user_id == user_id
            ).order_by(Payment.created_at.desc()).limit(limit).all()
            
            return [p.to_dict() for p in payments]
            
        except Exception as e:
            print(f"❌ Erreur get_user_payments: {e}")
            return []