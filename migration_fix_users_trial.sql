-- Migration AlloBara : Corriger les utilisateurs existants (syntaxe PostgreSQL)

-- Mettre à jour les utilisateurs existants avec une période d'essai de 30 jours
UPDATE users 
SET 
    subscription_status = 'trial',
    trial_expires_at = NOW() + INTERVAL '30 days'
WHERE trial_expires_at IS NULL;