"""
Endpoints utilisateurs AlloBara
Routes pour profils, recherche, mise à jour
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from app.models.portfolio import PortfolioItem
from app.services.stats_service import StatsService

from app.db.database import get_db
from app.services.user import UserService
from app.schemas.user import (
    PersonalInfoUpdate, ProfessionalInfoUpdate, LocationUpdate,
    SearchFilters, UserSearchResponse, UserProfileResponse,
    UserStatsResponse, ProfileCompletionResponse, ContactInfo
)
from app.api.deps.auth import (
    get_current_user, get_optional_user, require_complete_profile,
    get_current_admin_user
)
from app.models.user import User

# Router pour les endpoints utilisateurs
router = APIRouter()

# =========================================
# ROUTES PUBLIQUES (sans authentification)
# =========================================

@router.get("/", response_model=UserSearchResponse)
async def get_providers_list(
    page: int = Query(1, ge=1, description="Numéro de page"),
    limit: int = Query(20, ge=1, le=50, description="Nombre d'éléments par page"),
    query: Optional[str] = Query(None, description="Recherche textuelle"),
    domain: Optional[str] = Query(None, description="Domaine d'activité"),
    city: Optional[str] = Query(None, description="Ville"),
    commune: Optional[str] = Query(None, description="Commune"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Note minimum"),
    verified_only: bool = Query(False, description="Prestataires vérifiés uniquement"),
    user_lat: Optional[float] = Query(None, ge=-90, le=90, description="Latitude utilisateur"),
    user_lng: Optional[float] = Query(None, ge=-180, le=180, description="Longitude utilisateur"),
    max_distance: Optional[int] = Query(None, ge=1, le=50, description="Distance max en km"),
    db: Session = Depends(get_db)
):
    """
    Liste des prestataires avec filtres et scroll infini (style Facebook)
    """
    user_service = UserService(db)
    
    # Construire les filtres
    filters = SearchFilters(
        query=query,
        domain=domain,
        city=city,
        commune=commune,
        min_rating=min_rating,
        verified_only=verified_only,
        user_latitude=user_lat,
        user_longitude=user_lng,
        max_distance_km=max_distance
    )
    
    result = user_service.search_providers(filters, page, limit)
    return UserSearchResponse(**result)

@router.get("/home-feed")
async def get_home_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    user_lat: Optional[float] = Query(None, ge=-90, le=90),
    user_lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db)
):
    """
    Feed principal pour l'accueil avec scroll infini
    Featured en premier, puis tri par pertinence
    """
    user_service = UserService(db)
    user_location = (user_lat, user_lng) if user_lat and user_lng else None
    
    result = user_service.get_providers_for_home_feed(page, limit, user_location)
    return result

@router.get("/nearby")
async def get_nearby_providers(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius: int = Query(5, ge=1, le=50, description="Rayon en km"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Prestataires dans un rayon de 3-5km
    """
    user_service = UserService(db)
    providers = user_service.get_nearby_providers(lat, lng, radius, limit)
    
    return {
        "providers": providers,
        "total": len(providers),
        "radius_km": radius,
        "center": {"latitude": lat, "longitude": lng}
    }

@router.get("/featured")
async def get_featured_providers(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Prestataires mis en avant (sponsorisés)
    """
    user_service = UserService(db)
    featured = user_service.get_featured_providers(limit)
    
    return {
        "featured_providers": featured,
        "count": len(featured)
    }

@router.get("/{provider_id}", response_model=UserProfileResponse)
async def get_provider_profile(
    provider_id: int,
    user_lat: Optional[float] = Query(None, ge=-90, le=90),
    user_lng: Optional[float] = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db)
):
    """
    Profil détaillé d'un prestataire
    ✅ Incrémente automatiquement les vues
    """
    user_service = UserService(db)
    viewer_location = (user_lat, user_lng) if user_lat and user_lng else None
    
    profile = user_service.get_provider_by_id(provider_id, viewer_location)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestataire introuvable"
        )
    
    # ✅ NOUVEAU : Incrémenter les vues du profil
    try:
        stats_service = StatsService(db)
        stats_service.increment_profile_views(provider_id)
        print(f"✅ Vue incrémentée pour user {provider_id}")
    except Exception as e:
        print(f"⚠️ Erreur stats: {e}")
    
    return profile

@router.post("/{provider_id}/contact")
async def contact_provider(
    provider_id: int,
    db: Session = Depends(get_db)
):
    """
    Marquer qu'un contact a été établi avec un prestataire
    ✅ Incrémente automatiquement les contacts
    """
    user_service = UserService(db)
    success = user_service.increment_contact_count(provider_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prestataire introuvable"
        )
    
    # ✅ NOUVEAU : Incrémenter les contacts reçus dans daily_stats
    try:
        stats_service = StatsService(db)
        stats_service.increment_contacts_received(provider_id)
        print(f"✅ Contact incrémenté pour user {provider_id}")
    except Exception as e:
        print(f"⚠️ Erreur stats: {e}")
    
    return {"message": "Contact enregistré"}

@router.get("/me/stats/detailed")
async def get_my_detailed_stats(
    period: str = Query('week', description="today, week, month, 3months, year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Statistiques détaillées avec données pour graphiques
    """
    stats_service = StatsService(db)
    detailed_stats = stats_service.get_aggregated_stats(current_user.id, period)
    
    return detailed_stats

@router.get("/cities/list")
async def get_cities_list(
    db: Session = Depends(get_db)
):
    """
    Liste des villes avec nombre de prestataires
    """
    user_service = UserService(db)
    cities = user_service.get_cities_with_providers()
    
    return {
        "cities": cities,
        "total_cities": len(cities)
    }

# =========================================
# ROUTES AUTHENTIFIÉES
# =========================================

@router.get("/me/profile", response_model=UserProfileResponse)
async def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    RÃ©cupÃ©rer mon profil complet avec portfolio
    """
    try:
        # Charger le portfolio depuis portfolio_items
        portfolio_query = db.query(PortfolioItem).filter(
            PortfolioItem.user_id == current_user.id,
            PortfolioItem.status == 'active'
        ).order_by(PortfolioItem.order_index, PortfolioItem.created_at.desc()).all()
        
        # âœ… CORRECTION : Formatter le portfolio en List<String> comme les autres endpoints
        portfolio_urls = [item.file_path for item in portfolio_query]
        
        print(f"ðŸ“¸ Portfolio chargÃ©: {len(portfolio_urls)} items")
        print(f"ðŸ“¸ URLs: {portfolio_urls}")
        
        profile_data = {
            "id": current_user.id,
            "phone": current_user.phone,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "full_name": current_user.full_name,
            "profession": current_user.profession or "",
            "domain": current_user.domain,
            "years_experience": current_user.years_experience,
            "description": current_user.description,
            "city": current_user.city or "",
            "commune": current_user.commune or "",
            "country": current_user.country or "CÃ´te d'Ivoire",
            "address": current_user.address,
            "daily_rate": current_user.daily_rate,
            "monthly_rate": current_user.monthly_rate,
            "work_radius_km": current_user.work_radius_km or 5,
            "profile_picture": current_user.profile_picture,
            "cover_picture": current_user.cover_picture,
            "rating_average": current_user.rating_average or 0.0,
            "rating_count": current_user.rating_count or 0,
            "rating_display": current_user.rating_display,
            "is_verified": current_user.is_verified or False,
            "profile_views": current_user.profile_views or 0,
            "total_contacts": current_user.total_contacts or 0,
            "coordinates": current_user.coordinates,
            "created_at": current_user.created_at,
            "is_profile_complete": current_user.is_profile_complete,
            "profile_completion": current_user.profile_completion_percentage,
            "has_active_subscription": current_user.has_active_subscription,
            "portfolio": portfolio_urls  # âœ… List<String> au lieu de List<Map>
        }

        print(f"📊 STATS RETOURNÉES: profile_views={profile_data['profile_views']}, total_contacts={profile_data['total_contacts']}")
        
        return profile_data
        
    except Exception as e:
        print(f"âŒ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupérer mes statistiques
    """
    user_service = UserService(db)
    stats = user_service.get_user_stats(current_user.id)
    
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statistiques introuvables"
        )
    
    return UserStatsResponse(**stats)

@router.get("/me/completion", response_model=ProfileCompletionResponse)
async def get_profile_completion(
    current_user: User = Depends(get_current_user)
):
    """
    État de complétion du profil
    """
    missing_fields = []
    
    # Vérifier les champs requis
    if not current_user.first_name:
        missing_fields.append("Prénom")
    if not current_user.last_name:
        missing_fields.append("Nom de famille")
    if not current_user.profession:
        missing_fields.append("Profession")
    if not current_user.domain:
        missing_fields.append("Domaine d'activité")
    if not current_user.city:
        missing_fields.append("Ville")
    if not current_user.commune:
        missing_fields.append("Commune")
    if not current_user.description:
        missing_fields.append("Description")
    if not current_user.profile_picture:
        missing_fields.append("Photo de profil")
    if not (current_user.daily_rate or current_user.monthly_rate):
        missing_fields.append("Tarification")
    if not (current_user.latitude and current_user.longitude):
        missing_fields.append("Géolocalisation")
    
    is_complete = len(missing_fields) == 0
    completion_percentage = current_user.profile_completion_percentage
    
    # Déterminer la prochaine étape
    next_step = None
    if missing_fields:
        if "Prénom" in missing_fields or "Nom de famille" in missing_fields:
            next_step = "Complétez vos informations personnelles"
        elif "Profession" in missing_fields or "Domaine d'activité" in missing_fields:
            next_step = "Renseignez vos informations professionnelles"
        elif "Ville" in missing_fields or "Commune" in missing_fields:
            next_step = "Définissez votre localisation"
        else:
            next_step = "Finalisez votre profil"
    
    return ProfileCompletionResponse(
        is_complete=is_complete,
        completion_percentage=completion_percentage,
        missing_fields=missing_fields,
        next_step=next_step
    )

@router.put("/me/personal-info")
async def update_personal_info(
    update_data: PersonalInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour les informations personnelles
    """
    user_service = UserService(db)
    result = user_service.update_personal_info(current_user.id, update_data)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.put("/me/professional-info")
async def update_professional_info(
    update_data: ProfessionalInfoUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour les informations professionnelles
    """
    user_service = UserService(db)
    result = user_service.update_professional_info(current_user.id, update_data)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.put("/me/location")
async def update_location(
    update_data: LocationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour la localisation
    """
    user_service = UserService(db)
    result = user_service.update_location(current_user.id, update_data)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.post("/me/profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload de la photo de profil avec sauvegarde physique
    """
    from app.services.file_upload import FileUploadService
    import traceback
    
    try:
        print(f"📥 Upload profile picture - User: {current_user.id}, File: {file.filename}")
        print(f"🔖 Content-Type reçu: {file.content_type}")
        
        # ✅ CORRECTION : Vérifier par extension si Content-Type est octet-stream
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        
        # Accepter si bon Content-Type OU bonne extension
        is_valid = (file.content_type in allowed_types) or (file_extension in allowed_extensions)
        
        if not is_valid:
            print(f"❌ Format rejeté: {file.content_type} avec extension .{file_extension}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format non supporté. Utilisez JPG, PNG, GIF ou WebP."
            )
        
        print(f"✅ Format accepté: {file.content_type} (.{file_extension})")
        
        # Lire AVANT de vérifier la taille
        file_data = await file.read()
        file_size = len(file_data)
        
        print(f"📏 Taille: {file_size / 1024 / 1024:.2f} MB")
        
        # Vérifier la taille (max 5MB)
        if file_size > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fichier trop volumineux ({file_size / 1024 / 1024:.2f} MB). Max 5MB."
            )
        
        # Sauvegarder le fichier
        file_upload_service = FileUploadService()
        upload_result = await file_upload_service.upload_profile_picture(
            file_data=file_data,
            original_filename=file.filename,
            user_id=current_user.id
        )
        
        if not upload_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=upload_result.get("message", "Erreur sauvegarde")
            )
        
        # Mettre à jour la DB
        user_service = UserService(db)
        result = user_service.update_profile_picture(
            current_user.id, 
            upload_result["file_url"]
        )
        
        if not result["success"]:
            # Nettoyer le fichier si échec DB
            import os
            if os.path.exists(upload_result["file_path"]):
                os.remove(upload_result["file_path"])
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Erreur DB")
            )
        
        print(f"✅ Photo profil mise à jour: {upload_result['file_url']}")
        
        return {
            "success": True,
            "message": "Photo de profil mise à jour",
            "profile_picture": upload_result["file_url"],
            "file_info": {
                "size": upload_result["file_size"],
                "width": upload_result.get("width"),
                "height": upload_result.get("height")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur upload profile: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur: {type(e).__name__}"
        )

@router.post("/me/documents/upload")
async def upload_document_image(
    file: UploadFile = File(...),
    document_type: str = Form(...),  # 'cni' ou 'permis'
    document_side: str = Form(...),  # 'recto' ou 'verso'
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload d'un document d'identité (CNI/Permis) - recto ou verso
    Sauvegarde dans uploads/id_documents/
    """
    from app.services.file_upload import FileUploadService
    from fastapi import Form
    
    # Validation du type de document
    if document_type not in ['cni', 'permis']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type de document invalide. Utilisez 'cni' ou 'permis'."
        )
    
    # Validation du côté du document
    if document_side not in ['recto', 'verso']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Côté du document invalide. Utilisez 'recto' ou 'verso'."
        )
    
    # Vérifier le type de fichier
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format de fichier non supporté. Utilisez JPG, PNG ou GIF."
        )
    
    # Vérifier la taille (max 10MB pour les documents)
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier trop volumineux. Maximum 10MB."
        )
    
    try:
        # Lire les données du fichier
        file_data = await file.read()
        
        # Utiliser FileUploadService pour sauvegarder physiquement
        file_upload_service = FileUploadService()
        upload_result = await file_upload_service.upload_document_image(
            file_data=file_data,
            original_filename=file.filename,
            user_id=current_user.id,
            document_type=document_type,
            document_side=document_side
        )
        
        if not upload_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=upload_result["message"]
            )
        
        print(f"✅ Document {document_type}/{document_side} sauvegardé: {upload_result['file_path']}")
        
        return {
            "success": True,
            "message": f"Document {document_side} uploadé avec succès",
            "image_url": upload_result["file_url"],
            "document_type": document_type,
            "document_side": document_side,
            "file_info": {
                "size": upload_result["file_size"],
                "path": upload_result["file_path"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erreur upload document: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'upload du document"
        )

@router.put("/me/documents")
async def update_documents_info(
    document_type: str,
    recto_image_url: str,
    verso_image_url: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour les informations des documents d'identité
    """
    user_service = UserService(db)
    result = user_service.update_documents(
        user_id=current_user.id,
        document_type=document_type,
        recto_image_url=recto_image_url,
        verso_image_url=verso_image_url
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result


@router.post("/me/cover-picture")
async def upload_cover_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload de la photo de couverture avec sauvegarde physique
    ✅ VERSION FINALE : Accepte application/octet-stream + logs détaillés
    """
    from app.services.file_upload import FileUploadService
    import traceback
    
    try:
        print(f"\n{'='*60}")
        print(f"📥 UPLOAD COVER PICTURE")
        print(f"👤 User: {current_user.id}")
        print(f"📄 File: {file.filename}")
        print(f"🔖 Content-Type: {file.content_type}")
        print(f"{'='*60}\n")
        
        # ✅ CORRECTION : Vérifier par extension si Content-Type est octet-stream
        file_extension = file.filename.split('.')[-1].lower() if file.filename else ''
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp', 'application/octet-stream']
        
        # Validation
        has_valid_content_type = file.content_type in allowed_types
        has_valid_extension = file_extension in allowed_extensions
        
        if not (has_valid_content_type or has_valid_extension):
            print(f"❌ Format rejeté: Content-Type={file.content_type}, Extension=.{file_extension}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Format non supporté. Utilisez JPG, PNG, GIF ou WebP."
            )
        
        if file.content_type == 'application/octet-stream' and not has_valid_extension:
            print(f"❌ octet-stream avec extension invalide: .{file_extension}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extension de fichier invalide: .{file_extension}"
            )
        
        print(f"✅ Format accepté: {file.content_type} (.{file_extension})")
        
        # ✅ CORRECTION : Lire le fichier AVANT de vérifier la taille
        file_data = await file.read()
        file_size = len(file_data)
        
        print(f"📏 Taille: {file_size / 1024 / 1024:.2f} MB")
        
        # Vérifier la taille (max 5MB)
        if file_size > 5 * 1024 * 1024:
            print(f"❌ Fichier trop volumineux: {file_size / 1024 / 1024:.2f} MB")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fichier trop volumineux ({file_size / 1024 / 1024:.2f} MB). Maximum 5MB."
            )
        
        print(f"✅ Taille validée")
        
        # Sauvegarder physiquement le fichier
        print(f"💾 Sauvegarde en cours...")
        file_upload_service = FileUploadService()
        upload_result = await file_upload_service.upload_cover_picture(
            file_data=file_data,
            original_filename=file.filename,
            user_id=current_user.id
        )
        
        if not upload_result["success"]:
            print(f"❌ FileUploadService erreur: {upload_result.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=upload_result.get("message", "Erreur sauvegarde")
            )
        
        print(f"✅ Fichier sauvegardé: {upload_result['file_path']}")
        
        # Mettre à jour la base de données
        print(f"🗄️ Mise à jour DB...")
        user_service = UserService(db)
        result = user_service.update_cover_picture(
            current_user.id, 
            upload_result["file_url"]
        )
        
        if not result["success"]:
            print(f"❌ UserService erreur: {result.get('message')}")
            # Nettoyer le fichier physique si échec DB
            import os
            if os.path.exists(upload_result["file_path"]):
                try:
                    os.remove(upload_result["file_path"])
                    print(f"🗑️ Fichier nettoyé")
                except Exception as e:
                    print(f"⚠️ Impossible de nettoyer: {e}")
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "Erreur DB")
            )
        
        print(f"✅ DB mise à jour")
        print(f"\n{'='*60}")
        print(f"✅ UPLOAD TERMINÉ AVEC SUCCÈS")
        print(f"🔗 URL: {upload_result['file_url']}")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": "Photo de couverture mise à jour", 
            "cover_picture": upload_result["file_url"],
            "file_info": {
                "size": upload_result["file_size"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERREUR INATTENDUE")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print(f"{'='*60}\n")
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur: {type(e).__name__}"
        )

@router.get("/me/contact-info", response_model=ContactInfo)
async def get_my_contact_info(
    current_user: User = Depends(require_complete_profile)
):
    """
    Informations de contact publiques
    """
    return ContactInfo(
        phone=current_user.phone,
        formatted_phone=current_user.formatted_phone,
        city=current_user.city,
        commune=current_user.commune,
        work_radius_km=current_user.work_radius_km,
        coordinates=current_user.coordinates
    )

# manipuler les portfolios
@router.delete("/me/portfolio/item/{filename}")
async def delete_portfolio_item(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Supprimer un élément du portfolio
    """
    import os
    from app.models.portfolio import PortfolioItem
    
    try:
        print(f"🗑️ Tentative de suppression: {filename}")
        
        # Chercher l'élément dans la table portfolio_items
        portfolio_item = db.query(PortfolioItem).filter(
            PortfolioItem.user_id == current_user.id,
            PortfolioItem.file_path.like(f"%{filename}%")
        ).first()
        
        if not portfolio_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Élément du portfolio introuvable"
            )
        
        # Construire le chemin complet du fichier
        file_path = portfolio_item.file_path
        
        # Supprimer l'enregistrement en base de données
        db.delete(portfolio_item)
        db.commit()
        
        # Supprimer le fichier physique
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"✅ Fichier physique supprimé: {file_path}")
        else:
            print(f"⚠️ Fichier physique introuvable: {file_path}")
        
        print(f"✅ Portfolio item supprimé de la BDD")
        
        return {
            "success": True,
            "message": "Élément supprimé avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur lors de la suppression: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}"
        )


@router.post("/me/portfolio/delete-multiple")
async def delete_multiple_portfolio_items(
    filenames: List[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Supprimer plusieurs éléments du portfolio en une fois
    """
    import os
    from app.models.portfolio import PortfolioItem
    
    try:
        print(f"🗑️ Suppression multiple: {len(filenames)} fichiers")
        
        deleted_count = 0
        errors = []
        
        for filename in filenames:
            try:
                # Extraire juste le nom du fichier si c'est une URL complète
                clean_filename = filename.split('/')[-1]
                
                # Chercher l'élément
                portfolio_item = db.query(PortfolioItem).filter(
                    PortfolioItem.user_id == current_user.id,
                    PortfolioItem.file_path.like(f"%{clean_filename}%")
                ).first()
                
                if portfolio_item:
                    file_path = portfolio_item.file_path
                    
                    # Supprimer de la BDD
                    db.delete(portfolio_item)
                    
                    # Supprimer le fichier physique
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    deleted_count += 1
                else:
                    errors.append(f"{filename}: introuvable")
                    
            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
        
        db.commit()
        
        return {
            "success": deleted_count > 0,
            "message": f"{deleted_count} élément(s) supprimé(s)",
            "deleted_count": deleted_count,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur suppression multiple: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {str(e)}"
        )

# =========================================
# RECHERCHE AVANCÉE
# =========================================

@router.post("/search", response_model=UserSearchResponse)
async def search_providers_advanced(
    filters: SearchFilters,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Recherche avancée avec tous les filtres
    """
    user_service = UserService(db)
    result = user_service.search_providers(filters, page, limit)
    return UserSearchResponse(**result)

@router.get("/search/nearby")
async def search_nearby_providers(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius: int = Query(5, ge=1, le=50, description="Rayon de recherche en km"),
    domain: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Recherche géolocalisée dans un rayon spécifique (3-5km)
    """
    user_service = UserService(db)
    
    # Construire les filtres avec géolocalisation
    filters = SearchFilters(
        domain=domain,
        min_rating=min_rating,
        user_latitude=lat,
        user_longitude=lng,
        max_distance_km=radius
    )
    
    result = user_service.search_providers(filters, 1, limit)
    return result

# =========================================
# ROUTES ADMIN
# =========================================

@router.get("/admin/list")
async def admin_get_users_list(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    is_verified: Optional[bool] = Query(None),
    is_blocked: Optional[bool] = Query(None),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Liste des utilisateurs pour l'admin
    """
    try:
        query = self.db.query(User)
        
        # Filtres de recherche
        if search:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                or_(
                    func.lower(User.first_name).like(search_term),
                    func.lower(User.last_name).like(search_term),
                    User.phone.like(search_term),
                    func.lower(User.profession).like(search_term)
                )
            )
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if is_verified is not None:
            query = query.filter(User.is_verified == is_verified)
        
        if is_blocked is not None:
            query = query.filter(User.is_blocked == is_blocked)
        
        # Compter le total
        total = query.count()
        
        # Pagination et tri
        users = query.order_by(desc(User.created_at)).offset((page-1)*limit).limit(limit).all()
        
        # Convertir en réponse admin
        users_data = []
        for user in users:
            user_data = {
                "id": user.id,
                "phone": user.phone,
                "full_name": user.full_name,
                "profession": user.profession,
                "city": user.city,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_blocked": user.is_blocked,
                "blocked_reason": user.blocked_reason,
                "has_active_subscription": user.has_active_subscription,
                "subscription_status": user.subscription.status_display_name if user.subscription else "Aucun",
                "created_at": user.created_at,
                "last_login": user.last_login,
                "profile_completion": user.profile_completion_percentage
            }
            users_data.append(user_data)
        
        return {
            "users": users_data,
            "total": total,
            "page": page,
            "limit": limit,
            "has_next": (page * limit) < total
        }
        
    except Exception as e:
        print(f"Erreur admin_get_users_list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des utilisateurs"
        )

@router.post("/{user_id}/block")
async def admin_block_user(
    user_id: int,
    reason: str = Query(..., min_length=10, description="Raison du blocage"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Bloquer un utilisateur (admin)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur introuvable"
            )
        
        if user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Impossible de bloquer un administrateur"
            )
        
        user.is_blocked = True
        user.blocked_reason = reason
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"Utilisateur {user.full_name} bloqué",
            "blocked_reason": reason
        }
        
    except Exception as e:
        db.rollback()
        print(f"Erreur admin_block_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du blocage"
        )

@router.post("/{user_id}/unblock")
async def admin_unblock_user(
    user_id: int,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Débloquer un utilisateur (admin)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur introuvable"
            )
        
        user.is_blocked = False
        user.blocked_reason = None
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"Utilisateur {user.full_name} débloqué"
        }
        
    except Exception as e:
        db.rollback()
        print(f"Erreur admin_unblock_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du déblocage"
        )

@router.post("/{user_id}/verify")
async def admin_verify_user(
    user_id: int,
    notes: Optional[str] = Query(None, description="Notes de vérification"),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Vérifier un utilisateur (admin)
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur introuvable"
            )
        
        user.is_verified = True
        user.verification_date = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": f"Utilisateur {user.full_name} vérifié",
            "verification_notes": notes
        }
        
    except Exception as e:
        db.rollback()
        print(f"Erreur admin_verify_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification"
        )