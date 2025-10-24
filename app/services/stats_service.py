# backend/app/services/stats_service.py
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from app.models.daily_stats import DailyStats
from app.models.user import User
from typing import Optional, Dict, List

class StatsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_today_stats(self, user_id: int) -> DailyStats:
        """Récupérer ou créer les stats du jour pour un utilisateur"""
        today = date.today()
        
        stats = self.db.query(DailyStats).filter(
            DailyStats.user_id == user_id,
            DailyStats.date == today
        ).first()
        
        if not stats:
            stats = DailyStats(
                user_id=user_id,
                date=today,
                profile_views=0,
                contacts_received=0,
                contacts_responded=0,
                profile_shares=0,
                favorites_added=0
            )
            self.db.add(stats)
            self.db.commit()
            self.db.refresh(stats)
        
        return stats
    
    def increment_profile_views(self, user_id: int) -> bool:
        """Incrémenter le nombre de vues du profil"""
        try:
            stats = self.get_or_create_today_stats(user_id)
            stats.profile_views += 1
            self.db.commit()
            return True
        except Exception as e:
            print(f"Erreur increment_profile_views: {e}")
            self.db.rollback()
            return False
    
    def increment_contacts_received(self, user_id: int) -> bool:
        """Incrémenter le nombre de contacts reçus"""
        try:
            stats = self.get_or_create_today_stats(user_id)
            stats.contacts_received += 1
            self.db.commit()
            return True
        except Exception as e:
            print(f"Erreur increment_contacts_received: {e}")
            self.db.rollback()
            return False
    
    def increment_profile_shares(self, user_id: int) -> bool:
        """Incrémenter le nombre de partages"""
        try:
            stats = self.get_or_create_today_stats(user_id)
            stats.profile_shares += 1
            self.db.commit()
            return True
        except Exception as e:
            print(f"Erreur increment_profile_shares: {e}")
            self.db.rollback()
            return False
    
    def increment_favorites(self, user_id: int) -> bool:
        """Incrémenter les ajouts aux favoris"""
        try:
            stats = self.get_or_create_today_stats(user_id)
            stats.favorites_added += 1
            self.db.commit()
            return True
        except Exception as e:
            print(f"Erreur increment_favorites: {e}")
            self.db.rollback()
            return False
    
    def get_stats_for_period(
        self, 
        user_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[DailyStats]:
        """Récupérer les stats pour une période donnée"""
        return self.db.query(DailyStats).filter(
            DailyStats.user_id == user_id,
            DailyStats.date >= start_date,
            DailyStats.date <= end_date
        ).order_by(DailyStats.date).all()
    
    def get_aggregated_stats(
        self, 
        user_id: int, 
        period: str = 'week'
    ) -> Dict:
        """Obtenir les stats agrégées sur une période"""
        today = date.today()
        
        if period == 'today':
            start_date = today
        elif period == 'week':
            start_date = today - timedelta(days=7)
        elif period == 'month':
            start_date = today - timedelta(days=30)
        elif period == '3months':
            start_date = today - timedelta(days=90)
        elif period == 'year':
            start_date = today - timedelta(days=365)
        else:
            start_date = today - timedelta(days=7)
        
        stats = self.get_stats_for_period(user_id, start_date, today)
        
        # Calculer les totaux
        total_views = sum(s.profile_views for s in stats)
        total_contacts = sum(s.contacts_received for s in stats)
        total_shares = sum(s.profile_shares for s in stats)
        total_favorites = sum(s.favorites_added for s in stats)
        
        # Données pour les graphiques (derniers 7 jours)
        chart_data = []
        for i in range(7):
            day = today - timedelta(days=6-i)
            day_stats = next((s for s in stats if s.date == day), None)
            chart_data.append({
                'date': day.isoformat(),
                'profile_views': day_stats.profile_views if day_stats else 0,
                'contacts_received': day_stats.contacts_received if day_stats else 0,
            })
        
        return {
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': today.isoformat(),
            'total_profile_views': total_views,
            'total_contacts_received': total_contacts,
            'total_profile_shares': total_shares,
            'total_favorites_added': total_favorites,
            'chart_data': chart_data,
        }