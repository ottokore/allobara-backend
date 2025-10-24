"""
Modèle des paramètres système AlloBara
Gestion centralisée de la configuration modifiable par l'admin
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class SettingType(str, enum.Enum):
    """Types de paramètres"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"

# =========================================
# MODÈLE SYSTEM SETTINGS
# =========================================

class SystemSettings(Base):
    """
    Paramètres système modifiables par l'admin
    Permet de changer des configurations sans redéploiement
    """
    __tablename__ = "system_settings"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    setting_key = Column(String(100), unique=True, index=True, nullable=False)
    setting_value = Column(Text, nullable=False)
    setting_type = Column(SQLEnum(SettingType), default=SettingType.STRING, nullable=False)
    
    # =====================================
    # MÉTADONNÉES
    # =====================================
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)  # "trial", "pricing", "features"
    is_active = Column(Boolean, default=True, nullable=False)
    
    # =====================================
    # AUDIT
    # =====================================
    updated_by_admin_id = Column(Integer, nullable=True)
    updated_by_admin_name = Column(String(100), nullable=True)
    
    # =====================================
    # HORODATAGE
    # =====================================
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @property
    def typed_value(self):
        """Retourner la valeur avec le bon type Python"""
        if self.setting_type == SettingType.BOOLEAN:
            return self.setting_value.lower() in ['true', '1', 'yes', 'on']
        elif self.setting_type == SettingType.INTEGER:
            return int(self.setting_value)
        elif self.setting_type == SettingType.FLOAT:
            return float(self.setting_value)
        else:
            return self.setting_value
    
    @classmethod
    def is_free_trial_enabled(cls, db) -> bool:
        """Vérifier si la période d'essai est activée"""
        setting = db.query(cls).filter(
            cls.setting_key == "free_trial_enabled",
            cls.is_active == True
        ).first()
        
        if setting:
            return setting.typed_value
        return True  # Par défaut : activé
    
    @classmethod
    def toggle_free_trial(cls, db, enabled: bool, admin_id: int = None):
        """Activer/désactiver la période d'essai"""
        setting = db.query(cls).filter(cls.setting_key == "free_trial_enabled").first()
        
        if setting:
            setting.setting_value = str(enabled)
            setting.updated_by_admin_id = admin_id
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(
                setting_key="free_trial_enabled",
                setting_value=str(enabled),
                setting_type=SettingType.BOOLEAN,
                description="Activer/désactiver la période d'essai gratuite",
                category="trial",
                updated_by_admin_id=admin_id
            )
            db.add(setting)
        
        db.commit()
        return setting