"""
Endpoints d'authentification AlloBara
Routes pour inscription, connexion, OTP, PIN
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
import bcrypt

from app.db.database import get_db
from app.services.auth import AuthService
from app.schemas.auth import (
    PhoneRequest, OTPVerification, PINSetup, LoginRequest,
    ForgotPINRequest, ResetPINRequest, Token, OTPResponse,
    AuthResponse, AdminLoginRequest, AdminToken
)
from app.api.deps.auth import get_current_user, get_request_info
from app.models.user import User
from app.models.subscription import Subscription
from app.core.security import create_access_token
from app.models.subscription import SubscriptionPlan, SubscriptionStatus, PaymentStatus

# Router pour les endpoints d'authentification
router = APIRouter()

# =========================================
# SCHÉMA POUR INSCRIPTION COMPLÈTE
# =========================================

class RegisterCompleteRequest(BaseModel):
    phone_number: str
    country_code: str
    pin: str
    first_name: str
    last_name: str
    birth_date: str
    gender: str
    domain: str
    profession: str
    years_experience: int
    description: str
    rate_type: str
    country: str
    city: str
    subscription_plan_id: str
    transaction_id: str
    subscription_amount: float
    daily_rate: Optional[float] = None
    monthly_rate: Optional[float] = None
    commune: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

# =========================================
# ENDPOINTS D'AUTHENTIFICATION
# =========================================

@router.post("/send-otp", response_model=OTPResponse)
async def send_otp(
    request: PhoneRequest,
    db: Session = Depends(get_db)
):
    """
    Envoyer un code OTP par WhatsApp/SMS
    Étape 1 de l'inscription
    """
    try:
        auth_service = AuthService(db)
        result = await auth_service.send_otp(request.phone_number)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"]
            )
        
        return OTPResponse(
            success=result["success"],
            message=result["message"],
            expires_in=result.get("expires_in", 600)
        )
            
    except Exception as e:
        print(f"Erreur send_otp: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'envoi de l'OTP"
        )

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp(
    request: OTPVerification,
    db: Session = Depends(get_db)
):
    """
    Vérifier le code OTP
    Étape 2 de l'inscription
    """
    auth_service = AuthService(db)
    result = await auth_service.verify_otp(request.phone_number, request.otp_code)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return AuthResponse(**result)

@router.post("/create-account", response_model=Token)
async def create_account(
    request: PINSetup,
    db: Session = Depends(get_db)
):
    """
    Créer un compte avec code PIN
    Étape 3 de l'inscription (après vérification OTP)
    """
    auth_service = AuthService(db)
    
    if auth_service.check_user_exists(request.phone_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec ce numéro"
        )
    
    result = await auth_service.create_user_with_pin(
        request.phone_number, 
        request.pin_hash
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return Token(**result["data"])

# =========================================
# ✅ INSCRIPTION COMPLÈTE (NOUVEAU)
# =========================================

@router.post("/register-complete")
async def register_complete(
    request: RegisterCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    ✅ INSCRIPTION COMPLÈTE APRÈS PAIEMENT
    
    Crée le compte avec toutes les données collectées.
    """
    
    try:
        print(f"\n🔐 INSCRIPTION COMPLÈTE")
        print(f"📞 Téléphone: {request.country_code}{request.phone_number}")
        print(f"👤 Nom: {request.first_name} {request.last_name}")
        print(f"💼 Profession: {request.profession} ({request.domain})")
        print(f"📍 Ville: {request.city}, {request.country}")
        print(f"💳 Plan: {request.subscription_plan_id} ({request.subscription_amount} FCFA)")
        
        # 1. VÉRIFIER SI LE NUMÉRO EXISTE DÉJÀ
        full_phone = f"{request.country_code}{request.phone_number}"
        existing_user = db.query(User).filter(User.phone == full_phone).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce numéro de téléphone est déjà enregistré"
            )
        
        print("✅ Numéro disponible")
        
        # 2. HASHER LE PIN
        hashed_pin = bcrypt.hashpw(request.pin.encode('utf-8'), bcrypt.gensalt())
        print("✅ PIN hashé")
        
        # 3. CALCULER LA DATE D'EXPIRATION ABONNEMENT
        subscription_duration = {
            "monthly": timedelta(days=30),
            "quarterly": timedelta(days=90),
            "semiannual": timedelta(days=180),
            "annual": timedelta(days=365),
        }
        
        subscription_start = datetime.utcnow()
        duration = subscription_duration.get(request.subscription_plan_id, timedelta(days=90))
        subscription_end = subscription_start + duration
        
        print(f"📅 Abonnement: {subscription_start.date()} → {subscription_end.date()}")
        
        # 4. CRÉER LE COMPTE USER
        new_user = User(
            # Authentification
            phone=full_phone,
            pin_hash=hashed_pin.decode('utf-8'),
            
            # Informations personnelles
            first_name=request.first_name,
            last_name=request.last_name,
            birth_date=request.birth_date,
            gender=request.gender,
            profile_picture=None,
            
            # Informations professionnelles
            domain=request.domain,
            profession=request.profession,
            years_experience=request.years_experience,
            description=request.description,
            daily_rate=request.daily_rate,
            monthly_rate=request.monthly_rate,
            cover_picture=None,
            
            # Localisation
            country=request.country,
            city=request.city,
            commune=request.commune,
            latitude=request.latitude,
            longitude=request.longitude,
            
            # Statut
            is_active=True,
            is_verified=False,
            is_blocked=False,
            
            # Dates
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        db.add(new_user)
        db.flush()
        
        user_id = new_user.id
        print(f"✅ User créé: ID={user_id}")
        
        # 5. CRÉER L'ABONNEMENT
        subscription = Subscription(
            user_id=user_id,
            plan=SubscriptionPlan(request.subscription_plan_id),
            status=SubscriptionStatus.ACTIVE,
            price=request.subscription_amount,
            start_date=subscription_start,
            end_date=subscription_end,
            payment_reference=request.transaction_id,
            payment_status=PaymentStatus.SUCCESS,
            payment_date=datetime.utcnow(),
        )
        
        db.add(subscription)
        print(f"✅ Abonnement créé")

        # Mettre à jour les dates dans User
        new_user.subscription_status = SubscriptionStatus.ACTIVE  # Changer de TRIAL à ACTIVE
        new_user.subscription_expires_at = subscription_end        # Définir la date d'expiration
        
        # 6. COMMIT
        db.commit()
        db.refresh(new_user)
        
        print("✅ Toutes les données sauvegardées en DB")
        
        # 7. GÉNÉRER LE TOKEN JWT
        token_data = {
            "user_id": user_id,
            "phone": full_phone,
        }
        
        access_token = create_access_token(subject=user_id)
        
        print(f"✅ Token JWT généré")
        
        # 8. RÉPONSE
        return {
            "success": True,
            "message": "Compte créé avec succès",
            "data": {
                "user_id": user_id,
                "token": access_token,
                "user": {
                    "id": user_id,
                    "phone": full_phone,
                    "first_name": request.first_name,
                    "last_name": request.last_name,
                    "full_name": f"{request.first_name} {request.last_name}",
                    "profession": request.profession,
                    "domain": request.domain,
                    "city": request.city,
                    "commune": request.commune,
                    "profile_picture": None,
                    "cover_picture": None,
                    "rating_average": 0.0,
                    "rating_count": 0,
                    "is_verified": False,
                },
                "subscription": {
                    "plan_id": request.subscription_plan_id,
                    "status": "active",
                    "start_date": subscription_start.isoformat(),
                    "end_date": subscription_end.isoformat(),
                    "amount": request.subscription_amount,
                },
                "portfolio_count": 0,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ ERREUR INSCRIPTION: {e}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'inscription: {str(e)}"
        )

# =========================================
# AUTRES ENDPOINTS
# =========================================

@router.post("/login", response_model=Token)
async def login(
    request: LoginRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    Connexion avec PIN (clavier sécurisé)
    """
    auth_service = AuthService(db)
    result = await auth_service.login_with_pin(request.phone_number, request.pin_hash)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["message"]
        )
    
    return Token(**result["data"])

@router.get("/keypad-layout")
async def get_keypad_layout(db: Session = Depends(get_db)):
    """
    Générer une disposition aléatoire du clavier PIN pour la sécurité
    """
    auth_service = AuthService(db)
    layout = auth_service.generate_random_keypad_layout()
    
    return {
        "layout": layout,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/forgot-pin", response_model=OTPResponse)
async def forgot_pin(
    request: ForgotPINRequest,
    db: Session = Depends(get_db)
):
    """
    Demander la réinitialisation du PIN (mot de passe oublié)
    """
    auth_service = AuthService(db)
    result = await auth_service.reset_pin_request(request.phone_number)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return OTPResponse(**result)

@router.post("/reset-pin", response_model=AuthResponse)
async def reset_pin(
    request: ResetPINRequest,
    db: Session = Depends(get_db)
):
    """
    Confirmer la réinitialisation du PIN
    """
    auth_service = AuthService(db)
    result = await auth_service.reset_pin_confirm(
        request.phone_number,
        request.otp_code,
        request.new_pin
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return AuthResponse(**result)

@router.post("/logout", response_model=AuthResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Déconnexion utilisateur
    """
    auth_service = AuthService(db)
    result = auth_service.logout_user(current_user.id)
    
    return AuthResponse(**result)

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Récupérer les informations de l'utilisateur connecté
    """
    return {
        "id": current_user.id,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "profession": current_user.profession,
        "city": current_user.city,
        "commune": current_user.commune,
        "is_profile_complete": current_user.is_profile_complete,
        "profile_completion": current_user.profile_completion_percentage,
        "has_active_subscription": current_user.has_active_subscription,
        "is_verified": current_user.is_verified,
        "profile_picture": current_user.profile_picture,
        "rating_display": current_user.rating_display,
        "created_at": current_user.created_at
    }

@router.get("/check-phone/{phone_number}")
async def check_phone_exists(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """
    Vérifier si un numéro de téléphone est déjà enregistré
    """
    auth_service = AuthService(db)
    exists = auth_service.check_user_exists(phone_number)
    
    return {
        "exists": exists,
        "message": "Numéro déjà enregistré" if exists else "Numéro disponible"
    }

@router.get("/debug/active-otps")
async def debug_active_otps(db: Session = Depends(get_db)):
    """
    ENDPOINT DE DEBUG - Lister tous les OTP actifs
    ⚠️ À SUPPRIMER EN PRODUCTION
    """
    auth_service = AuthService(db)
    otps = auth_service.debug_list_active_otps()
    
    return {
        "message": "Liste des OTP actifs",
        "data": otps
    }

@router.post("/admin/login", response_model=AdminToken)
async def admin_login(
    request: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Connexion administrateur
    """
    auth_service = AuthService(db)
    result = await auth_service.admin_login(request.username, request.password)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result["message"]
        )
    
    return AdminToken(**result["data"])

@router.get("/countries")
async def get_supported_countries():
    """
    Liste des pays supportés avec leurs codes téléphoniques
    """
    return {
        "countries": [
            {
                "name": "Côte d'Ivoire",
                "code": "CI",
                "phone_code": "+225",
                "flag": "🇨🇮",
                "is_primary": True
            },
            {
                "name": "Burkina Faso", 
                "code": "BF",
                "phone_code": "+226",
                "flag": "🇧🇫",
                "is_primary": False
            },
            {
                "name": "Mali",
                "code": "ML", 
                "phone_code": "+223",
                "flag": "🇲🇱",
                "is_primary": False
            }
        ]
    }

@router.get("/service-categories")
async def get_service_categories():
    """
    Catégories de services disponibles
    """
    return {
        "categories": [
            {
                "id": "batiment",
                "name": "Bâtiment et BTP",
                "icon": "🔧",
                "services": [
                    "Maçon", "Plombier", "Électricien", "Peintre", 
                    "Staffeur", "Ferrailleur", "Menuisier"
                ]
            },
            {
                "id": "menage",
                "name": "Ménage et Domestique", 
                "icon": "🧹",
                "services": [
                    "Femme de ménage", "Nounou", "Bonne", 
                    "Nettoyage de bureaux", "Jardinier"
                ]
            },
            {
                "id": "transport",
                "name": "Transport",
                "icon": "🚗", 
                "services": [
                    "Chauffeur privé", "Chauffeur taxi", "Livreur",
                    "Mécanicien"
                ]
            },
            {
                "id": "restauration",
                "name": "Restauration",
                "icon": "🍽️",
                "services": [
                    "Cuisinier", "Traiteur", "Serveur", "Barman",
                    "Gérant de bar"
                ]
            },
            {
                "id": "beaute",
                "name": "Beauté et Bien-être",
                "icon": "💇🏾",
                "services": [
                    "Coiffeur", "Barbier", "Esthéticienne", "Masseur"
                ]
            },
            {
                "id": "autres",
                "name": "Autres Services",
                "icon": "🛠️",
                "services": [
                    "Réparateur électroménager", "Soudeur", "Agent de sécurité",
                    "Photographe", "Technicien informatique"
                ]
            }
        ]
    }