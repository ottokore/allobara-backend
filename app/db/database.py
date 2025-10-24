"""
Configuration de la base de données AlloBara
SQLAlchemy + PostgreSQL
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import logging

from app.core.config import settings

# =========================================
# CONFIGURATION DU LOGGER
# =========================================
logger = logging.getLogger(__name__)

# =========================================
# CONFIGURATION DU MOTEUR DE BASE DE DONNÉES
# =========================================

# Configuration du moteur SQLAlchemy
engine_kwargs = {
    "echo": settings.DEBUG,          # Log des requêtes SQL en debug
    "pool_size": 20,                 # Taille du pool de connexions
    "max_overflow": 30,              # Connexions supplémentaires autorisées
    "pool_pre_ping": True,           # Vérification des connexions
    "pool_recycle": 3600,            # Recyclage des connexions après 1h
    "connect_args": {
        "connect_timeout": 10,       # Timeout de connexion
        "application_name": "AlloBara Backend"
    }
}

# Création du moteur de base de données
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# =========================================
# CONFIGURATION DE LA SESSION
# =========================================

# Factory de sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Évite les erreurs après commit
)

# =========================================
# BASE DES MODÈLES
# =========================================

# Classe de base pour tous les modèles
Base = declarative_base()

# =========================================
# DEPENDENCY POUR FASTAPI
# =========================================

def get_db():
    """
    Dependency FastAPI pour obtenir une session de base de données
    Utilisé avec Depends(get_db) dans les endpoints
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Erreur dans la session DB: {e}")
        db.rollback()
        raise
    finally:
        db.close()

# =========================================
# FONCTIONS UTILITAIRES
# =========================================

def create_tables():
    """Créer toutes les tables de la base de données"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tables créées avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création des tables: {e}")
        raise

def drop_tables():
    """Supprimer toutes les tables (DANGER - Utiliser avec précaution)"""
    if settings.ENVIRONMENT == "production":
        raise ValueError("❌ Impossible de supprimer les tables en production!")
    
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("⚠️ Toutes les tables ont été supprimées")
    except Exception as e:
        logger.error(f"❌ Erreur lors de la suppression des tables: {e}")
        raise

def check_database_connection():
    """Vérifier la connexion à la base de données"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.fetchone()[0] == 1:
                logger.info("✅ Connexion à la base de données OK")
                return True
    except Exception as e:
        logger.error(f"❌ Impossible de se connecter à la base de données: {e}")
        return False

def get_database_info():
    """Obtenir des informations sur la base de données"""
    try:
        with engine.connect() as connection:
            # Version PostgreSQL
            version_result = connection.execute(text("SELECT version()"))
            version = version_result.fetchone()[0]
            
            # Nombre de connexions actives
            connections_result = connection.execute(
                text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            )
            active_connections = connections_result.fetchone()[0]
            
            info = {
                "database_url": settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else "masked",
                "version": version.split(',')[0],
                "active_connections": active_connections,
                "pool_size": engine.pool.size(),
                "checked_out": engine.pool.checkedout()
            }
            
            logger.info(f"📊 Info DB: {info}")
            return info
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération des infos DB: {e}")
        return {"error": str(e)}

# =========================================
# EVENTS SQLALCHEMY
# =========================================

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configuration spécifique pour SQLite (si utilisé en test)"""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

@event.listens_for(engine, "first_connect")
def receive_first_connect(dbapi_connection, connection_record):
    """Event déclenché à la première connexion"""
    logger.info("🔌 Première connexion à la base de données établie")

@event.listens_for(SessionLocal, "after_transaction_end")
def restart_savepoint(session, transaction):
    """Redémarrer le savepoint après chaque transaction"""
    if transaction.nested and not transaction._parent.nested:
        session.expire_all()

# =========================================
# CONTEXT MANAGER POUR SESSIONS
# =========================================

class DatabaseSession:
    """Context manager pour gérer les sessions de base de données"""
    
    def __init__(self):
        self.db = None
    
    def __enter__(self):
        self.db = SessionLocal()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.db.rollback()
            logger.error(f"Transaction rollback: {exc_val}")
        self.db.close()

# =========================================
# INITIALISATION
# =========================================

def init_database():
    """Initialiser la base de données au démarrage de l'application"""
    try:
        # Vérifier la connexion
        if not check_database_connection():
            raise ConnectionError("Impossible de se connecter à la base de données")
        
        # Créer les tables si nécessaire
        create_tables()
        
        # Afficher les informations
        get_database_info()
        
        logger.info("🚀 Base de données initialisée avec succès")
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la DB: {e}")
        raise