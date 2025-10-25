"""
Service d'authentification AlloBara - VERSION REDIS ASYNC
Gestion complète de l'auth: OTP, PIN, JWT
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.security import (
    hash_pin, verify_pin, generate_otp, create_access_token,
    verify_token, generate_referral_code, sanitize_phone_number,
    create_admin_token, verify_admin_token
)
from app.core.config import settings
from app.models.user import User
from app.services.sms import SMSService
from app.services.cache import CacheService  # ⭐ AJOUTÉ POUR REDIS

import logging
logger = logging.getLogger(__name__)

# ✅ Cache Redis au lieu de cache mémoire local

class AuthService:
    
    def __init__(self, db: Session):
        self.db = db
        self.sms_service = SMSService()
        self.cache = CacheService()  # ⭐ Instance du cache
    
    def _store_otp_sync(self, phone_number: str, otp_code: str) -> None:
        """
        Stocker l'OTP dans Redis (10 minutes) - Version synchrone
        """
        expires_in = 600  # 10 minutes en secondes
        redis_key = f"otp:{phone_number}"
        
        # Appeler la méthode async de manière synchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                self.cache.set(redis_key, otp_code, expire_seconds=expires_in)
            )
            logger.info(f"📱 OTP stocké dans Redis pour {phone_number}: {otp_code} (expire dans 10min)")
        finally:
            loop.close()
    
    def _get_otp_sync(self, phone_number: str) -> Optional[str]:
        """
        Récupérer l'OTP depuis Redis - Version synchrone
        """
        redis_key = f"otp:{phone_number}"
        
        # Appeler la méthode async de manière synchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            otp_code = loop.run_until_complete(self.cache.get(redis_key))
            
            if otp_code:
                logger.info(f"✅ OTP trouvé dans Redis pour {phone_number}: {otp_code}")
                return otp_code
            else:
                logger.warning(f"❌ Aucun OTP trouvé dans Redis pour {phone_number}")
                return None
        finally:
            loop.close()
    
    def _clear_otp_sync(self, phone_number: str) -> None:
        """
        Supprimer l'OTP de Redis - Version synchrone
        """
        redis_key = f"otp:{phone_number}"
        
        # Appeler la méthode async de manière synchrone
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.cache.delete(redis_key))
            logger.info(f"🗑️ OTP supprimé de Redis pour {phone_number}")
        finally:
            loop.close()
    
    async def send_otp(self, phone_number: str) -> Dict[str, Any]:
        """
        Envoyer un code OTP par WhatsApp
        """
        try:
            # Nettoyer le numéro de téléphone
            clean_phone = sanitize_phone_number(phone_number)
            logger.info(f"📞 Envoi OTP pour: {phone_number} -> {clean_phone}")
            
            # Générer le code OTP
            otp_code = generate_otp()
            
            # Stocker dans Redis
            self._store_otp_sync(clean_phone, otp_code)
            
            # Message à envoyer
            message = f"Votre code AlloBara est: {otp_code}. Ce code expire dans 10 minutes."
            
            # Envoyer via SMS/WhatsApp (ou afficher dans le terminal pour la démo)
            if settings.DEMO_MODE or True:  # Force demo mode
                print(f"\n" + "="*50)
                print(f"🚀 ALLOBARA - CODE OTP")
                print(f"="*50)
                print(f"📱 Téléphone: {clean_phone}")
                print(f"🔑 Code: {otp_code}")
                print(f"⏰ Valide pendant: 10 minutes")
                print(f"💬 Message: {message}")
                print(f"="*50 + "\n")
                success = True
            else:
                success = await self.sms_service.send_whatsapp_message(clean_phone, message)
            
            if success:
                return {
                    "success": True,
                    "message": "Code OTP envoyé avec succès",
                    "expires_in": 600,  # 10 minutes = 600 secondes
                    "phone": clean_phone
                }
            else:
                return {
                    "success": False,
                    "message": "Erreur lors de l'envoi du code OTP"
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur send_otp: {e}")
            return {
                "success": False,
                "message": "Erreur technique lors de l'envoi"
            }
    
    async def verify_otp(self, phone_number: str, otp_code: str) -> Dict[str, Any]:
        """
        Vérifier le code OTP
        """
        try:
            clean_phone = sanitize_phone_number(phone_number)
            logger.info(f"🔐 Vérification OTP: {phone_number} -> {clean_phone}, code: {otp_code}")
            
            # Récupérer l'OTP depuis Redis
            stored_otp = self._get_otp_sync(clean_phone)
            
            if not stored_otp:
                logger.warning(f"❌ OTP non trouvé ou expiré pour {clean_phone}")
                return {
                    "success": False,
                    "message": "Code OTP expiré ou inexistant"
                }
            
            # Vérifier le code (conversion en string pour sécurité)
            stored_code = str(stored_otp).strip()
            input_code = str(otp_code).strip()
            
            logger.info(f"🔍 Comparaison: '{stored_code}' vs '{input_code}'")
            
            if stored_code != input_code:
                logger.warning(f"❌ Code incorrect pour {clean_phone}: reçu '{input_code}', attendu '{stored_code}'")
                return {
                    "success": False,
                    "message": "Code OTP incorrect"
                }
            
            # Code valide, le supprimer du cache
            self._clear_otp_sync(clean_phone)
            logger.info(f"✅ OTP vérifié avec succès pour {clean_phone}")
            
            return {
                "success": True,
                "message": "Code OTP vérifié avec succès"
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur verify_otp: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la vérification"
            }
    
    def debug_list_active_otps(self) -> Dict[str, Any]:
        """
        Lister tous les OTP actifs dans Redis (uniquement pour le debug)
        Note: Cette méthode ne peut pas lister facilement sans la méthode keys()
        """
        return {
            "message": "Liste des OTP non disponible (méthode keys() non implémentée dans CacheService)",
            "count": 0
        }
    def debug_list_active_otps(self) -> Dict[str, Any]:
        """
        Lister tous les OTP actifs (uniquement pour le debug)
        """
        global _MODULE_OTP_CACHE
        current_time = datetime.utcnow()
        active_otps = {}
        
        for phone, data in _MODULE_OTP_CACHE.items():
            time_left = data["expires_at"] - current_time
            active_otps[phone] = {
                "code": data["code"],
                "expires_at": data["expires_at"].isoformat(),
                "time_left_seconds": int(time_left.total_seconds()),
                "attempts": data["attempts"]
            }
        
        return {
            "current_time": current_time.isoformat(),
            "active_otps": active_otps,
            "count": len(active_otps)
        }

    async def create_user_with_pin(
        self, 
        phone_number: str, 
        pin_code: str
    ) -> Dict[str, Any]:
        """
        Créer un utilisateur après vérification OTP avec période d'essai gratuite
        """
        try:
            clean_phone = sanitize_phone_number(phone_number)
            logger.info(f"👤 Création utilisateur pour {clean_phone}")
            
            # Vérifier si l'utilisateur existe déjà  
            existing_user = self.db.query(User).filter(
                User.phone == clean_phone
            ).first()
            
            if existing_user:
                logger.warning(f"⚠️ Utilisateur existe déjà : {clean_phone}")
                return {
                    "success": False,
                    "message": "Un compte existe déjà avec ce numéro"
                }
            
            # Hacher le PIN
            hashed_pin = hash_pin(pin_code)
            
            # Créer l'utilisateur avec période d'essai
            new_user = User(
                phone=clean_phone,
                pin_hash=hashed_pin,
                is_active=True,
                is_verified=False,
                created_at=datetime.utcnow(),
                # Période d'essai gratuite de 30 jours
                trial_expires_at=datetime.utcnow() + timedelta(days=30),
                subscription_status="trial"  # Status d'essai
            )
            
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            
            # Générer le code de parrainage
            referral_code = generate_referral_code(new_user.id)
            new_user.referral_code = referral_code
            self.db.commit()
            
            # Créer le token d'accès
            access_token = create_access_token(subject=new_user.id)
            
            logger.info(f"✅ Utilisateur créé avec succès: {new_user.id}")
            
            return {
                "success": True,
                "message": "Compte créé avec succès",
                "data": {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    "user_id": new_user.id,
                    "phone_number": new_user.phone,
                    "is_profile_complete": False,
                    "has_free_trial": True,  # Période d'essai active
                    "trial_expires_at": new_user.trial_expires_at.isoformat(),
                    "referral_code": referral_code
                }
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Erreur create_user_with_pin: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la création du compte"
            }

    async def login_with_pin(
        self, 
        phone_number: str, 
        pin_code: str
    ) -> Dict[str, Any]:
        """
        Connexion avec numéro et PIN (clavier sécurisé avec disposition aléatoire)
        """
        try:
            clean_phone = sanitize_phone_number(phone_number)
            logger.info(f"🔐 Tentative de connexion: {clean_phone}")
            
            # Chercher l'utilisateur
            user = self.db.query(User).filter(
                and_(
                    User.phone == clean_phone,
                    User.is_active == True,
                    User.is_blocked == False
                )
            ).first()
            
            if not user:
                logger.warning(f"❌ Utilisateur non trouvé: {clean_phone}")
                return {
                    "success": False,
                    "message": "Aucun compte trouvé avec ce numéro"
                }
            
            # Vérifier le PIN
            if not verify_pin(pin_code, user.pin_hash):
                logger.warning(f"❌ PIN incorrect pour: {clean_phone}")
                return {
                    "success": False,
                    "message": "Code PIN incorrect"
                }
            
            # Mettre à jour la dernière connexion
            user.last_login = datetime.utcnow()
            user.last_seen = datetime.utcnow()
            self.db.commit()
            
            # Vérifier si le profil est complet
            is_profile_complete = user.is_profile_complete
            
            # Vérifier le statut d'abonnement (incluant période d'essai)
            has_active_subscription = (
                user.subscription_status == "active" or 
                (user.subscription_status == "trial" and user.trial_expires_at and user.trial_expires_at > datetime.utcnow())
            )
            
            # Créer le token d'accès
            access_token = create_access_token(subject=user.id)
            
            logger.info(f"✅ Connexion réussie: {user.id}")
            
            return {
                "success": True,
                "message": "Connexion réussie",
                "data": {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    "user_id": user.id,
                    "phone_number": user.phone,
                    "is_profile_complete": is_profile_complete,
                    "profile_completion": user.profile_completion_percentage or 0,
                    "has_active_subscription": has_active_subscription,
                    "subscription_status": user.subscription_status,
                    "trial_expires_at": user.trial_expires_at.isoformat() if user.trial_expires_at else None
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur login_with_pin: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la connexion"
            }

    async def reset_pin_request(self, phone_number: str) -> Dict[str, Any]:
        """
        Demander la réinitialisation du PIN
        """
        try:
            clean_phone = sanitize_phone_number(phone_number)
            logger.info(f"🔄 Demande reset PIN pour: {clean_phone}")
            
            # Vérifier si l'utilisateur existe
            user = self.db.query(User).filter(
                User.phone == clean_phone
            ).first()
            
            if not user:
                logger.warning(f"❌ Utilisateur non trouvé pour reset: {clean_phone}")
                return {
                    "success": False,
                    "message": "Aucun compte trouvé avec ce numéro"
                }
            
            # Envoyer un nouvel OTP
            result = await self.send_otp(clean_phone)
            
            if result["success"]:
                logger.info(f"✅ OTP de reset envoyé pour: {clean_phone}")
                return {
                    "success": True,
                    "message": "Code de réinitialisation envoyé par WhatsApp",
                    "expires_in": 600  # 10 minutes
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"❌ Erreur reset_pin_request: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la demande de réinitialisation"
            }
    
    async def reset_pin_confirm(
        self,
        phone_number: str,
        otp_code: str,
        new_pin: str
    ) -> Dict[str, Any]:
        """
        Confirmer la réinitialisation du PIN
        """
        try:
            clean_phone = sanitize_phone_number(phone_number)
            logger.info(f"🔄 Confirmation reset PIN pour: {clean_phone}")
            
            # Vérifier l'OTP
            otp_result = await self.verify_otp(clean_phone, otp_code)
            if not otp_result["success"]:
                logger.warning(f"❌ OTP invalide pour reset PIN: {clean_phone}")
                return otp_result
            
            # Chercher l'utilisateur
            user = self.db.query(User).filter(
                User.phone == clean_phone
            ).first()
            
            if not user:
                logger.warning(f"❌ Utilisateur non trouvé pour confirmation reset: {clean_phone}")
                return {
                    "success": False,
                    "message": "Utilisateur introuvable"
                }
            
            # Mettre à jour le PIN
            user.pin_hash = hash_pin(new_pin)
            user.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"✅ PIN mis à jour pour: {clean_phone}")
            
            return {
                "success": True,
                "message": "Code PIN mis à jour avec succès"
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Erreur reset_pin_confirm: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la mise à jour du PIN"
            }

    def get_current_user(self, token: str) -> Optional[User]:
        """
        Récupérer l'utilisateur actuel depuis le token
        """
        try:
            payload = verify_token(token)  # ✅ Récupère le dict
            if payload is None:
                logger.error("❌ Token invalide ou expiré")
                return None
            
            # ✅ Extraire user_id du payload
            if isinstance(payload, dict):
                user_id = payload.get('user_id')
            else:
                user_id = payload
            
            if user_id is None:
                logger.error("❌ user_id non trouvé dans le payload")
                return None
            
            user = self.db.query(User).filter(
                and_(
                    User.id == int(user_id),  # ✅ Maintenant c'est bien un int
                    User.is_active == True,
                    User.is_blocked == False
                )
            ).first()
            
            return user
            
        except Exception as e:
            logger.error(f"❌ Erreur get_current_user: {e}")
            return None
    
    def get_admin_user(self, token: str) -> Optional[User]:
        """
        Récupérer un utilisateur admin depuis le token
        """
        try:
            token_data = verify_admin_token(token)
            if not token_data:
                return None
            
            user = self.db.query(User).filter(
                and_(
                    User.id == int(token_data["user_id"]),
                    User.is_admin == True,
                    User.is_active == True
                )
            ).first()
            
            return user
            
        except Exception as e:
            logger.error(f"❌ Erreur get_admin_user: {e}")
            return None
    
    async def admin_login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Connexion admin avec username/password
        """
        try:
            logger.info(f"🔐 Tentative connexion admin: {username}")
            
            # Pour la démo, utiliser des credentials hardcodés
            # En production, utiliser une table admin séparée
            if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
                
                # Créer ou récupérer l'admin
                admin_user = self.db.query(User).filter(
                    User.phone == "+22500000000"  # Numéro admin fictif
                ).first()
                
                if not admin_user:
                    admin_user = User(
                        phone="+22500000000",
                        first_name="Admin",
                        last_name="AlloBara",
                        role="admin",
                        is_active=True,
                        is_verified=True,
                        is_admin=True,
                        pin_hash=hash_pin("0000")  # PIN admin par défaut
                    )
                    self.db.add(admin_user)
                    self.db.commit()
                    self.db.refresh(admin_user)
                
                # Créer le token admin
                admin_token = create_admin_token(admin_user.id)
                
                logger.info(f"✅ Connexion admin réussie: {admin_user.id}")
                
                return {
                    "success": True,
                    "message": "Connexion admin réussie",
                    "data": {
                        "access_token": admin_token,
                        "token_type": "bearer",
                        "expires_in": 8 * 3600,  # 8 heures
                        "role": "admin",
                        "user_id": admin_user.id,
                        "permissions": ["dashboard", "users", "finances", "moderation"]
                    }
                }
            else:
                logger.warning(f"❌ Identifiants admin incorrects: {username}")
                return {
                    "success": False,
                    "message": "Identifiants admin incorrects"
                }
                
        except Exception as e:
            logger.error(f"❌ Erreur admin_login: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la connexion admin"
            }
    
    def check_user_exists(self, phone_number: str) -> bool:
        """
        Vérifier si un utilisateur existe avec ce numéro
        """
        clean_phone = sanitize_phone_number(phone_number)
        user = self.db.query(User).filter(User.phone == clean_phone).first()
        return user is not None
    
    def logout_user(self, user_id: int) -> Dict[str, Any]:
        """
        Déconnexion utilisateur (mise à jour last_seen)
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user.last_seen = datetime.utcnow()
                self.db.commit()
            
            logger.info(f"🚪 Déconnexion utilisateur: {user_id}")
            
            return {
                "success": True,
                "message": "Déconnexion réussie"
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur logout_user: {e}")
            return {
                "success": False,
                "message": "Erreur lors de la déconnexion"
            }
    
    def generate_random_keypad_layout(self) -> list:
        """
        Générer une disposition aléatoire du clavier pour la sécurité de connexion
        """
        import random
        
        # Chiffres de 0 à 9
        digits = list(range(10))
        random.shuffle(digits)
        
        # Organiser en grille 3x3 + dernière ligne
        layout = []
        for i in range(0, 9, 3):
            layout.append(digits[i:i+3])
        
        # Dernière ligne : chiffre restant + bouton biométrie + bouton supprimer
        last_row = [digits[9], "biometric", "delete"]
        layout.append(last_row)
        
        logger.info(f"🔢 Nouveau layout clavier généré: {layout}")
        
        return layout
    
    def get_user_profile_summary(self, user_id: int) -> Optional[Dict]:
        """
        Récupérer un résumé du profil utilisateur
        """
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            return {
                "id": user.id,
                "phone": user.phone,
                "full_name": user.full_name,
                "profession": user.profession,
                "city": user.city,
                "is_profile_complete": user.is_profile_complete,
                "profile_completion": user.profile_completion_percentage or 0,
                "has_active_subscription": user.has_active_subscription,
                "subscription_status": user.subscription_status,
                "is_verified": user.is_verified,
                "profile_picture": user.profile_picture,
                "rating_average": user.rating_average or 0,
                "rating_count": user.rating_count or 0,
                "trial_expires_at": user.trial_expires_at.isoformat() if user.trial_expires_at else None
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur get_user_profile_summary: {e}")
            return None
