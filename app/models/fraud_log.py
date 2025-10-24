"""
Modèle FraudLog AlloBara
Historique des détections de fraude et activités suspectes
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.db.database import Base

# =========================================
# ENUMS
# =========================================

class FraudType(str, enum.Enum):
    """Types de fraude détectés"""
    MULTIPLE_ACCOUNTS = "multiple_accounts"
    RAPID_CREATION = "rapid_creation"
    PHONE_REUSE = "phone_reuse"
    SUSPICIOUS_TIMING = "suspicious_timing"
    BLOCKED_DEVICE = "blocked_device"

class FraudSeverity(str, enum.Enum):
    """Niveaux de sévérité"""
    LOW = "low"           # 0-29
    MEDIUM = "medium"     # 30-49
    HIGH = "high"         # 50-69
    CRITICAL = "critical" # 70-100

class FraudAction(str, enum.Enum):
    """Action prise"""
    ALLOWED = "allowed"
    FLAGGED = "flagged"
    BLOCKED = "blocked"

# =========================================
# MODÈLE FRAUD LOG
# =========================================

class FraudLog(Base):
    """
    Logs de détection de fraude
    Enregistre toutes les activités suspectes
    """
    __tablename__ = "fraud_logs"
    
    # =====================================
    # IDENTIFIANTS
    # =====================================
    id = Column(Integer, primary_key=True, index=True)
    
    # =====================================
    # ENTITÉS IMPLIQUÉES
    # =====================================
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    device_id = Column(Integer, ForeignKey("device_fingerprints.id"), nullable=True, index=True)
    phone_number = Column(String(20), nullable=True)
    
    # =====================================
    # DÉTAILS DE LA FRAUDE
    # =====================================
    fraud_type = Column(SQLEnum(FraudType), nullable=False)
    severity = Column(SQLEnum(FraudSeverity), nullable=False)
    fraud_score = Column(Integer, nullable=False)  # 0-100
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # =====================================
    # ACTION PRISE
    # =====================================
    action_taken = Column(SQLEnum(FraudAction), default=FraudAction.FLAGGED, nullable=False)
    auto_blocked = Column(Boolean, default=False, nullable=False)
    
    # =====================================
    # MÉTADONNÉES
    # =====================================
    detection_rules = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # =====================================
    # EXAMEN MANUEL
    # =====================================
    reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_admin_id = Column(Integer, nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # =====================================
    # HORODATAGE
    # =====================================
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # =====================================
    # RELATIONS
    # =====================================
    user = relationship("User", backref="fraud_logs")
    device = relationship("DeviceFingerprint", backref="fraud_logs")
    
    # =====================================
    # MÉTHODES UTILITAIRES
    # =====================================
    
    @classmethod
    def create_log(cls, db, fraud_type: FraudType, fraud_score: int, **kwargs):
        """Créer un nouveau log de fraude"""
        # Déterminer la sévérité basée sur le score
        if fraud_score < 30:
            severity = FraudSeverity.LOW
        elif fraud_score < 50:
            severity = FraudSeverity.MEDIUM
        elif fraud_score < 70:
            severity = FraudSeverity.HIGH
        else:
            severity = FraudSeverity.CRITICAL
        
        # Déterminer l'action automatique
        if fraud_score >= 70:
            action = FraudAction.BLOCKED
            auto_blocked = True
        elif fraud_score >= 50:
            action = FraudAction.FLAGGED
            auto_blocked = False
        else:
            action = FraudAction.ALLOWED
            auto_blocked = False
        
        log = cls(
            fraud_type=fraud_type,
            fraud_score=fraud_score,
            severity=severity,
            action_taken=action,
            auto_blocked=auto_blocked,
            **kwargs
        )
        
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    
    @property
    def severity_emoji(self) -> str:
        """Emoji associé au niveau de sévérité"""
        emojis = {
            FraudSeverity.LOW: "🟢",
            FraudSeverity.MEDIUM: "🟡",
            FraudSeverity.HIGH: "🟠",
            FraudSeverity.CRITICAL: "🔴"
        }
        return emojis.get(self.severity, "⚪")