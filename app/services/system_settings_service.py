"""
Service de gestion des paramètres système AlloBara
Permet à l'admin de modifier les configurations sans redéploiement
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.models.system_settings import SystemSettings, SettingType

class SystemSettingsService:
    """Service pour gérer les paramètres système"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================
    # GESTION PÉRIODE D'ESSAI
    # =========================================
    
    def is_free_trial_enabled(self) -> bool:
        """Vérifier si la période d'essai est activée"""
        return SystemSettings.get_setting(self.db, "free_trial_enabled", default=True)
    
    def get_free_trial_days(self) -> int:
        """Obtenir la durée de la période d'essai"""
        return SystemSettings.get_setting(self.db, "free_trial_days", default=30)
    
    def toggle_free_trial(self, enabled: bool, admin_id: int = None, admin_name: str = None) -> Dict[str, Any]:
        """
        Activer/désactiver la période d'essai
        
        Args:
            enabled: True pour activer, False pour désactiver
            admin_id: ID de l'admin qui fait le changement
            admin_name: Nom de l'admin
        
        Returns:
            Dict avec success et message
        """
        try:
            setting = SystemSettings.toggle_free_trial(
                self.db,
                enabled=enabled,
                admin_id=admin_id,
                admin_name=admin_name
            )
            
            status = "activée" if enabled else "désactivée"
            
            return {
                "success": True,
                "message": f"Période d'essai {status} avec succès",
                "enabled": enabled,
                "updated_by": admin_name,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de la modification : {str(e)}"
            }
    
    def update_free_trial_duration(self, days: int, admin_id: int = None, admin_name: str = None) -> Dict[str, Any]:
        """
        Modifier la durée de la période d'essai
        
        Args:
            days: Nombre de jours (0-365)
            admin_id: ID de l'admin
            admin_name: Nom de l'admin
        
        Returns:
            Dict avec success et message
        """
        try:
            # Validation
            if days < 0 or days > 365:
                return {
                    "success": False,
                    "message": "La durée doit être entre 0 et 365 jours"
                }
            
            setting = SystemSettings.set_setting(
                self.db,
                "free_trial_days",
                days,
                admin_id=admin_id,
                admin_name=admin_name
            )
            
            return {
                "success": True,
                "message": f"Durée de la période d'essai mise à jour : {days} jours",
                "days": days,
                "updated_by": admin_name,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur lors de la modification : {str(e)}"
            }
    
    # =========================================
    # GESTION ANTI-FRAUDE
    # =========================================
    
    def get_max_accounts_per_device(self) -> int:
        """Obtenir le nombre max de comptes par appareil"""
        return SystemSettings.get_setting(self.db, "max_accounts_per_device", default=3)
    
    def update_max_accounts_per_device(self, max_accounts: int, admin_id: int = None) -> Dict[str, Any]:
        """Modifier le nombre max de comptes par appareil"""
        try:
            if max_accounts < 1 or max_accounts > 10:
                return {
                    "success": False,
                    "message": "Le nombre doit être entre 1 et 10"
                }
            
            SystemSettings.set_setting(
                self.db,
                "max_accounts_per_device",
                max_accounts,
                admin_id=admin_id
            )
            
            return {
                "success": True,
                "message": f"Limite mise à jour : {max_accounts} comptes max par appareil",
                "max_accounts": max_accounts
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur : {str(e)}"
            }
    
    def is_fraud_detection_enabled(self) -> bool:
        """Vérifier si la détection de fraude est activée"""
        return SystemSettings.get_setting(self.db, "fraud_detection_enabled", default=True)
    
    def toggle_fraud_detection(self, enabled: bool, admin_id: int = None) -> Dict[str, Any]:
        """Activer/désactiver la détection de fraude"""
        try:
            SystemSettings.set_setting(
                self.db,
                "fraud_detection_enabled",
                enabled,
                admin_id=admin_id
            )
            
            status = "activée" if enabled else "désactivée"
            
            return {
                "success": True,
                "message": f"Détection de fraude {status}",
                "enabled": enabled
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur : {str(e)}"
            }
    
    # =========================================
    # GESTION GÉNÉRALE DES PARAMÈTRES
    # =========================================
    
    def get_all_settings(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Récupérer tous les paramètres système
        
        Args:
            category: Filtrer par catégorie (trial, fraud, pricing, etc.)
        
        Returns:
            Liste des paramètres
        """
        try:
            query = self.db.query(SystemSettings).filter(SystemSettings.is_active == True)
            
            if category:
                query = query.filter(SystemSettings.category == category)
            
            settings = query.order_by(SystemSettings.category, SystemSettings.setting_key).all()
            
            return [
                {
                    "id": s.id,
                    "key": s.setting_key,
                    "value": s.typed_value,
                    "type": s.setting_type.value,
                    "description": s.description,
                    "category": s.category,
                    "updated_by": s.updated_by_admin_name,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None
                }
                for s in settings
            ]
            
        except Exception as e:
            print(f"❌ Erreur get_all_settings: {e}")
            return []
    
    def get_setting_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Récupérer un paramètre spécifique"""
        try:
            setting = self.db.query(SystemSettings).filter(
                SystemSettings.setting_key == key,
                SystemSettings.is_active == True
            ).first()
            
            if not setting:
                return None
            
            return {
                "id": setting.id,
                "key": setting.setting_key,
                "value": setting.typed_value,
                "raw_value": setting.setting_value,
                "type": setting.setting_type.value,
                "description": setting.description,
                "category": setting.category,
                "updated_by": setting.updated_by_admin_name,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
            }
            
        except Exception as e:
            print(f"❌ Erreur get_setting_by_key: {e}")
            return None
    
    def update_setting(self, key: str, value: Any, admin_id: int = None, admin_name: str = None) -> Dict[str, Any]:
        """Mettre à jour un paramètre"""
        try:
            SystemSettings.set_setting(
                self.db,
                key=key,
                value=value,
                admin_id=admin_id,
                admin_name=admin_name
            )
            
            return {
                "success": True,
                "message": f"Paramètre '{key}' mis à jour",
                "key": key,
                "value": value
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Erreur : {str(e)}"
            }
    
    # =========================================
    # DASHBOARD ADMIN
    # =========================================
    
    def get_trial_settings_summary(self) -> Dict[str, Any]:
        """Résumé des paramètres de période d'essai pour le dashboard admin"""
        try:
            return {
                "enabled": self.is_free_trial_enabled(),
                "duration_days": self.get_free_trial_days(),
                "max_accounts_per_device": self.get_max_accounts_per_device(),
                "fraud_detection_enabled": self.is_fraud_detection_enabled()
            }
            
        except Exception as e:
            print(f"❌ Erreur get_trial_settings_summary: {e}")
            return {
                "enabled": True,
                "duration_days": 30,
                "max_accounts_per_device": 3,
                "fraud_detection_enabled": True
            }