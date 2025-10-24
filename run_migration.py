# backend/run_migration.py
import os
from app.db.database import engine

# Lire le fichier SQL
with open('backend/migrations/migration_add_favorites.sql', 'r') as f:
    sql_commands = f.read()

# Exécuter la migration
with engine.connect() as connection:
    for command in sql_commands.split(';'):
        command = command.strip()
        if command:
            connection.execute(command)
    print("✅ Migration exécutée avec succès !")