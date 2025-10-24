-- Migration: Ajouter la table daily_stats
CREATE TABLE IF NOT EXISTS daily_stats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    profile_views INTEGER DEFAULT 0,
    contacts_received INTEGER DEFAULT 0,
    contacts_responded INTEGER DEFAULT 0,
    profile_shares INTEGER DEFAULT 0,
    favorites_added INTEGER DEFAULT 0,
    CONSTRAINT unique_user_date UNIQUE (user_id, date)
);

CREATE INDEX idx_user_date ON daily_stats(user_id, date);

COMMENT ON TABLE daily_stats IS 'Statistiques quotidiennes par 
utilisateur';

