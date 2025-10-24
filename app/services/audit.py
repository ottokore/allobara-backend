"""
Service d'audit AlloBara
Traçabilité des actions, logs et conformité
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func

from app.models.audit import AuditLog, AuditAction, AuditLevel
from app.models.user import User
from app.core.config import settings

class AuditService:
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================
    # CRÉATION D'AUDIT LOGS
    # =========================================
    
    def log_action(
        self,
        action: AuditAction,
        description: str,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        level: AuditLevel = AuditLevel.INFO,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        **kwargs
    ) -> int:
        """
        Créer un log d'audit
        """
        try:
            # Récupérer les infos utilisateur si ID fourni
            user_phone = None
            user_role = None
            if user_id:
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user_phone = user.phone
                    user_role = user.role.value
            
            # Créer le log
            audit_log = AuditLog(
                action=action,
                level=level,
                user_id=user_id,
                user_phone=user_phone,
                user_role=user_role,
                resource_type=resource_type,
                resource_id=resource_id,
                description=description,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                method=method,
                **kwargs
            )
            
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)
            
            return audit_log.id
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur log_action: {e}")
            return None
    
    # =========================================
    # LOGS SPÉCIALISÉS PAR DOMAINE
    # =========================================
    
    def log_user_created(self, user_id: int, ip_address: str = None) -> int:
        """
        Log de création d'utilisateur
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        description = f"Création du compte utilisateur {user.phone}" if user else f"Création du compte ID {user_id}"
        
        return self.log_action(
            action=AuditAction.USER_CREATED,
            description=description,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            level=AuditLevel.INFO,
            ip_address=ip_address
        )
    
    def log_user_login(self, user_id: int, success: bool, ip_address: str = None, user_agent: str = None) -> int:
        """
        Log de connexion utilisateur
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if success:
            description = f"Connexion réussie: {user.phone if user else f'ID {user_id}'}"
            level = AuditLevel.INFO
        else:
            description = f"Tentative de connexion échouée: {user.phone if user else f'ID {user_id}'}"
            level = AuditLevel.WARNING
        
        return self.log_action(
            action=AuditAction.USER_LOGIN,
            description=description,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            level=level,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_subscription_created(self, subscription_id: int, user_id: int, plan: str, amount: float) -> int:
        """
        Log de création d'abonnement
        """
        formatted_amount = f"{int(amount):,} FCFA".replace(",", " ")
        description = f"Création abonnement {plan} - {formatted_amount}"
        
        return self.log_action(
            action=AuditAction.SUBSCRIPTION_CREATED,
            description=description,
            user_id=user_id,
            resource_type="subscription",
            resource_id=subscription_id,
            level=AuditLevel.INFO,
            new_values={"plan": plan, "amount": amount}
        )
    
    def log_payment_completed(self, payment_id: str, user_id: int, amount: float, provider: str) -> int:
        """
        Log de paiement réussi
        """
        formatted_amount = f"{int(amount):,} FCFA".replace(",", " ")
        description = f"Paiement confirmé: {formatted_amount} via {provider}"
        
        return self.log_action(
            action=AuditAction.PAYMENT_COMPLETED,
            description=description,
            user_id=user_id,
            resource_type="payment",
            resource_id=payment_id,
            level=AuditLevel.INFO,
            new_values={"amount": amount, "provider": provider, "payment_id": payment_id}
        )
    
    def log_payment_failed(self, payment_id: str, user_id: int, amount: float, error: str) -> int:
        """
        Log de paiement échoué
        """
        formatted_amount = f"{int(amount):,} FCFA".replace(",", " ")
        description = f"Échec paiement: {formatted_amount} - {error[:100]}"
        
        return self.log_action(
            action=AuditAction.PAYMENT_FAILED,
            description=description,
            user_id=user_id,
            resource_type="payment",
            resource_id=payment_id,
            level=AuditLevel.ERROR,
            new_values={"amount": amount, "error": error, "payment_id": payment_id}
        )
    
    def log_admin_login(self, admin_id: int, ip_address: str = None, user_agent: str = None) -> int:
        """
        Log de connexion admin
        """
        admin = self.db.query(User).filter(User.id == admin_id).first()
        description = f"Connexion admin: {admin.full_name if admin else f'ID {admin_id}'}"
        
        return self.log_action(
            action=AuditAction.ADMIN_LOGIN,
            description=description,
            user_id=admin_id,
            resource_type="admin",
            resource_id=admin_id,
            level=AuditLevel.WARNING,  # Connexions admin = niveau attention
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    def log_admin_user_blocked(self, admin_id: int, blocked_user_id: int, reason: str) -> int:
        """
        Log de blocage d'utilisateur par admin
        """
        admin = self.db.query(User).filter(User.id == admin_id).first()
        blocked_user = self.db.query(User).filter(User.id == blocked_user_id).first()
        
        description = f"Blocage utilisateur {blocked_user.phone if blocked_user else blocked_user_id} par {admin.full_name if admin else admin_id}"
        
        return self.log_action(
            action=AuditAction.ADMIN_USER_BLOCKED,
            description=description,
            user_id=admin_id,
            resource_type="user",
            resource_id=blocked_user_id,
            level=AuditLevel.WARNING,
            new_values={"reason": reason, "admin_id": admin_id}
        )
    
    def log_admin_withdrawal(self, admin_id: int, amount: float, destination: str, reference: str) -> int:
        """
        Log de retrait d'argent par admin
        """
        admin = self.db.query(User).filter(User.id == admin_id).first()
        formatted_amount = f"{int(amount):,} FCFA".replace(",", " ")
        description = f"Retrait wallet: {formatted_amount} vers {destination} par {admin.full_name if admin else admin_id}"
        
        return self.log_action(
            action=AuditAction.ADMIN_WITHDRAWAL,
            description=description,
            user_id=admin_id,
            resource_type="withdrawal",
            resource_id=reference,
            level=AuditLevel.CRITICAL,  # Retraits = niveau critique
            new_values={"amount": amount, "destination": destination, "reference": reference}
        )
    
    def log_user_profile_updated(self, user_id: int, fields_updated: List[str], old_values: Dict = None, new_values: Dict = None) -> int:
        """
        Log de mise à jour de profil
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        fields_str = ", ".join(fields_updated)
        description = f"Mise à jour profil {user.phone if user else user_id}: {fields_str}"
        
        return self.log_action(
            action=AuditAction.USER_UPDATED,
            description=description,
            user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            level=AuditLevel.INFO,
            old_values=old_values,
            new_values=new_values
        )
    
    # =========================================
    # CONSULTATION DES LOGS
    # =========================================
    
    def get_audit_logs(
        self,
        page: int = 1,
        limit: int = 50,
        user_id: Optional[int] = None,
        action: Optional[AuditAction] = None,
        level: Optional[AuditLevel] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Récupérer les logs d'audit avec filtres
        """
        try:
            query = self.db.query(AuditLog)
            
            # Filtres
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            
            if action:
                query = query.filter(AuditLog.action == action)
            
            if level:
                query = query.filter(AuditLog.level == level)
            
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)
            
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            # Total
            total = query.count()
            
            # Pagination et tri
            offset = (page - 1) * limit
            logs = query.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
            
            # Convertir en dictionnaire
            logs_data = [log.to_dict() for log in logs]
            
            return {
                "logs": logs_data,
                "total": total,
                "page": page,
                "limit": limit,
                "has_next": len(logs) == limit
            }
            
        except Exception as e:
            print(f"Erreur get_audit_logs: {e}")
            return {"logs": [], "total": 0, "page": page, "limit": limit, "has_next": False}
    
    def get_user_activity(self, user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        Activité d'un utilisateur sur X jours
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            logs = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= start_date
                )
            ).order_by(desc(AuditLog.created_at)).all()
            
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            print(f"Erreur get_user_activity: {e}")
            return []
    
    def get_admin_actions(self, admin_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """
        Actions administratives sur X jours
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            logs = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == admin_id,
                    AuditLog.action.like('admin_%'),
                    AuditLog.created_at >= start_date
                )
            ).order_by(desc(AuditLog.created_at)).all()
            
            return [log.to_dict() for log in logs]
            
        except Exception as e:
            print(f"Erreur get_admin_actions: {e}")
            return []
    
    # =========================================
    # STATISTIQUES D'AUDIT
    # =========================================
    
    def get_audit_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Statistiques d'audit sur X jours
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Total des logs
            total_logs = self.db.query(AuditLog).filter(
                AuditLog.created_at >= start_date
            ).count()
            
            # Par niveau
            level_stats = self.db.query(
                AuditLog.level,
                func.count(AuditLog.id).label('count')
            ).filter(
                AuditLog.created_at >= start_date
            ).group_by(AuditLog.level).all()
            
            level_data = {level.value: 0 for level in AuditLevel}
            for level, count in level_stats:
                level_data[level.value] = count
            
            # Par action
            action_stats = self.db.query(
                AuditLog.action,
                func.count(AuditLog.id).label('count')
            ).filter(
                AuditLog.created_at >= start_date
            ).group_by(AuditLog.action).order_by(desc('count')).limit(10).all()
            
            top_actions = [{"action": action.value, "count": count} for action, count in action_stats]
            
            # Utilisateurs les plus actifs
            user_stats = self.db.query(
                AuditLog.user_id,
                AuditLog.user_phone,
                func.count(AuditLog.id).label('count')
            ).filter(
                and_(
                    AuditLog.created_at >= start_date,
                    AuditLog.user_id.isnot(None)
                )
            ).group_by(AuditLog.user_id, AuditLog.user_phone).order_by(desc('count')).limit(10).all()
            
            top_users = []
            for user_id, user_phone, count in user_stats:
                top_users.append({
                    "user_id": user_id,
                    "user_phone": user_phone,
                    "actions_count": count
                })
            
            # Actions critiques récentes
            critical_logs = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.level == AuditLevel.CRITICAL,
                    AuditLog.created_at >= start_date
                )
            ).order_by(desc(AuditLog.created_at)).limit(5).all()
            
            critical_actions = [log.to_dict() for log in critical_logs]
            
            return {
                "period_days": days,
                "total_logs": total_logs,
                "level_breakdown": level_data,
                "top_actions": top_actions,
                "most_active_users": top_users,
                "recent_critical_actions": critical_actions,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Erreur get_audit_statistics: {e}")
            return {}
    
    # =========================================
    # SÉCURITÉ ET DÉTECTION D'ANOMALIES
    # =========================================
    
    def detect_suspicious_activity(self, user_id: int, hours: int = 1) -> Dict[str, Any]:
        """
        Détecter une activité suspecte pour un utilisateur
        """
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Compter les actions dans la période
            total_actions = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= start_time
                )
            ).count()
            
            # Tentatives de connexion échouées
            failed_logins = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.action == AuditAction.USER_LOGIN,
                    AuditLog.level == AuditLevel.WARNING,
                    AuditLog.created_at >= start_time
                )
            ).count()
            
            # IPs distinctes
            distinct_ips = self.db.query(func.distinct(AuditLog.ip_address)).filter(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.created_at >= start_time,
                    AuditLog.ip_address.isnot(None)
                )
            ).count()
            
            # Définir les seuils de suspicion
            is_suspicious = (
                total_actions > 100 or  # Plus de 100 actions par heure
                failed_logins > 5 or    # Plus de 5 échecs de connexion
                distinct_ips > 3        # Plus de 3 IPs différentes
            )
            
            risk_score = min(100, (total_actions * 0.5) + (failed_logins * 10) + (distinct_ips * 15))
            
            return {
                "user_id": user_id,
                "is_suspicious": is_suspicious,
                "risk_score": round(risk_score, 1),
                "period_hours": hours,
                "metrics": {
                    "total_actions": total_actions,
                    "failed_logins": failed_logins,
                    "distinct_ips": distinct_ips
                },
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Erreur detect_suspicious_activity: {e}")
            return {"user_id": user_id, "is_suspicious": False, "error": str(e)}
    
    def get_security_alerts(self) -> List[Dict[str, Any]]:
        """
        Alertes de sécurité basées sur les logs récents
        """
        try:
            alerts = []
            last_hour = datetime.utcnow() - timedelta(hours=1)
            
            # Trop de tentatives de connexion échouées
            failed_login_threshold = 10
            failed_logins = self.db.query(
                AuditLog.ip_address,
                func.count(AuditLog.id).label('count')
            ).filter(
                and_(
                    AuditLog.action == AuditAction.USER_LOGIN,
                    AuditLog.level == AuditLevel.WARNING,
                    AuditLog.created_at >= last_hour,
                    AuditLog.ip_address.isnot(None)
                )
            ).group_by(AuditLog.ip_address).having(func.count(AuditLog.id) >= failed_login_threshold).all()
            
            for ip, count in failed_logins:
                alerts.append({
                    "type": "multiple_failed_logins",
                    "severity": "high",
                    "message": f"IP {ip}: {count} tentatives de connexion échouées en 1h",
                    "ip_address": ip,
                    "count": count
                })
            
            # Actions critiques récentes
            critical_actions = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.level == AuditLevel.CRITICAL,
                    AuditLog.created_at >= last_hour
                )
            ).count()
            
            if critical_actions > 0:
                alerts.append({
                    "type": "critical_actions",
                    "severity": "critical",
                    "message": f"{critical_actions} action(s) critique(s) dans la dernière heure",
                    "count": critical_actions
                })
            
            return alerts
            
        except Exception as e:
            print(f"Erreur get_security_alerts: {e}")
            return []
    
    # =========================================
    # NETTOYAGE ET MAINTENANCE
    # =========================================
    
    def cleanup_old_logs(self, days_to_keep: int = 90) -> Dict[str, Any]:
        """
        Nettoyer les anciens logs (garder seulement les X derniers jours)
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Compter les logs à supprimer
            count_to_delete = self.db.query(AuditLog).filter(
                AuditLog.created_at < cutoff_date
            ).count()
            
            # Garder les logs critiques même anciens (optionnel)
            if settings.KEEP_CRITICAL_AUDIT_LOGS:
                deleted_count = self.db.query(AuditLog).filter(
                    and_(
                        AuditLog.created_at < cutoff_date,
                        AuditLog.level != AuditLevel.CRITICAL
                    )
                ).delete()
            else:
                deleted_count = self.db.query(AuditLog).filter(
                    AuditLog.created_at < cutoff_date
                ).delete()
            
            self.db.commit()
            
            return {
                "success": True,
                "days_kept": days_to_keep,
                "logs_deleted": deleted_count,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            print(f"Erreur cleanup_old_logs: {e}")
            return {"success": False, "error": str(e)}
    
    def export_audit_logs(
        self, 
        start_date: datetime, 
        end_date: datetime, 
        format: str = "json"
    ) -> Optional[str]:
        """
        Exporter les logs d'audit pour une période (conformité)
        """
        try:
            logs = self.db.query(AuditLog).filter(
                and_(
                    AuditLog.created_at >= start_date,
                    AuditLog.created_at <= end_date
                )
            ).order_by(AuditLog.created_at).all()
            
            logs_data = [log.to_dict() for log in logs]
            
            if format.lower() == "json":
                export_data = {
                    "export_metadata": {
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "exported_at": datetime.utcnow().isoformat(),
                        "total_logs": len(logs_data)
                    },
                    "audit_logs": logs_data
                }
                return json.dumps(export_data, indent=2, ensure_ascii=False)
            
            # TODO: Ajouter d'autres formats (CSV, Excel) si nécessaire
            
            return None
            
        except Exception as e:
            print(f"Erreur export_audit_logs: {e}")
            return None