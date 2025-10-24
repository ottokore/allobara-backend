-- Migration SQL pour la table favorites
-- Création de la table de gestion des favoris utilisateurs

-- ========================================
-- TABLE: favorites
-- ========================================

CREATE TABLE IF NOT EXISTS favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    provider_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Index pour améliorer les performances
    INDEX idx_user_id (user_id),
    INDEX idx_provider_id (provider_id),
    INDEX idx_created_at (created_at),
    
    -- Contrainte d'unicité : un utilisateur ne peut ajouter un prestataire qu'une seule fois
    UNIQUE KEY uix_user_provider (user_id, provider_id),
    
    -- Clés étrangères
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ========================================
-- COMMENTAIRES
-- ========================================

ALTER TABLE favorites COMMENT = 'Table des favoris - Relation entre utilisateurs et prestataires favoris';

-- ========================================
-- VÉRIFICATION
-- ========================================

-- Afficher la structure de la table
DESCRIBE favorites;

-- Compter les favoris existants (devrait être 0 après création)
SELECT COUNT(*) AS total_favorites FROM favorites;

-- ========================================
-- EXEMPLES DE REQUÊTES UTILES
-- ========================================

-- Récupérer tous les favoris d'un utilisateur
-- SELECT * FROM favorites WHERE user_id = 1;

-- Vérifier si un prestataire est en favori
-- SELECT EXISTS(SELECT 1 FROM favorites WHERE user_id = 1 AND provider_id = 36) AS is_favorite;

-- Compter les favoris d'un utilisateur
-- SELECT COUNT(*) FROM favorites WHERE user_id = 1;

-- Compter combien d'utilisateurs ont mis un prestataire en favori
-- SELECT COUNT(*) FROM favorites WHERE provider_id = 36;

-- Top 10 des prestataires les plus mis en favoris
-- SELECT provider_id, COUNT(*) as favorite_count 
-- FROM favorites 
-- GROUP BY provider_id 
-- ORDER BY favorite_count DESC 
-- LIMIT 10;