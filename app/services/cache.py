"""
Service de cache AlloBara
Cache Redis avec fallback en mémoire
"""

import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List
import logging

# Tentative d'import Redis avec fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Redis non disponible, utilisation du cache mémoire")

from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis_client = None
        self._memory_cache = {}  # Cache en mémoire comme fallback
        self._memory_expiry = {}  # Expiration pour le cache mémoire
        
        # Initialiser Redis si disponible
        if REDIS_AVAILABLE and settings.REDIS_URL:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=False,  # Garder bytes pour pickle
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True
                )
                # Tester la connexion
                self.redis_client.ping()
                logger.info("✅ Cache Redis connecté")
            except Exception as e:
                logger.warning(f"⚠️ Redis non disponible, utilisation cache mémoire: {e}")
                self.redis_client = None
    
    @property
    def is_redis_available(self) -> bool:
        """Vérifier si Redis est disponible"""
        return self.redis_client is not None
    
    # =========================================
    # OPÉRATIONS CACHE PRINCIPALES
    # =========================================
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Récupérer une valeur du cache
        """
        try:
            if self.is_redis_available:
                return await self._redis_get(key)
            else:
                return self._memory_get(key)
        except Exception as e:
            logger.error(f"Erreur cache get {key}: {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire_seconds: Optional[int] = None
    ) -> bool:
        """
        Stocker une valeur dans le cache
        """
        try:
            if self.is_redis_available:
                return await self._redis_set(key, value, expire_seconds)
            else:
                return self._memory_set(key, value, expire_seconds)
        except Exception as e:
            logger.error(f"Erreur cache set {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Supprimer une clé du cache
        """
        try:
            if self.is_redis_available:
                return await self._redis_delete(key)
            else:
                return self._memory_delete(key)
        except Exception as e:
            logger.error(f"Erreur cache delete {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Vérifier si une clé existe dans le cache
        """
        try:
            if self.is_redis_available:
                return bool(self.redis_client.exists(key))
            else:
                return key in self._memory_cache and not self._is_memory_expired(key)
        except Exception as e:
            logger.error(f"Erreur cache exists {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Définir l'expiration d'une clé
        """
        try:
            if self.is_redis_available:
                return bool(self.redis_client.expire(key, seconds))
            else:
                if key in self._memory_cache:
                    self._memory_expiry[key] = datetime.utcnow() + timedelta(seconds=seconds)
                    return True
                return False
        except Exception as e:
            logger.error(f"Erreur cache expire {key}: {e}")
            return False
    
    # =========================================
    # MÉTHODES REDIS
    # =========================================
    
    async def _redis_get(self, key: str) -> Optional[Any]:
        """Récupérer depuis Redis"""
        try:
            data = self.redis_client.get(key)
            if data is None:
                return None
            
            # Essayer de désérialiser avec pickle d'abord
            try:
                return pickle.loads(data)
            except:
                # Fallback sur JSON si pickle échoue
                try:
                    return json.loads(data.decode('utf-8'))
                except:
                    # Retourner la string brute
                    return data.decode('utf-8')
        except Exception as e:
            logger.error(f"Erreur _redis_get {key}: {e}")
            return None
    
    async def _redis_set(self, key: str, value: Any, expire_seconds: Optional[int]) -> bool:
        """Stocker dans Redis"""
        try:
            # Sérialiser la valeur avec pickle pour préserver les types Python
            try:
                serialized_data = pickle.dumps(value)
            except:
                # Fallback sur JSON
                try:
                    serialized_data = json.dumps(value, ensure_ascii=False).encode('utf-8')
                except:
                    # Fallback sur string
                    serialized_data = str(value).encode('utf-8')
            
            # Stocker avec ou sans expiration
            if expire_seconds:
                return bool(self.redis_client.setex(key, expire_seconds, serialized_data))
            else:
                return bool(self.redis_client.set(key, serialized_data))
        
        except Exception as e:
            logger.error(f"Erreur _redis_set {key}: {e}")
            return False
    
    async def _redis_delete(self, key: str) -> bool:
        """Supprimer de Redis"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Erreur _redis_delete {key}: {e}")
            return False
    
    # =========================================
    # MÉTHODES CACHE MÉMOIRE (FALLBACK)
    # =========================================
    
    def _memory_get(self, key: str) -> Optional[Any]:
        """Récupérer depuis le cache mémoire"""
        if key not in self._memory_cache:
            return None
        
        if self._is_memory_expired(key):
            self._memory_delete(key)
            return None
        
        return self._memory_cache[key]
    
    def _memory_set(self, key: str, value: Any, expire_seconds: Optional[int]) -> bool:
        """Stocker dans le cache mémoire"""
        try:
            self._memory_cache[key] = value
            
            if expire_seconds:
                self._memory_expiry[key] = datetime.utcnow() + timedelta(seconds=expire_seconds)
            elif key in self._memory_expiry:
                del self._memory_expiry[key]
            
            return True
        except Exception as e:
            logger.error(f"Erreur _memory_set {key}: {e}")
            return False
    
    def _memory_delete(self, key: str) -> bool:
        """Supprimer du cache mémoire"""
        try:
            if key in self._memory_cache:
                del self._memory_cache[key]
            if key in self._memory_expiry:
                del self._memory_expiry[key]
            return True
        except Exception as e:
            logger.error(f"Erreur _memory_delete {key}: {e}")
            return False
    
    def _is_memory_expired(self, key: str) -> bool:
        """Vérifier si une clé mémoire a expiré"""
        if key not in self._memory_expiry:
            return False
        return datetime.utcnow() > self._memory_expiry[key]
    
    # =========================================
    # MÉTHODES SPÉCIALISÉES POUR ALLOBARA
    # =========================================
    
    async def cache_user_profile(self, user_id: int, profile_data: Dict, expire_minutes: int = 30) -> bool:
        """
        Mettre en cache le profil d'un utilisateur
        """
        key = f"user:profile:{user_id}"
        return await self.set(key, profile_data, expire_minutes * 60)
    
    async def get_cached_user_profile(self, user_id: int) -> Optional[Dict]:
        """
        Récupérer le profil utilisateur en cache
        """
        key = f"user:profile:{user_id}"
        return await self.get(key)
    
    async def cache_search_results(
        self, 
        search_query: str, 
        filters: Dict, 
        results: List[Dict], 
        expire_minutes: int = 15
    ) -> bool:
        """
        Mettre en cache les résultats de recherche
        """
        # Créer une clé unique basée sur la requête et les filtres
        import hashlib
        filter_str = json.dumps(filters, sort_keys=True)
        query_hash = hashlib.md5(f"{search_query}:{filter_str}".encode()).hexdigest()
        key = f"search:results:{query_hash}"
        
        cache_data = {
            "query": search_query,
            "filters": filters,
            "results": results,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        return await self.set(key, cache_data, expire_minutes * 60)
    
    async def get_cached_search_results(self, search_query: str, filters: Dict) -> Optional[Dict]:
        """
        Récupérer les résultats de recherche en cache
        """
        import hashlib
        filter_str = json.dumps(filters, sort_keys=True)
        query_hash = hashlib.md5(f"{search_query}:{filter_str}".encode()).hexdigest()
        key = f"search:results:{query_hash}"
        
        return await self.get(key)
    
    async def cache_subscription_status(self, user_id: int, status_data: Dict, expire_minutes: int = 60) -> bool:
        """
        Mettre en cache le statut d'abonnement
        """
        key = f"subscription:status:{user_id}"
        return await self.set(key, status_data, expire_minutes * 60)
    
    async def get_cached_subscription_status(self, user_id: int) -> Optional[Dict]:
        """
        Récupérer le statut d'abonnement en cache
        """
        key = f"subscription:status:{user_id}"
        return await self.get(key)
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """
        Invalider tout le cache relatif à un utilisateur
        """
        keys_to_delete = [
            f"user:profile:{user_id}",
            f"subscription:status:{user_id}",
            f"user:stats:{user_id}"
        ]
        
        success = True
        for key in keys_to_delete:
            result = await self.delete(key)
            success = success and result
        
        return success
    
    async def cache_provider_list(
        self, 
        page: int, 
        filters: Dict, 
        providers: List[Dict], 
        expire_minutes: int = 10
    ) -> bool:
        """
        Mettre en cache une liste de prestataires
        """
        import hashlib
        filter_str = json.dumps(filters, sort_keys=True)
        cache_key = hashlib.md5(f"page:{page}:{filter_str}".encode()).hexdigest()
        key = f"providers:list:{cache_key}"
        
        cache_data = {
            "page": page,
            "filters": filters,
            "providers": providers,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        return await self.set(key, cache_data, expire_minutes * 60)
    
    async def get_cached_provider_list(self, page: int, filters: Dict) -> Optional[Dict]:
        """
        Récupérer une liste de prestataires en cache
        """
        import hashlib
        filter_str = json.dumps(filters, sort_keys=True)
        cache_key = hashlib.md5(f"page:{page}:{filter_str}".encode()).hexdigest()
        key = f"providers:list:{cache_key}"
        
        return await self.get(key)
    
    # =========================================
    # GESTION DES SESSIONS ET OTP
    # =========================================
    
    async def store_otp(self, phone_number: str, otp_code: str, expire_minutes: int = 5) -> bool:
        """
        Stocker un code OTP temporairement
        """
        key = f"otp:{phone_number}"
        otp_data = {
            "code": otp_code,
            "created_at": datetime.utcnow().isoformat(),
            "attempts": 0
        }
        return await self.set(key, otp_data, expire_minutes * 60)
    
    async def get_otp(self, phone_number: str) -> Optional[Dict]:
        """
        Récupérer un code OTP
        """
        key = f"otp:{phone_number}"
        return await self.get(key)
    
    async def increment_otp_attempts(self, phone_number: str) -> Optional[int]:
        """
        Incrémenter le compteur de tentatives OTP
        """
        key = f"otp:{phone_number}"
        otp_data = await self.get(key)
        
        if not otp_data:
            return None
        
        otp_data["attempts"] = otp_data.get("attempts", 0) + 1
        
        # Remettre en cache avec la TTL restante
        if await self.set(key, otp_data, 300):  # 5 minutes par défaut
            return otp_data["attempts"]
        
        return None
    
    async def delete_otp(self, phone_number: str) -> bool:
        """
        Supprimer un code OTP
        """
        key = f"otp:{phone_number}"
        return await self.delete(key)
    
    # =========================================
    # LIMITATIONS DE TAUX (RATE LIMITING)
    # =========================================
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        limit: int, 
        window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Vérifier les limitations de taux
        """
        key = f"rate_limit:{identifier}:{window_seconds}"
        
        try:
            # Récupérer le compteur actuel
            current = await self.get(key)
            
            if current is None:
                # Premier appel dans cette fenêtre
                await self.set(key, 1, window_seconds)
                return {
                    "allowed": True,
                    "count": 1,
                    "limit": limit,
                    "remaining": limit - 1,
                    "reset_in": window_seconds
                }
            
            count = int(current) + 1
            
            if count > limit:
                return {
                    "allowed": False,
                    "count": count,
                    "limit": limit,
                    "remaining": 0,
                    "reset_in": window_seconds
                }
            
            # Incrémenter le compteur
            await self.set(key, count, window_seconds)
            
            return {
                "allowed": True,
                "count": count,
                "limit": limit,
                "remaining": limit - count,
                "reset_in": window_seconds
            }
            
        except Exception as e:
            logger.error(f"Erreur check_rate_limit {identifier}: {e}")
            # En cas d'erreur, autoriser la requête
            return {
                "allowed": True,
                "count": 0,
                "limit": limit,
                "remaining": limit,
                "reset_in": window_seconds,
                "error": str(e)
            }
    
    # =========================================
    # STATISTIQUES ET MÉTRIQUES
    # =========================================
    
    async def increment_counter(self, counter_name: str, increment: int = 1) -> Optional[int]:
        """
        Incrémenter un compteur
        """
        key = f"counter:{counter_name}"
        
        try:
            if self.is_redis_available:
                return self.redis_client.incrby(key, increment)
            else:
                # Fallback mémoire
                current = self._memory_cache.get(key, 0)
                new_value = current + increment
                self._memory_cache[key] = new_value
                return new_value
        except Exception as e:
            logger.error(f"Erreur increment_counter {counter_name}: {e}")
            return None
    
    async def get_counter(self, counter_name: str) -> int:
        """
        Récupérer la valeur d'un compteur
        """
        key = f"counter:{counter_name}"
        value = await self.get(key)
        return int(value) if value is not None else 0
    
    async def cache_daily_stats(self, date_str: str, stats: Dict, expire_hours: int = 25) -> bool:
        """
        Mettre en cache les statistiques journalières
        """
        key = f"stats:daily:{date_str}"
        return await self.set(key, stats, expire_hours * 3600)
    
    async def get_cached_daily_stats(self, date_str: str) -> Optional[Dict]:
        """
        Récupérer les statistiques journalières en cache
        """
        key = f"stats:daily:{date_str}"
        return await self.get(key)
    
    # =========================================
    # ADMINISTRATION ET MAINTENANCE
    # =========================================
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Informations sur l'état du cache
        """
        info = {
            "cache_type": "redis" if self.is_redis_available else "memory",
            "redis_available": self.is_redis_available
        }
        
        try:
            if self.is_redis_available:
                redis_info = self.redis_client.info()
                info.update({
                    "redis_version": redis_info.get("redis_version"),
                    "used_memory": redis_info.get("used_memory_human"),
                    "connected_clients": redis_info.get("connected_clients"),
                    "total_commands_processed": redis_info.get("total_commands_processed")
                })
            else:
                info.update({
                    "memory_cache_keys": len(self._memory_cache),
                    "memory_cache_with_expiry": len(self._memory_expiry)
                })
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    async def flush_cache(self) -> bool:
        """
        Vider complètement le cache
        """
        try:
            if self.is_redis_available:
                return bool(self.redis_client.flushdb())
            else:
                self._memory_cache.clear()
                self._memory_expiry.clear()
                return True
        except Exception as e:
            logger.error(f"Erreur flush_cache: {e}")
            return False
    
    async def cleanup_expired_keys(self) -> int:
        """
        Nettoyer les clés expirées du cache mémoire
        """
        if self.is_redis_available:
            # Redis gère automatiquement l'expiration
            return 0
        
        expired_keys = []
        now = datetime.utcnow()
        
        for key, expiry_time in self._memory_expiry.items():
            if now > expiry_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._memory_delete(key)
        
        return len(expired_keys)
    
    # =========================================
    # MÉTHODES UTILITAIRES
    # =========================================
    
    def _generate_cache_key(self, *parts: Any) -> str:
        """
        Générer une clé de cache cohérente
        """
        return ":".join(str(part) for part in parts)
    
    async def get_or_set(
        self, 
        key: str, 
        value_func, 
        expire_seconds: Optional[int] = None
    ) -> Any:
        """
        Récupérer une valeur ou la calculer et la mettre en cache
        """
        # Essayer de récupérer depuis le cache
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Calculer la valeur
        try:
            if asyncio.iscoroutinefunction(value_func):
                value = await value_func()
            else:
                value = value_func()
            
            # Mettre en cache
            await self.set(key, value, expire_seconds)
            return value
            
        except Exception as e:
            logger.error(f"Erreur get_or_set {key}: {e}")
            return None

# =========================================
# INSTANCE GLOBALE
# =========================================

# Instance globale du service de cache
cache_service = CacheService()

# =========================================
# FONCTIONS UTILITAIRES
# =========================================

async def get_cached_or_compute(
    key: str,
    compute_func,
    expire_seconds: int = 3600
) -> Any:
    """
    Fonction utilitaire pour récupérer depuis le cache ou calculer
    """
    return await cache_service.get_or_set(key, compute_func, expire_seconds)