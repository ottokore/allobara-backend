"""
Fonctions de sécurité pour AlloBara
Gestion JWT, hachage PIN, génération OTP
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Any, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Configuration pour le hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None
) -> str:
    """
    Créer un token JWT d'accès
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def verify_token(token: str) -> Union[str, None]:
    """
    Vérifier et décoder un token JWT
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None

def hash_pin(pin: str) -> str:
    """
    Hacher un code PIN à 4 chiffres
    """
    return pwd_context.hash(pin)

def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """
    Vérifier un code PIN
    """
    return pwd_context.verify(plain_pin, hashed_pin)

def generate_otp() -> str:
    """
    Générer un code OTP à 6 chiffres
    """
    return f"{secrets.randbelow(1000000):06d}"

def generate_referral_code(user_id: int) -> str:
    """
    Générer un code de parrainage unique
    Format: ALL + 5 chiffres basés sur l'ID utilisateur
    """
    # Créer un hash basé sur l'ID utilisateur et un salt
    salt = settings.SECRET_KEY[:10]
    hash_input = f"{user_id}{salt}".encode()
    hash_object = hashlib.sha256(hash_input)
    hash_hex = hash_object.hexdigest()
    
    # Extraire 5 chiffres du hash
    numbers = ''.join(filter(str.isdigit, hash_hex))[:5]
    
    # S'assurer qu'on a 5 chiffres
    if len(numbers) < 5:
        numbers = f"{user_id:05d}"[-5:]
    
    return f"ALL{numbers}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifier un mot de passe (pour usage futur si nécessaire)
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hacher un mot de passe (pour usage futur si nécessaire)
    """
    return pwd_context.hash(password)

def generate_random_pin() -> str:
    """
    Générer un PIN aléatoire à 4 chiffres (pour tests)
    """
    return f"{secrets.randbelow(10000):04d}"

def is_pin_secure(pin: str) -> bool:
    """
    Vérifier si un PIN est suffisamment sécurisé
    - Ne doit pas être 0000, 1111, 2222, etc.
    - Ne doit pas être 1234, 4321, etc.
    """
    if len(pin) != 4:
        return False
    
    # Vérifier que ce ne sont pas tous les mêmes chiffres
    if len(set(pin)) == 1:
        return False
    
    # Vérifier que ce n'est pas une séquence simple
    forbidden_sequences = [
        "1234", "2345", "3456", "4567", "5678", "6789",
        "4321", "5432", "6543", "7654", "8765", "9876",
        "0123", "1230", "2301", "3012"
    ]
    
    if pin in forbidden_sequences:
        return False
    
    return True

def create_admin_token(admin_id: str) -> str:
    """
    Créer un token JWT spécial pour les administrateurs
    """
    expire = datetime.utcnow() + timedelta(hours=8)  # Token admin expire plus vite
    to_encode = {
        "exp": expire, 
        "sub": str(admin_id),
        "role": "admin",
        "type": "admin_access"
    }
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def verify_admin_token(token: str) -> Union[dict, None]:
    """
    Vérifier un token JWT admin et retourner les infos
    """
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        token_type: str = payload.get("type")
        
        if user_id is None or role != "admin" or token_type != "admin_access":
            return None
            
        return {
            "user_id": user_id,
            "role": role,
            "type": token_type
        }
    except JWTError:
        return None

def generate_secure_filename(original_filename: str) -> str:
    """
    Générer un nom de fichier sécurisé et unique
    """
    import os
    from uuid import uuid4
    
    # Extraire l'extension
    _, ext = os.path.splitext(original_filename)
    
    # Générer un nom unique
    unique_name = str(uuid4())
    
    return f"{unique_name}{ext.lower()}"

def validate_file_type(filename: str, allowed_types: list) -> bool:
    """
    Valider le type de fichier uploadé
    """
    import os
    _, ext = os.path.splitext(filename)
    return ext.lower() in allowed_types

def sanitize_phone_number(phone: str) -> str:
    """
    Nettoyer et standardiser un numéro de téléphone
    CORRECTION MAJEURE: Ne jamais supprimer le premier 0 des numéros ivoiriens
    """
    import re
    
    if not phone:
        return ""
    
    # Supprimer tous les espaces et caractères spéciaux sauf le +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    # CORRECTION: Logs détaillés pour debug
    print(f"🔍 SANITIZE_PHONE_NUMBER DEBUG:")
    print(f"  - Original: '{phone}'")
    print(f"  - Nettoyé: '{cleaned}'")
    print(f"  - Longueur: {len(cleaned)}")
    
    # CORRECTION: Gestion spécifique pour Côte d'Ivoire
    if cleaned.startswith('+225') and len(cleaned) == 13:
        # Format déjà correct: +225xxxxxxxxxx (13 caractères)
        result = cleaned
        print(f"  - Cas 1: Format +225 complet déjà correct")
        
    elif cleaned.startswith('225') and len(cleaned) == 12:
        # Format sans +: 225xxxxxxxxxx (12 caractères)
        result = '+' + cleaned
        print(f"  - Cas 2: Ajout du + au début")
        
    elif cleaned.startswith('+2250') and len(cleaned) == 14:
        # Format avec +225 suivi de 0: +2250xxxxxxxxx (14 caractères)
        # CORRECTION: Ne PAS supprimer le 0, c'est partie intégrante du numéro
        result = cleaned
        print(f"  - Cas 3: Format +2250 (14 chars) conservé tel quel")
        
    elif cleaned.startswith('2250') and len(cleaned) == 13:
        # Format 2250xxxxxxxxx (13 caractères) - ajouter juste le +
        result = '+' + cleaned
        print(f"  - Cas 4: Format 2250, ajout du +")
        
    elif cleaned.startswith('0') and len(cleaned) == 10:
        # Format local court: 0xxxxxxxxx (10 caractères)
        # CORRECTION: Ajouter +225 DEVANT le 0, ne pas le remplacer
        result = '+225' + cleaned
        print(f"  - Cas 5: Format local 10 chiffres, +225 ajouté devant")
        
    elif len(cleaned) == 10 and not cleaned.startswith('+') and not cleaned.startswith('0'):
        # 10 chiffres sans préfixe: xxxxxxxxxx
        result = '+225' + cleaned
        print(f"  - Cas 6: 10 chiffres, ajout de +225")
        
    else:
        # Format non reconnu, garder tel quel avec warning
        result = cleaned
        print(f"  - Cas 7: Format non reconnu, conservation")
        print(f"  ⚠️ WARNING: Format inhabituel: '{cleaned}' (longueur: {len(cleaned)})")
    
    print(f"  - Résultat final: '{result}'")
    print(f"  - Longueur finale: {len(result)}")
    
    # CORRECTION: Validation finale mise à jour
    expected_length = 13  # +225 + 10 chiffres
    if result.startswith('+2250') and len(result) == 14:
        expected_length = 14  # +225 + 0 + 9 chiffres
    
    if result.startswith('+225') and len(result) == expected_length:
        print(f"  ✅ Format valide pour Côte d'Ivoire")
    else:
        print(f"  ⚠️ Format potentiellement invalide")
    
    return result