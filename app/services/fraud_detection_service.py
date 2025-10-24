"""
Service de détection de fraude AlloBara
Détecte les abus de la période d'essai et les comptes multiples
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from app.models.device_fingerprint import DeviceFingerprint
from app.models.fraud_log import FraudLog, FraudType, FraudSeverity, FraudAction
from app.models.user import User
from app.models.system_settings import SystemSettings

class FraudDetectionService:
    """Service de détection de fraude"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================
    # DÉTECTION LORS DE L'INSCRIPTION
    # =========================================
    
    def check_signup_fraud(
        self,
        phone_number: str,
        device_id: str,
        device_info: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vérifier si une inscription est suspecte
        
        Args:
            phone_number: Numéro de téléphone
            device_id: ID unique de l'appareil
            device_info: Infos sur l'appareil (optionnel)
            ip_address: Adresse IP (optionnel)
        
        Returns:
            Dict avec fraud_score, is_blocked, reasons
        """
        
        # Vérifier si la détection est activée
        fraud_enabled = SystemSettings.get_setting(
            self.db, 
            "fraud_detection_enabled", 
            default=True
        )
        
        if not fraud_enabled:
            return {
                "fraud_score": 0,
                "is_blocked": False,
                "is_suspicious": False,
                "reasons": [],
                "message": "Détection de fraude désactivée"
            }
        
        fraud_score = 0
        reasons = []
        
        # 1️⃣ Vérifier l'appareil
        device = DeviceFingerprint.get_or_create(self.db, device_id, device_info)
        
        # 2️⃣ Appareil déjà bloqué ?
        if device.is_blocked:
            fraud_score = 100
            reasons.append("Appareil bloqué précédemment")
            
            self._create_fraud_log(
                fraud_type=FraudType.BLOCKED_DEVICE,
                fraud_score=fraud_score,
                phone_number=phone_number,
                device_id=device.id,
                title="Tentative d'inscription depuis appareil bloqué",
                description=f"Raison du blocage: {device.blocked_reason}",
                ip_address=ip_address
            )
            
            return {
                "fraud_score": fraud_score,
                "is_blocked": True,
                "is_suspicious": True,
                "reasons": reasons,
                "message": "Appareil bloqué"
            }
        
        # 3️⃣ Trop de comptes sur le même appareil ?
        max_accounts = SystemSettings.get_setting(
            self.db,
            "max_accounts_per_device",
            default=3
        )
        
        if device.accounts_created >= max_accounts:
            fraud_score += 30
            reasons.append(f"Trop de comptes sur cet appareil ({device.accounts_created}/{max_accounts})")
        
        # 4️⃣ Création rapide après le dernier compte ?
        if device.last_account_created_at:
            hours_since_last = (datetime.utcnow() - device.last_account_created_at).total_seconds() / 3600
            min_hours = SystemSettings.get_setting(
                self.db,
                "min_time_between_trials_hours",
                default=168  # 7 jours
            )
            
            if hours_since_last < min_hours:
                fraud_score += 25
                days = int(hours_since_last / 24)
                reasons.append(f"Création rapide après le dernier compte ({days} jours)")
        
        # 5️⃣ Numéro déjà utilisé ?
        existing_user = self.db.query(User).filter(User.phone == phone_number).first()
        if existing_user:
            fraud_score += 20
            reasons.append("Numéro de téléphone déjà utilisé")
        
        # 6️⃣ Trust score faible ?
        if device.trust_score < 50:
            fraud_score += 15
            reasons.append(f"Score de confiance faible ({device.trust_score:.0f}/100)")
        
        # Déterminer si on bloque
        is_blocked = fraud_score >= 70
        is_suspicious = fraud_score >= 30
        
        # Logger si suspect
        if is_suspicious:
            self._create_fraud_log(
                fraud_type=self._determine_fraud_type(reasons),
                fraud_score=fraud_score,
                phone_number=phone_number,
                device_id=device.id,
                title=f"Inscription suspecte détectée (score: {fraud_score})",
                description="; ".join(reasons),
                ip_address=ip_address,
                detection_rules={"reasons": reasons, "device_accounts": device.accounts_created}
            )
        
        return {
            "fraud_score": fraud_score,
            "is_blocked": is_blocked,
            "is_suspicious": is_suspicious,
            "reasons": reasons,
            "device": {
                "id": device.id,
                "accounts_created": device.accounts_created,
                "trust_score": device.trust_score
            },
            "message": self._get_fraud_message(fraud_score)
        }
    
    # =========================================
    # GESTION DES APPAREILS
    # =========================================
    
    def register_device_for_user(self, user_id: int, device_id: str, phone_number: str) -> bool:
        """Enregistrer l'appareil après une inscription réussie"""
        try:
            device = self.db.query(DeviceFingerprint).filter(
                DeviceFingerprint.device_id == device_id
            ).first()
            
            if device:
                device.increment_account_count(phone_number)
                self.db.commit()
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Erreur register_device_for_user: {e}")
            return False
    
    def get_suspicious_devices(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Récupérer les appareils suspects"""
        try:
            max_accounts = SystemSettings.get_setting(
                self.db,
                "max_accounts_per_device",
                default=3
            )
            
            devices = self.db.query(DeviceFingerprint).filter(
                (DeviceFingerprint.accounts_created > max_accounts) |
                (DeviceFingerprint.trust_score < 50) |
                (DeviceFingerprint.fraud_flags_count > 0)
            ).order_by(
                DeviceFingerprint.fraud_flags_count.desc(),
                DeviceFingerprint.accounts_created.desc()
            ).limit(limit).all()
            
            return [device.to_dict() for device in devices]
            
        except Exception as e:
            print(f"❌ Erreur get_suspicious_devices: {e}")
            return []
    
    def block_device(self, device_id: int, reason: str, admin_id: int = None) -> Dict[str, Any]:
        """Bloquer un appareil manuellement"""
        try:
            device = self.db.query(DeviceFingerprint).filter(
                DeviceFingerprint.id == device_id
            ).first()
            
            if not device:
                return {
                    "success": False,
                    "message": "Appareil introuvable"
                }
            
            device.block(reason, admin_id)
            self.db.commit()
            
            return {
                "success": True,
                "message": f"Appareil bloqué : {device.display_name}",
                "device_id": device.id
            }
            
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"Erreur : {str(e)}"
            }
    
    def unblock_device(self, device_id: int) -> Dict[str, Any]:
        """Débloquer un appareil"""
        try:
            device = self.db.query(DeviceFingerprint).filter(
                DeviceFingerprint.id == device_id
            ).first()
            
            if not device:
                return {
                    "success": False,
                    "message": "Appareil introuvable"
                }
            
            device.unblock()
            self.db.commit()
            
            return {
                "success": True,
                "message": f"Appareil débloqué : {device.display_name}"
            }
            
        except Exception as e:
            self.db.rollback()
            return {
                "success": False,
                "message": f"Erreur : {str(e)}"
            }
    
    # =========================================
    # GESTION DES LOGS
    # =========================================
    
    def get_recent_fraud_logs(self, limit: int = 50, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """Récupérer les logs de fraude récents"""
        try:
            query = self.db.query(FraudLog)
            
            if severity:
                query = query.filter(FraudLog.severity == severity)
            
            logs = query.order_by(
                FraudLog.detected_at.desc()
            ).limit(limit).all()
            
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            print(f"❌ Erreur get_recent_fraud_logs: {e}")
            return []
    
    def get_fraud_stats(self, days: int = 7) -> Dict[str, Any]:
        """Statistiques de fraude"""
        try:
            stats = FraudLog.get_stats(self.db, days=days)
            return stats
            
        except Exception as e:
            print(f"❌ Erreur get_fraud_stats: {e}")
            return {
                "period_days": days,
                "total_detections": 0,
                "by_severity": {},
                "by_type": {},
                "auto_blocked": 0,
                "pending_review": 0
            }
    
    # =========================================
    # MÉTHODES PRIVÉES
    # =========================================
    
    def _create_fraud_log(
        self,
        fraud_type: FraudType,
        fraud_score: int,
        title: str,
        phone_number: Optional[str] = None,
        user_id: Optional[int] = None,
        device_id: Optional[int] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        detection_rules: Optional[Dict] = None
    ):
        """Créer un log de fraude"""
        try:
            FraudLog.create_log(
                self.db,
                fraud_type=fraud_type,
                fraud_score=fraud_score,
                title=title,
                description=description,
                phone_number=phone_number,
                user_id=user_id,
                device_id=device_id,
                ip_address=ip_address,
                detection_rules=detection_rules
            )
        except Exception as e:
            print(f"❌ Erreur _create_fraud_log: {e}")
    
    def _determine_fraud_type(self, reasons: List[str]) -> FraudType:
        """Déterminer le type de fraude principal"""
        reasons_str = " ".join(reasons).lower()
        
        if "appareil" in reasons_str and "comptes" in reasons_str:
            return FraudType.MULTIPLE_ACCOUNTS
        elif "rapide" in reasons_str or "création" in reasons_str:
            return FraudType.RAPID_CREATION
        elif "numéro" in reasons_str and "utilisé" in reasons_str:
            return FraudType.PHONE_REUSE
        elif "bloqué" in reasons_str:
            return FraudType.BLOCKED_DEVICE
        else:
            return FraudType.SUSPICIOUS_TIMING
    
    def _get_fraud_message(self, fraud_score: int) -> str:
        """Message selon le score de fraude"""
        if fraud_score >= 70:
            return "Inscription bloquée : activité suspecte détectée"
        elif fraud_score >= 50:
            return "Inscription en attente de vérification manuelle"
        elif fraud_score >= 30:
            return "Inscription autorisée mais signalée"
        else:
            return "Inscription autorisée"