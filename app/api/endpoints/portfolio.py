"""
Endpoints portfolio AlloBara
Routes pour gestion des rÃ©alisations des prestataires
"""

from typing import List, Dict, Any, Optional  # AJOUT DES IMPORTS MANQUANTS
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.portfolio import PortfolioService
from app.schemas.portfolio import (
    PortfolioItemCreate, PortfolioItemUpdate, PortfolioReorderRequest,
    BulkPortfolioAction, PortfolioGalleryResponse, PortfolioStatsResponse,
    FileUploadResponse, PortfolioSearchResponse, PortfolioModerationRequest
)
from app.api.deps.auth import get_current_user, get_current_admin_user, get_optional_user
from app.models.user import User

# Router pour les endpoints de portfolio
router = APIRouter()

# =========================================
# ROUTES PUBLIQUES
# =========================================

@router.get("/featured")
async def get_featured_portfolio(
    limit: int = Query(20, ge=1, le=50),
    domain: Optional[str] = Query(None, description="Filtrer par domaine"),
    db: Session = Depends(get_db)
):
    """
    Portfolio mis en avant (Ã©lÃ©ments sponsorisÃ©s)
    """
    service = PortfolioService(db)
    featured_items = service.get_featured_portfolio_items(limit, domain)
    
    return {
        "featured_items": featured_items,
        "total": len(featured_items),
        "domain": domain
    }

@router.get("/search", response_model=PortfolioSearchResponse)
async def search_portfolio(
    q: Optional[str] = Query(None, description="Recherche dans les titres/descriptions"),
    file_type: Optional[str] = Query(None, description="image ou video"),
    domain: Optional[str] = Query(None, description="Domaine du prestataire"),
    city: Optional[str] = Query(None, description="Ville du prestataire"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Recherche dans tous les portfolios
    """
    from app.models.portfolio import PortfolioType
    
    service = PortfolioService(db)
    
    # Valider le type de fichier
    portfolio_type = None
    if file_type:
        if file_type.lower() == "image":
            portfolio_type = PortfolioType.IMAGE
        elif file_type.lower() == "video":
            portfolio_type = PortfolioType.VIDEO
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Type de fichier invalide. Utilisez 'image' ou 'video'."
            )
    
    result = service.search_portfolio_items(q, portfolio_type, domain, city, page, limit)
    return PortfolioSearchResponse(**result)

@router.get("/domains/{domain}")
async def get_portfolio_by_domain(
    domain: str,
    limit: int = Query(12, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Exemples de portfolio par domaine d'activitÃ©
    """
    # Valider le domaine
    valid_domains = ["batiment", "menage", "transport", "restauration", "beaute", "autres"]
    if domain not in valid_domains:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domaine invalide. Domaines valides: {', '.join(valid_domains)}"
        )
    
    service = PortfolioService(db)
    items = service.get_portfolio_by_domain(domain, limit)
    
    domain_info = {
        "batiment": {"name": "BÃ¢timent et BTP", "icon": "ðŸ”§"},
        "menage": {"name": "MÃ©nage et Domestique", "icon": "ðŸ§¹"},
        "transport": {"name": "Transport", "icon": "ðŸš—"},
        "restauration": {"name": "Restauration", "icon": "ðŸ½ï¸"},
        "beaute": {"name": "BeautÃ© et Bien-Ãªtre", "icon": "ðŸ’‡ðŸ¾"},
        "autres": {"name": "Autres Services", "icon": "ðŸ› ï¸"}
    }
    
    return {
        "domain": domain_info[domain],
        "portfolio_items": items,
        "total": len(items)
    }

@router.get("/user/{user_id}", response_model=PortfolioGalleryResponse)
async def get_user_portfolio_public(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Portfolio public d'un prestataire
    """
    service = PortfolioService(db)
    portfolio = service.get_user_portfolio(user_id, include_inactive=False)
    
    if portfolio.get("error"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio introuvable"
        )
    
    return PortfolioGalleryResponse(**portfolio)

@router.get("/item/{item_id}")
async def get_portfolio_item_public(
    item_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    DÃ©tails d'un Ã©lÃ©ment de portfolio (public)
    """
    service = PortfolioService(db)
    item = service.get_portfolio_item(item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ã‰lÃ©ment introuvable"
        )
    
    return item

# =========================================
# ROUTES AUTHENTIFIÃ‰ES
# =========================================

@router.get("/me", response_model=PortfolioGalleryResponse)
async def get_my_portfolio(
    include_inactive: bool = Query(False, description="Inclure les Ã©lÃ©ments archivÃ©s"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mon portfolio complet
    """
    service = PortfolioService(db)
    portfolio = service.get_user_portfolio(current_user.id, include_inactive)
    
    return PortfolioGalleryResponse(**portfolio)

@router.get("/me/stats", response_model=PortfolioStatsResponse)
async def get_my_portfolio_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Statistiques de mon portfolio
    """
    service = PortfolioService(db)
    stats = service.get_portfolio_stats(current_user.id)
    
    if "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=stats["error"]
        )
    
    return PortfolioStatsResponse(**stats)

@router.post("/upload", response_model=FileUploadResponse)
async def upload_portfolio_item(
    file: UploadFile = File(..., description="Fichier image ou vidÃ©o"),
    title: Optional[str] = Form(None, description="Titre de la rÃ©alisation"),
    description: Optional[str] = Form(None, description="Description du travail"),
    order_index: int = Form(0, description="Position dans le portfolio"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload d'un nouvel Ã©lÃ©ment de portfolio
    """
    # Valider le fichier
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom de fichier manquant"
        )
    
    # VÃ©rifier les formats autorisÃ©s
    allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'mp4']
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format non supportÃ©. Formats autorisÃ©s: {', '.join(allowed_extensions)}"
        )
    
    # VÃ©rifier la taille
    max_size = 50 * 1024 * 1024  # 50MB max
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier trop volumineux. Maximum 50MB."
        )
    
    # Lire le contenu du fichier
    file_data = await file.read()
    
    # CrÃ©er les donnÃ©es de l'Ã©lÃ©ment
    item_data = PortfolioItemCreate(
        title=title,
        description=description,
        order_index=order_index
    )
    
    # Upload via le service
    service = PortfolioService(db)
    result = await service.create_portfolio_item(
        current_user.id,
        file_data,
        file.filename,
        item_data
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return FileUploadResponse(
        success=True,
        message=result["message"],
        file_id=result["data"]["id"],
        file_url=result["data"]["file_url"],
        thumbnail_url=result["data"]["thumbnail_url"],
        file_size=result["data"]["file_size"]
    )

@router.put("/item/{item_id}")
async def update_portfolio_item(
    item_id: int,
    update_data: PortfolioItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mettre Ã  jour un Ã©lÃ©ment de portfolio
    """
    service = PortfolioService(db)
    result = service.update_portfolio_item(item_id, current_user.id, update_data)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.delete("/item/{item_id}")
async def delete_portfolio_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Supprimer un Ã©lÃ©ment de portfolio
    """
    service = PortfolioService(db)
    result = service.delete_portfolio_item(item_id, current_user.id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.post("/reorder")
async def reorder_portfolio(
    reorder_data: PortfolioReorderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    RÃ©organiser les Ã©lÃ©ments du portfolio
    """
    service = PortfolioService(db)
    result = service.reorder_portfolio_items(current_user.id, reorder_data.item_orders)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.post("/bulk-action")
async def bulk_portfolio_action(
    action_data: BulkPortfolioAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Action en lot sur le portfolio
    """
    # Valider l'action
    allowed_actions = ["archive", "delete", "feature", "unfeature"]
    if action_data.action not in allowed_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action invalide. Actions autorisÃ©es: {', '.join(allowed_actions)}"
        )
    
    service = PortfolioService(db)
    result = await service.bulk_action_portfolio(
        current_user.id,
        action_data.item_ids,
        action_data.action
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.get("/me/item/{item_id}")
async def get_my_portfolio_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DÃ©tails d'un de mes Ã©lÃ©ments de portfolio
    """
    service = PortfolioService(db)
    item = service.get_portfolio_item(item_id, current_user.id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ã‰lÃ©ment introuvable dans votre portfolio"
        )
    
    return item

# =========================================
# ROUTES ADMIN
# =========================================

@router.get("/admin/pending-moderation")
async def admin_get_pending_moderation(
    limit: int = Query(50, ge=1, le=100),
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Ã‰lÃ©ments en attente de modÃ©ration
    """
    service = PortfolioService(db)
    pending_items = service.get_pending_moderation_items(limit)
    
    return {
        "pending_items": pending_items,
        "total_pending": len(pending_items)
    }

@router.post("/admin/moderate/{item_id}")
async def admin_moderate_item(
    item_id: int,
    moderation_data: PortfolioModerationRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    ModÃ©rer un Ã©lÃ©ment de portfolio
    """
    # Valider l'action
    allowed_actions = ["approve", "reject", "hide"]
    if moderation_data.action not in allowed_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action invalide. Actions autorisÃ©es: {', '.join(allowed_actions)}"
        )
    
    service = PortfolioService(db)
    result = service.moderate_portfolio_item(
        item_id,
        moderation_data.action,
        admin_user.id,
        moderation_data.reason
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return result

@router.get("/admin/stats")
async def admin_get_portfolio_stats(
    admin_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Statistiques globales des portfolios
    """
    try:
        from sqlalchemy import func
        from app.models.portfolio import PortfolioItem, PortfolioType, PortfolioStatus
        
        # Statistiques de base
        total_items = db.query(PortfolioItem).count()
        active_items = db.query(PortfolioItem).filter(
            PortfolioItem.status == PortfolioStatus.ACTIVE
        ).count()
        pending_items = db.query(PortfolioItem).filter(
            PortfolioItem.status == PortfolioStatus.PENDING
        ).count()
        
        # Par type de fichier
        images_count = db.query(PortfolioItem).filter(
            PortfolioItem.file_type == PortfolioType.IMAGE
        ).count()
        videos_count = db.query(PortfolioItem).filter(
            PortfolioItem.file_type == PortfolioType.VIDEO
        ).count()
        
        # Statistiques de vues
        total_views = db.query(func.sum(PortfolioItem.views_count)).scalar() or 0
        
        # Ã‰lÃ©ments les plus vus
        top_viewed = db.query(PortfolioItem).join(User).filter(
            PortfolioItem.views_count > 0
        ).order_by(
            PortfolioItem.views_count.desc()
        ).limit(5).all()
        
        top_viewed_data = []
        for item in top_viewed:
            top_viewed_data.append({
                "id": item.id,
                "title": item.get_display_title(),
                "views": item.views_count,
                "user_name": item.user.full_name,
                "file_type": item.file_type.value
            })
        
        return {
            "total_items": total_items,
            "active_items": active_items,
            "pending_moderation": pending_items,
            "images_count": images_count,
            "videos_count": videos_count,
            "total_views": total_views,
            "average_views_per_item": round(total_views / max(1, total_items), 1),
            "top_viewed_items": top_viewed_data
        }
        
    except Exception as e:
        print(f"Erreur admin_get_portfolio_stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la rÃ©cupÃ©ration des statistiques"
        )

# =========================================
# UTILITAIRES
# =========================================

@router.get("/formats")
async def get_supported_formats():
    """
    Formats de fichiers supportÃ©s
    """
    return {
        "images": {
            "formats": ["JPG", "JPEG", "PNG", "GIF"],
            "max_size_mb": 5,
            "recommended_size": "800x600 pixels minimum",
            "compression": "Automatique avec optimisation"
        },
        "videos": {
            "formats": ["MP4"],
            "max_size_mb": 50,
            "recommended_duration": "30 secondes Ã  2 minutes",
            "compression": "Optimisation web automatique"
        },
        "thumbnails": {
            "size": "300x200 pixels",
            "format": "JPG",
            "generation": "Automatique pour tous les fichiers"
        },
        "limits": {
            "max_items_per_portfolio": 20,
            "featured_items_limit": 5
        }
    }

@router.get("/examples")
async def get_portfolio_examples():
    """
    Exemples de bon portfolio par domaine
    """
    return {
        "tips": [
            "Montrez vos meilleurs travaux terminÃ©s",
            "Utilisez des photos bien Ã©clairÃ©es",
            "Ajoutez des descriptions claires",
            "Variez les angles de vue",
            "Mettez en avant vos spÃ©cialitÃ©s"
        ],
        "examples_by_domain": {
            "batiment": [
                "Photos avant/aprÃ¨s d'une rÃ©novation",
                "DÃ©tails de finitions soignÃ©es",
                "Vue d'ensemble du chantier terminÃ©"
            ],
            "menage": [
                "Espaces nettoyÃ©s avec soin",
                "Organisation d'espaces de vie",
                "RÃ©sultats de nettoyage approfondi"
            ],
            "restauration": [
                "Plats prÃ©parÃ©s et dressÃ©s",
                "Service en action",
                "VariÃ©tÃ© du menu proposÃ©"
            ]
        },
        "quality_guidelines": {
            "resolution_min": "800x600 pixels",
            "lighting": "Ã‰clairage naturel privilÃ©giÃ©",
            "composition": "Sujet centrÃ© et bien cadrÃ©",
            "clarity": "Images nettes sans flou"
        }
    }

@router.get("/inspiration")
async def get_portfolio_inspiration(
    domain: Optional[str] = Query(None),
    limit: int = Query(9, ge=3, le=15),
    db: Session = Depends(get_db)
):
    """
    Portfolio d'inspiration pour les nouveaux prestataires
    """
    service = PortfolioService(db)
    
    if domain:
        items = service.get_portfolio_by_domain(domain, limit)
        title = f"Exemples de portfolio en {domain}"
    else:
        items = service.get_featured_portfolio_items(limit)
        title = "Portfolio inspirants"
    
    return {
        "title": title,
        "inspiration_items": items,
        "total": len(items),
        "tips": [
            "Photographiez vos travaux sous plusieurs angles",
            "Documentez le processus de rÃ©alisation",
            "Montrez les dÃ©tails qui font la diffÃ©rence",
            "N'hÃ©sitez pas Ã  expliquer vos techniques"
        ]
    }