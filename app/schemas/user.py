"""
Schémas Pydantic pour les utilisateurs
Validation des profils prestataires
"""

from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, validator, Field
from enum import Enum

# =========================================
# ENUMS POUR VALIDATION
# =========================================

class GenderEnum(str, Enum):
    MALE = "M"
    FEMALE = "F"
    OTHER = "other"

class DocumentTypeEnum(str, Enum):
    CNI = "cni"
    PASSPORT = "passport"
    DRIVING_LICENSE = "permis"

class DomainEnum(str, Enum):
    BATIMENT = "batiment"
    MENAGE = "menage"
    TRANSPORT = "transport"
    RESTAURATION = "restauration"
    BEAUTE = "beaute"
    AUTRES = "autres"

# =========================================
# SCHÉMAS DE BASE
# =========================================

class UserBase(BaseModel):
    """
    Schéma de base pour les utilisateurs
    """
    phone: str = Field(..., description="Numéro de téléphone")
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    birth_date: Optional[date] = None
    gender: Optional[GenderEnum] = None

class PersonalInfoUpdate(BaseModel):
    """
    Mise à jour des informations personnelles
    """
    first_name: str = Field(..., min_length=2, max_length=100, description="Prénom")
    last_name: str = Field(..., min_length=2, max_length=100, description="Nom de famille")
    birth_date: Optional[date] = Field(None, description="Date de naissance")
    gender: Optional[GenderEnum] = None
    
    @validator('birth_date')
    def validate_birth_date(cls, v):
        if v:
            # Vérifier que l'âge est entre 16 and 80 ans
            today = date.today()
            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            
            if age < 16:
                raise ValueError('Vous devez avoir au moins 16 ans')
            if age > 80:
                raise ValueError('Date de naissance invalide')
        
        return v

class ProfessionalInfoUpdate(BaseModel):
    """
    Mise à jour des informations professionnelles
    """
    profession: str = Field(..., min_length=3, max_length=100, description="Métier")
    domain: DomainEnum = Field(..., description="Domaine d'activité")
    years_experience: int = Field(..., ge=0, le=50, description="Années d'expérience")
    description: str = Field(..., min_length=20, max_length=1000, description="Description du prestataire")
    daily_rate: Optional[float] = Field(None, ge=1000, le=100000, description="Tarif journalier")
    monthly_rate: Optional[float] = Field(None, ge=5000, le=500000, description="Tarif mensuel")
    
    @validator('daily_rate', 'monthly_rate')
    def validate_rates(cls, v, values):
        # Au moins un tarif doit être défini
        if not v and not values.get('daily_rate') and not values.get('monthly_rate'):
            raise ValueError('Veuillez définir au moins un tarif')
        return v

class LocationUpdate(BaseModel):
    """
    Mise à jour de la localisation
    """
    country: str = Field(default="Côte d'Ivoire", max_length=50)
    city: str = Field(..., min_length=2, max_length=100, description="Ville")
    commune: str = Field(..., min_length=2, max_length=100, description="Commune")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    work_radius_km: int = Field(default=5, ge=1, le=50, description="Rayon de travail en km")
    address: Optional[str] = Field(None, max_length=500, description="Adresse complète")

class DocumentUpload(BaseModel):
    """
    Upload des documents d'identité
    """
    document_type: DocumentTypeEnum = Field(..., description="Type de document")
    document_number: Optional[str] = Field(None, max_length=50, description="Numéro du document")

# =========================================
# SCHÉMAS DE RÉPONSE
# =========================================

class UserResponse(BaseModel):
    """
    Réponse utilisateur complète
    """
    id: int
    phone: str
    full_name: str
    profession: Optional[str]
    domain: Optional[str]
    city: Optional[str]
    commune: Optional[str]
    rating_average: float
    rating_count: int
    profile_picture: Optional[str]
    cover_picture: Optional[str]
    is_verified: bool
    years_experience: Optional[int]
    description: Optional[str]
    daily_rate: Optional[float]
    monthly_rate: Optional[float]
    work_radius_km: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserCardResponse(BaseModel):
    """
    Réponse pour les cartes de prestataires (page d'accueil)
    """
    id: int
    full_name: str
    profession: Optional[str]
    city: Optional[str]
    commune: Optional[str]
    rating_average: float
    rating_count: int
    profile_picture: Optional[str]
    daily_rate: Optional[float]
    monthly_rate: Optional[float]
    is_verified: bool
    distance_km: Optional[float] = None  # Distance calculée
    
    class Config:
        from_attributes = True

class UserProfileResponse(BaseModel):
    """
    Réponse profil détaillé
    """
    id: int
    phone: str
    full_name: str
    first_name: Optional[str]
    last_name: Optional[str]
    profession: Optional[str]
    domain: Optional[str]
    years_experience: Optional[int]
    description: Optional[str]
    city: Optional[str]
    commune: Optional[str]
    country: str
    address: Optional[str]
    daily_rate: Optional[float]
    monthly_rate: Optional[float]
    work_radius_km: int
    profile_picture: Optional[str]
    cover_picture: Optional[str]
    
    # Portfolio
    portfolio: Optional[List[str]] = None
    
    rating_average: float
    rating_count: int
    rating_display: str
    is_verified: bool
    profile_views: int
    total_contacts: int
    coordinates: Optional[tuple]
    created_at: datetime
    
    # Statistiques du profil
    is_profile_complete: bool
    profile_completion: int
    has_active_subscription: bool
    
    class Config:
        from_attributes = True

class SearchFilters(BaseModel):
    """
    Filtres de recherche pour les prestataires
    """
    query: Optional[str] = Field(None, max_length=200, description="Recherche textuelle")
    domain: Optional[DomainEnum] = None
    country: Optional[str] = Field(None, max_length=100, description="Pays")  # ✅ AJOUTÉ
    city: Optional[str] = Field(None, max_length=100, description="Ville")
    commune: Optional[str] = Field(None, max_length=100, description="Commune")
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    max_distance_km: Optional[int] = Field(None, ge=1, le=50)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    verified_only: bool = Field(False, description="Prestataires vérifiés uniquement")
    available_today: bool = Field(False, description="Disponibles aujourd'hui")
    
    # Géolocalisation pour calcul de distance
    user_latitude: Optional[float] = Field(None, ge=-90, le=90)
    user_longitude: Optional[float] = Field(None, ge=-180, le=180)

class UserSearchResponse(BaseModel):
    """
    Réponse de recherche paginée
    """
    users: List[UserCardResponse]
    total: int
    page: int
    limit: int
    has_next: bool
    filters_applied: dict

class UserStatsResponse(BaseModel):
    """
    Statistiques d'un utilisateur
    """
    profile_views: int
    total_contacts: int
    rating_average: float
    rating_count: int
    portfolio_items_count: int
    days_since_creation: int
    subscription_status: str
    subscription_days_remaining: Optional[int]

# =========================================
# SCHÉMAS DE MISE À JOUR
# =========================================

class ProfilePictureUpdate(BaseModel):
    """
    Mise à jour de la photo de profil
    """
    profile_picture: str = Field(..., description="URL de la nouvelle photo")

class CoverPictureUpdate(BaseModel):
    """
    Mise à jour de la photo de couverture
    """
    cover_picture: str = Field(..., description="URL de la nouvelle photo de couverture")

class RatesUpdate(BaseModel):
    """
    Mise à jour des tarifs
    """
    daily_rate: Optional[float] = Field(None, ge=1000, le=100000)
    monthly_rate: Optional[float] = Field(None, ge=5000, le=500000)
    
    @validator('monthly_rate')
    def validate_at_least_one_rate(cls, v, values):
        if not v and not values.get('daily_rate'):
            raise ValueError('Au moins un tarif doit être défini')
        return v

class WorkRadiusUpdate(BaseModel):
    """
    Mise à jour du rayon de travail
    """
    work_radius_km: int = Field(..., ge=1, le=50, description="Rayon de travail en kilomètres")

# =========================================
# SCHÉMAS ADMIN
# =========================================

class UserAdminResponse(BaseModel):
    """
    Réponse utilisateur pour l'admin (plus de détails)
    """
    id: int
    phone: str
    full_name: str
    profession: Optional[str]
    domain: Optional[str]
    city: Optional[str]
    is_active: bool
    is_verified: bool
    is_blocked: bool
    blocked_reason: Optional[str]
    has_active_subscription: bool
    subscription_status: Optional[str]
    total_contacts: int
    profile_views: int
    created_at: datetime
    last_login: Optional[datetime]
    last_seen: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserBlockRequest(BaseModel):
    """
    Demande de blocage d'utilisateur
    """
    reason: str = Field(..., min_length=10, max_length=500, description="Raison du blocage")

class UserVerificationUpdate(BaseModel):
    """
    Mise à jour du statut de vérification
    """
    is_verified: bool
    verification_notes: Optional[str] = Field(None, max_length=500)

# =========================================
# SCHÉMAS UTILITAIRES
# =========================================

class BulkActionRequest(BaseModel):
    """
    Actions en lot sur les utilisateurs
    """
    user_ids: List[int] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., description="Action à effectuer")
    reason: Optional[str] = Field(None, max_length=500)

class ProfileCompletionResponse(BaseModel):
    """
    État de complétion du profil
    """
    is_complete: bool
    completion_percentage: int
    missing_fields: List[str]
    next_step: Optional[str]
    
class ContactInfo(BaseModel):
    """
    Informations de contact pour affichage public
    """
    phone: str
    formatted_phone: str
    city: str
    commune: str
    work_radius_km: int
    coordinates: Optional[tuple]