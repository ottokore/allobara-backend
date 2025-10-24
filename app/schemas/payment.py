"""
Schémas Pydantic pour les paiements AlloBara
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime


# =========================================
# SCHÉMAS DE REQUÊTE
# =========================================

class PaymentInitRequest(BaseModel):
    """Requête d'initialisation de paiement CinetPay"""
    subscription_plan: str = Field(
        ...,
        description="Plan d'abonnement: monthly, quarterly, biannual, annual"
    )
    phone_number: str = Field(
        ...,
        description="Numéro de téléphone pour le paiement (format: +225XXXXXXXXXX)"
    )
    operator: str = Field(
        ...,
        description="Opérateur mobile: orange, mtn, wave, moov"
    )
    
    @validator('subscription_plan')
    def validate_plan(cls, v):
        valid_plans = ["monthly", "quarterly", "biannual", "annual"]
        if v not in valid_plans:
            raise ValueError(f"Plan invalide. Doit être: {', '.join(valid_plans)}")
        return v
    
    @validator('operator')
    def validate_operator(cls, v):
        valid_operators = ["orange", "mtn", "wave", "moov"]
        v_lower = v.lower()
        if v_lower not in valid_operators:
            raise ValueError(f"Opérateur invalide. Doit être: {', '.join(valid_operators)}")
        return v_lower
    
    @validator('phone_number')
    def validate_phone(cls, v):
        # Nettoyer le numéro
        cleaned = ''.join(c for c in v if c.isdigit() or c == '+')
        
        # Vérifier le format de base
        if not cleaned:
            raise ValueError("Numéro de téléphone invalide")
        
        # Accepter les formats avec ou sans +225
        if cleaned.startswith('+'):
            if not cleaned.startswith('+225'):
                raise ValueError("Le numéro doit commencer par +225 (Côte d'Ivoire)")
            if len(cleaned) != 14:  # +225 + 10 chiffres
                raise ValueError("Format: +225XXXXXXXXXX (10 chiffres après +225)")
        else:
            if len(cleaned) not in [10, 13]:  # 10 chiffres ou 225 + 10 chiffres
                raise ValueError("Format invalide. Utilisez 10 chiffres ou +225XXXXXXXXXX")
        
        return cleaned
    
    class Config:
        json_schema_extra = {
            "example": {
                "subscription_plan": "monthly",
                "phone_number": "+2250709198692",
                "operator": "orange"
            }
        }


class PaymentVerificationRequest(BaseModel):
    """Requête de vérification de paiement"""
    transaction_id: str = Field(..., description="ID de transaction AlloBara")
    
    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": "ALB20250124123456ABC123"
            }
        }


# =========================================
# SCHÉMAS WEBHOOK CINETPAY
# =========================================

class CinetPayWebhookData(BaseModel):
    """Données reçues du webhook CinetPay"""
    cpm_site_id: str
    cpm_trans_id: str  # ID CinetPay
    cpm_custom: str  # Notre transaction_id
    cpm_amount: str
    cpm_currency: str
    cpm_payid: str
    cpm_trans_status: str  # ACCEPTED, REFUSED, etc.
    cpm_result: str  # 00 = success
    signature: str
    payment_method: Optional[str] = None
    cel_phone_num: Optional[str] = None
    cpm_phone_prefixe: Optional[str] = None
    cpm_error_message: Optional[str] = None
    cpm_payment_date: Optional[str] = None
    cpm_payment_time: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "cpm_site_id": "984114",
                "cpm_trans_id": "123456",
                "cpm_custom": "ALB20250124123456ABC123",
                "cpm_amount": "2500",
                "cpm_currency": "XOF",
                "cpm_payid": "PAY123456",
                "cpm_trans_status": "ACCEPTED",
                "cpm_result": "00",
                "signature": "abcdef123456",
                "payment_method": "ORANGE_MONEY",
                "cel_phone_num": "0709198692"
            }
        }


# =========================================
# SCHÉMAS DE RÉPONSE
# =========================================

class PaymentInitResponse(BaseModel):
    """Réponse d'initialisation de paiement"""
    success: bool
    message: str
    payment_url: Optional[str] = None
    transaction_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = "XOF"
    error_code: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Paiement initialisé avec succès",
                "payment_url": "https://checkout.cinetpay.com/payment/123456",
                "transaction_id": "ALB20250124123456ABC123",
                "amount": 2500,
                "currency": "XOF"
            }
        }


class PaymentVerificationResponse(BaseModel):
    """Réponse de vérification de paiement"""
    success: bool
    status: str  # pending, success, failed, expired
    message: str
    amount: Optional[int] = None
    currency: Optional[str] = None
    payment_method: Optional[str] = None
    operator_id: Optional[str] = None
    payment_date: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status": "success",
                "message": "Paiement confirmé",
                "amount": 2500,
                "currency": "XOF",
                "payment_method": "ORANGE_MONEY"
            }
        }


class PaymentStatusResponse(BaseModel):
    """Réponse de statut d'abonnement"""
    success: bool
    has_subscription: bool
    subscription: Optional[Dict[str, Any]] = None
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "has_subscription": True,
                "subscription": {
                    "id": 1,
                    "plan": "monthly",
                    "start_date": "2025-01-24T10:00:00",
                    "end_date": "2025-02-24T10:00:00",
                    "days_remaining": 30,
                    "status": "active",
                    "amount": 2500
                },
                "message": "Abonnement actif"
            }
        }


class PaymentHistoryResponse(BaseModel):
    """Élément de l'historique des paiements"""
    id: int
    transaction_id: str
    amount: int
    currency: str
    status: str
    operator: Optional[str] = None
    description: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    formatted_amount: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "transaction_id": "ALB20250124123456ABC123",
                "amount": 2100,
                "currency": "XOF",
                "status": "success",
                "operator": "orange",
                "description": "Abonnement mensuel",
                "created_at": "2025-01-24T10:00:00",
                "completed_at": "2025-01-24T10:05:00",
                "formatted_amount": "2 100 XOF"
            }
        }


# =========================================
# SCHÉMAS PLANS D'ABONNEMENT
# =========================================

class SubscriptionPlan(BaseModel):
    """Plan d'abonnement"""
    id: str
    name: str
    duration_days: int
    amount: int
    currency: str = "FCFA"
    description: str
    features: list[str]
    savings: Optional[int] = None
    popular: Optional[bool] = False
    best_value: Optional[bool] = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "monthly",
                "name": "Mensuel",
                "duration_days": 30,
                "amount": 2500,
                "currency": "FCFA",
                "description": "Abonnement mensuel - Parfait pour commencer",
                "features": [
                    "Profil visible dans les recherches",
                    "Portfolio illimité",
                    "Réception d'appels clients"
                ]
            }
        }


class SubscriptionPlansResponse(BaseModel):
    """Liste des plans d'abonnement"""
    success: bool
    plans: list[SubscriptionPlan]


# =========================================
# SCHÉMAS OPÉRATEURS
# =========================================

class PaymentOperator(BaseModel):
    """Opérateur de paiement mobile"""
    id: str
    name: str
    channel: str  # MOBILE_MONEY ou WALLET
    color: str
    icon: str
    enabled: bool = True
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "orange",
                "name": "Orange Money",
                "channel": "MOBILE_MONEY",
                "color": "#FF6600",
                "icon": "🟠",
                "enabled": True
            }
        }


class PaymentOperatorsResponse(BaseModel):
    """Liste des opérateurs disponibles"""
    success: bool
    operators: list[PaymentOperator]
