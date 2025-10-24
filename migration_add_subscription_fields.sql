-- Migration AlloBara : Ajout des champs d'abonnement et période d'essai
-- À exécuter dans votre base de données

-- 1. Ajouter les nouveaux champs à la table users
ALTER TABLE users ADD COLUMN subscription_status VARCHAR(20) DEFAULT 'trial';
ALTER TABLE users ADD COLUMN trial_expires_at TIMESTAMP NULL;
ALTER TABLE users ADD COLUMN subscription_expires_at TIMESTAMP NULL;

-- 2. Mettre à jour les utilisateurs existants avec une période d'essai de 30 jours
UPDATE users 
SET 
    subscription_status = 'trial',
    trial_expires_at = datetime('now', '+30 days')
WHERE trial_expires_at IS NULL;