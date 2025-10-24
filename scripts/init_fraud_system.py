"""
Script d'initialisation du système anti-fraude AlloBara
Crée les tables et initialise les paramètres par défaut
"""

import sys
import os

# Ajouter le dossier parent au path pour importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, SessionLocal, Base
from app.models.system_settings import SystemSettings
from app.models.device_fingerprint import DeviceFingerprint
from app.models.fraud_log import FraudLog
from app.models.payment import Payment

def create_tables():
    """Créer toutes les tables dans la base de données"""
    print("🔧 Création des tables...")
    
    try:
        # Créer toutes les tables définies dans Base.metadata
        Base.metadata.create_all(bind=engine)
        print("✅ Tables créées avec succès !")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création des tables: {e}")
        return False

def initialize_default_settings():
    """Initialiser les paramètres système par défaut"""
    print("\n⚙️ Initialisation des paramètres système...")
    
    db = SessionLocal()
    
    try:
        # Liste des paramètres par défaut
        default_settings = [
            {
                "key": "free_trial_enabled",
                "value": "true",
                "type": "boolean",
                "description": "Activer/désactiver la période d'essai gratuite",
                "category": "trial"
            },
            {
                "key": "free_trial_days",
                "value": "30",
                "type": "integer",
                "description": "Durée de la période d'essai en jours",
                "category": "trial"
            },
            {
                "key": "max_accounts_per_device",
                "value": "3",
                "type": "integer",
                "description": "Nombre maximum de comptes par appareil",
                "category": "fraud"
            },
            {
                "key": "fraud_detection_enabled",
                "value": "true",
                "type": "boolean",
                "description": "Activer la détection de fraude",
                "category": "fraud"
            },
            {
                "key": "min_time_between_trials_hours",
                "value": "168",  # 7 jours
                "type": "integer",
                "description": "Temps minimum entre deux essais gratuits (heures)",
                "category": "fraud"
            }
        ]
        
        # Créer chaque paramètre s'il n'existe pas déjà
        for setting_data in default_settings:
            existing = db.query(SystemSettings).filter(
                SystemSettings.setting_key == setting_data["key"]
            ).first()
            
            if not existing:
                from app.models.system_settings import SettingType
                
                setting = SystemSettings(
                    setting_key=setting_data["key"],
                    setting_value=setting_data["value"],
                    setting_type=SettingType(setting_data["type"]),
                    description=setting_data["description"],
                    category=setting_data["category"]
                )
                db.add(setting)
                print(f"  ✅ Paramètre créé : {setting_data['key']} = {setting_data['value']}")
            else:
                print(f"  ⏭️  Paramètre existe déjà : {setting_data['key']}")
        
        db.commit()
        print("\n✅ Paramètres système initialisés !")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erreur lors de l'initialisation des paramètres: {e}")
        return False
    finally:
        db.close()

def verify_tables():
    """Vérifier que les tables ont bien été créées"""
    print("\n🔍 Vérification des tables...")
    
    db = SessionLocal()
    
    try:
        # Vérifier chaque table
        tables_to_check = [
            ("system_settings", SystemSettings),
            ("device_fingerprints", DeviceFingerprint),
            ("fraud_logs", FraudLog),
            ("payments", Payment)
        ]
        
        all_ok = True
        for table_name, model in tables_to_check:
            try:
                count = db.query(model).count()
                print(f"  ✅ Table '{table_name}' existe ({count} enregistrements)")
            except Exception as e:
                print(f"  ❌ Table '{table_name}' introuvable : {e}")
                all_ok = False
        
        if all_ok:
            print("\n🎉 Toutes les tables sont présentes !")
        else:
            print("\n⚠️ Certaines tables sont manquantes")
        
        return all_ok
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la vérification: {e}")
        return False
    finally:
        db.close()

def main():
    """Fonction principale"""
    print("=" * 60)
    print("🚀 INITIALISATION DU SYSTÈME ANTI-FRAUDE ALLOBARA")
    print("=" * 60)
    
    # Étape 1 : Créer les tables
    if not create_tables():
        print("\n❌ Échec de la création des tables. Arrêt.")
        return
    
    # Étape 2 : Initialiser les paramètres
    if not initialize_default_settings():
        print("\n⚠️ Avertissement : Échec de l'initialisation des paramètres")
    
    # Étape 3 : Vérifier
    verify_tables()
    
    print("\n" + "=" * 60)
    print("✅ INITIALISATION TERMINÉE AVEC SUCCÈS !")
    print("=" * 60)
    print("\n📋 Prochaines étapes :")
    print("  1. Vérifier les tables dans pgAdmin")
    print("  2. Tester l'API admin pour modifier les paramètres")
    print("  3. Tester la détection de fraude lors de l'inscription")

if __name__ == "__main__":
    main()