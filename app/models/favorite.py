"""
Modèle Favorite - Gestion des favoris utilisateurs
Table: favorites (relation many-to-many User <-> Provider)
"""

from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.database import Base


class Favorite(Base):
    """
    Table des favoris - Relation entre utilisateurs et prestataires favoris
    """
    __tablename__ = "favorites"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    user = relationship("User", foreign_keys=[user_id], backref="favorites_given")
    provider = relationship("User", foreign_keys=[provider_id], backref="favorites_received")
    
    # Contrainte d'unicité : un utilisateur ne peut ajouter un prestataire qu'une seule fois
    __table_args__ = (
        UniqueConstraint('user_id', 'provider_id', name='uix_user_provider'),
    )
    
    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, provider_id={self.provider_id})>"
    
    def to_dict(self):
        """Convertir en dictionnaire"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "provider_id": self.provider_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }