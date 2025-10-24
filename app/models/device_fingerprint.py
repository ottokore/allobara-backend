"""
Modèle DeviceFingerprint AlloBara
Détection et tracking des appareils pour prévenir les abus
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from app.db.database import Base

# =========================================
# TABLE D'ASSOCIATION USER-DEVICE
# =========================================

user_devices = Table(
    'user_devices',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('device_id', Integer, ForeignKey('device_fingerprints.id'), primary_key=True),
    Column('linked_at', DateTime, default=datetime.utcnow)
)

# =========================================
# MODÈLE DEVICE FINGERPRINT
# =========================================

class DeviceFingerprint(Base):
    """
    Empreinte d'appareil pour détecter les comptes multiples
    Utilisé pour prévenir l'abus de la période d'essai
    """
    __tablename__ = "device_fingerprints"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), unique=True, index=True, nullable=False)
    
    # =====================================
    # INFORMATIONS APPAREIL
    # =====================================
    device_name = Column(String(200), nullable=True)
    device_model = Column(String(100), nullable=True)
    device_brand = Column(String(100), nullable=True)
    os_name = Column(String(50), nullable=True)
    os_version = Column(String(50), nullable=True)
    
    # =====================================
    # TRACKING DES COMPTES
    # =====================================
    accounts_created = Column(Integer, default=0, nullable=False)
    last_account_phone = Column(String(20), nullable=True)
    last_account_created_at = Column(DateTime, nullable=True)
    
    # =====================================
    # STATUT ET BLOCAGE
    # =====================================
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_reason = Column(Text, nullable=True)
    blocked_at = Column(DateTime, nullable=True)
    
    # =====================================
    # MÉTRIQUES DE CONFIANCE
    # =====================================
    trust_score = Column(Float, default=100.0, nullable=False)
    fraud_flags_count = Column(Integer, default=0, nullable=False)
    
    # =====================================
    # HORODATAGE
    # =====================================
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @property
    def is_suspicious(self) -> bool:
        """Vérifier si l'appareil est suspect"""
        return (
            self.accounts_created > 3 or
            self.fraud_flags_count > 0 or
            self.trust_score < 50
        )
    
    def increment_account_count(self, phone_number: str):
        """Incrémenter le compteur de comptes"""
        self.accounts_created += 1
        self.last_account_phone = phone_number
        self.last_account_created_at = datetime.utcnow()
        self.last_seen_at = datetime.utcnow()
        
        # Réduire le score de confiance si trop de comptes
        if self.accounts_created > 3:
            self.trust_score = max(0, self.trust_score - 20)
    
    def block(self, reason: str):
        """Bloquer l'appareil"""
        self.is_blocked = True
        self.blocked_reason = reason
        self.blocked_at = datetime.utcnow()
        self.trust_score = 0
    
    @classmethod
    def get_or_create(cls, db, device_id: str, device_info: dict = None):
        """Récupérer ou créer une empreinte d'appareil"""
        device = db.query(cls).filter(cls.device_id == device_id).first()
        
        if device:
            device.last_seen_at = datetime.utcnow()
            db.commit()
            return device
        
        # Créer un nouveau device
        device = cls(device_id=device_id)
        
        if device_info:
            device.device_name = device_info.get("device_name")
            device.device_model = device_info.get("device_model")
            device.device_brand = device_info.get("device_brand")
            device.os_name = device_info.get("os_name")
            device.os_version = device_info.get("os_version")
        
        db.add(device)
        db.commit()
        db.refresh(device)
        return device