# backend/app/models/daily_stats.py
from sqlalchemy import Column, Integer, Date, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.database import Base

class DailyStats(Base):
    __tablename__ = "daily_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    
    # Métriques quotidiennes
    profile_views = Column(Integer, default=0)
    contacts_received = Column(Integer, default=0)
    contacts_responded = Column(Integer, default=0)
    profile_shares = Column(Integer, default=0)
    favorites_added = Column(Integer, default=0)
    
    # Relations
    user = relationship("User", back_populates="daily_stats")
    
    # Index composite pour optimiser les requêtes
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'date', unique=True),
    )
    
    @property
    def response_rate(self):
        """Taux de réponse en pourcentage"""
        if self.contacts_received == 0:
            return 0.0
        return (self.contacts_responded / self.contacts_received) * 100