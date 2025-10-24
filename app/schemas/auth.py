"""
Schémas Pydantic pour l'authentification
"""

from typing import Optional
from pydantic import BaseModel, validator, Field
import re

class PhoneRequest(BaseModel):
    """
    Schéma pour la demande d'envoi d'OTP
    """
    phone_number: str = Field(..., description="Numéro de téléphone")
    
    @validator('phone_number')
    def validate_phone(cls, v):
        # Nettoyer le numéro
        cleaned = re.sub(r'[^\d+]', '', v)
        
        # Vérifier le format pour la Côte d'Ivoire
        if not cleaned.startswith('+225'):
            if cleaned.startswith('225'):
                cleaned = '+' + cleaned
            elif cleaned.startswith('0'):
                cleaned = '+225' + cleaned[1:]
            else:
                cleaned = '+225' + cleaned
        
        # Vérifier la longueur (format ivoirien : +225 + 10 chiffres)
        if len(cleaned) != 14:
            raise ValueError('Numéro de téléphone ivoirien invalide')
        
        return cleaned

class OTPVerification(BaseModel):
    """
    Schéma pour la vérification de l'OTP
    """
    phone_number: str = Field(..., description="Numéro de téléphone")
    otp_code: str = Field(..., min_length=6, max_length=6, description="Code OTP à 6 chiffres")
    
    @validator('otp_code')
    def validate_otp(cls, v):
        if not v.isdigit():
            raise ValueError('Le code OTP doit contenir uniquement des chiffres')
        return v

class PINSetup(BaseModel):
    """
    Schéma pour la création du code PIN
    """
    phone_number: str = Field(..., description="Numéro de téléphone")
    pin_hash: str = Field(..., min_length=4, max_length=4, description="Code PIN à 4 chiffres")
    confirm_pin: str = Field(..., min_length=4, max_length=4, description="Confirmation du PIN")
    
    @validator('pin_hash')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('Le code PIN doit contenir uniquement des chiffres')
        
        # Vérifier que ce ne sont pas tous les mêmes chiffres
        if len(set(v)) == 1:
            raise ValueError('Le code PIN ne peut pas contenir que des chiffres identiques')
        
        # Vérifier que ce n'est pas une séquence simple
        forbidden = ["1234", "2345", "3456", "4567", "5678", "6789", 
                    "4321", "5432", "6543", "7654", "8765", "9876"]
        if v in forbidden:
            raise ValueError('Ce code PIN est trop simple')
        
        return v
    
    @validator('confirm_pin')
    def validate_confirm_pin(cls, v, values):
        if 'pin_hash' in values and v != values['pin_hash']:
            raise ValueError('La confirmation du PIN ne correspond pas')
        return v

class LoginRequest(BaseModel):
    """
    Schéma pour la connexion avec le clavier sécurisé
    """
    phone_number: str = Field(..., description="Numéro de téléphone")
    pin_hash: str = Field(..., min_length=4, max_length=4, description="Code PIN")
    
    @validator('pin_hash')
    def validate_pin(cls, v):
        if not v.isdigit():
            raise ValueError('Le code PIN doit contenir uniquement des chiffres')
        return v

class ForgotPINRequest(BaseModel):
    """
    Schéma pour mot de passe oublié
    """
    phone_number: str = Field(..., description="Numéro de téléphone")

class ResetPINRequest(BaseModel):
    """
    Schéma pour réinitialiser le PIN
    """
    phone_number: str = Field(..., description="Numéro de téléphone")
    otp_code: str = Field(..., min_length=6, max_length=6, description="Code OTP")
    new_pin: str = Field(..., min_length=4, max_length=4, description="Nouveau PIN")
    confirm_pin: str = Field(..., min_length=4, max_length=4, description="Confirmation PIN")
    
    @validator('new_pin')
    def validate_new_pin(cls, v):
        if not v.isdigit():
            raise ValueError('Le code PIN doit contenir uniquement des chiffres')
        
        # Même validation que PINSetup
        if len(set(v)) == 1:
            raise ValueError('Le code PIN ne peut pas contenir que des chiffres identiques')
        
        forbidden = ["1234", "2345", "3456", "4567", "5678", "6789", 
                    "4321", "5432", "6543", "7654", "8765", "9876"]
        if v in forbidden:
            raise ValueError('Ce code PIN est trop simple')
        
        return v
    
    @validator('confirm_pin')
    def validate_confirm_pin(cls, v, values):
        if 'new_pin' in values and v != values['new_pin']:
            raise ValueError('La confirmation du PIN ne correspond pas')
        return v

class Token(BaseModel):
    """
    Schéma de réponse token
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    phone_number: str
    is_profile_complete: bool = False

class TokenData(BaseModel):
    """
    Données extraites du token
    """
    user_id: Optional[int] = None
    phone_number: Optional[str] = None

class OTPResponse(BaseModel):
    """
    Réponse après envoi d'OTP
    """
    success: bool
    message: str
    expires_in: int = 300  # 5 minutes

class AuthResponse(BaseModel):
    """
    Réponse d'authentification générique
    """
    success: bool
    message: str
    data: Optional[dict] = None

class AdminLoginRequest(BaseModel):
    """
    Schéma pour connexion admin
    """
    username: str = Field(..., description="Nom d'utilisateur admin")
    password: str = Field(..., description="Mot de passe admin")

class AdminToken(BaseModel):
    """
    Token spécial pour admin
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str = "admin"
    permissions: list = []