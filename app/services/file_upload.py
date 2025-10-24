"""
Service d'upload et compression de fichiers AlloBara
Gestion des images (JPG, PNG, GIF) et vidéos (MP4)
"""

import os
import shutil
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from PIL import Image, ImageOps
import subprocess

from app.core.config import settings
from app.core.security import generate_secure_filename

class FileUploadService:
    def __init__(self):
        self.upload_dir = settings.UPLOAD_DIR
        self.max_image_size_mb = 5
        self.max_video_size_mb = 50
        self.allowed_image_formats = ['jpg', 'jpeg', 'png', 'gif']
        self.allowed_video_formats = ['mp4']
        
        # Créer les dossiers s'ils n'existent pas
        self._ensure_directories()
    
    def _ensure_directories(self):
        """
        Créer les dossiers d'upload s'ils n'existent pas
        """
        directories = [
            f"{self.upload_dir}/profile_pictures",
            f"{self.upload_dir}/cover_pictures", 
            f"{self.upload_dir}/id_documents",
            f"{self.upload_dir}/portfolio",
            f"{self.upload_dir}/portfolio/thumbnails",
            f"{self.upload_dir}/portfolio/compressed"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def get_file_hash(self, file_path: str) -> str:
        """
        Calculer le hash SHA256 d'un fichier pour détecter les doublons
        """
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            print(f"Erreur calcul hash: {e}")
            return None
    
    def validate_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Valider un fichier uploadé
        """
        try:
            if not os.path.exists(file_path):
                return {"valid": False, "error": "Fichier introuvable"}
            
            # Vérifier la taille
            file_size = os.path.getsize(file_path)
            max_size = self.max_image_size_mb if file_type == "image" else self.max_video_size_mb
            max_size_bytes = max_size * 1024 * 1024
            
            if file_size > max_size_bytes:
                return {
                    "valid": False,
                    "error": f"Fichier trop volumineux. Maximum {max_size}MB."
                }
            
            # Vérifier l'extension
            _, ext = os.path.splitext(file_path)
            ext = ext.lower().lstrip('.')
            
            allowed_formats = self.allowed_image_formats if file_type == "image" else self.allowed_video_formats
            if ext not in allowed_formats:
                return {
                    "valid": False,
                    "error": f"Format non supporté. Formats autorisés: {', '.join(allowed_formats)}"
                }
            
            # Validation spécifique aux images
            if file_type == "image":
                try:
                    with Image.open(file_path) as img:
                        width, height = img.size
                        
                        # Vérifier les dimensions minimales
                        if width < 100 or height < 100:
                            return {
                                "valid": False,
                                "error": "Image trop petite. Minimum 100x100 pixels."
                            }
                        
                        # Vérifier les dimensions maximales
                        if width > 5000 or height > 5000:
                            return {
                                "valid": False,
                                "error": "Image trop grande. Maximum 5000x5000 pixels."
                            }
                        
                        return {
                            "valid": True,
                            "width": width,
                            "height": height,
                            "format": img.format,
                            "mode": img.mode
                        }
                        
                except Exception as e:
                    return {"valid": False, "error": "Fichier image corrompu"}
            
            # Validation basique pour les vidéos
            elif file_type == "video":
                return {
                    "valid": True,
                    "format": ext
                }
            
            return {"valid": True}
            
        except Exception as e:
            print(f"Erreur validate_file: {e}")
            return {"valid": False, "error": "Erreur lors de la validation"}
    
    async def upload_profile_picture(
        self,
        file_data: bytes,
        original_filename: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Upload et traitement d'une photo de profil
        """
        try:
            # Générer un nom sécurisé
            secure_filename = generate_secure_filename(original_filename)
            file_path = f"{self.upload_dir}/profile_pictures/{secure_filename}"
            
            # Sauvegarder le fichier
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # Valider
            validation = self.validate_file(file_path, "image")
            if not validation["valid"]:
                os.remove(file_path)
                return {"success": False, "message": validation["error"]}
            
            # Redimensionner pour profil (400x400)
            resized_path = await self._resize_profile_image(file_path, 400)
            
            # Supprimer l'original si redimensionnement réussi
            if resized_path and resized_path != file_path:
                os.remove(file_path)
                file_path = resized_path
            
            # Calculer le hash
            file_hash = self.get_file_hash(file_path)
            
            return {
                "success": True,
                "file_path": file_path,
                "file_url": f"/uploads/profile_pictures/{os.path.basename(file_path)}",
                "file_size": os.path.getsize(file_path),
                "file_hash": file_hash,
                "width": validation.get("width"),
                "height": validation.get("height")
            }
            
        except Exception as e:
            print(f"Erreur upload_profile_picture: {e}")
            return {"success": False, "message": "Erreur lors de l'upload"}
    
    async def upload_cover_picture(
        self,
        file_data: bytes,
        original_filename: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Upload et traitement d'une photo de couverture
        """
        try:
            secure_filename = generate_secure_filename(original_filename)
            file_path = f"{self.upload_dir}/cover_pictures/{secure_filename}"
            
            # Sauvegarder
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # Valider
            validation = self.validate_file(file_path, "image")
            if not validation["valid"]:
                os.remove(file_path)
                return {"success": False, "message": validation["error"]}
            
            # Redimensionner pour couverture (800x400)
            resized_path = await self._resize_cover_image(file_path, 800, 400)
            
            if resized_path and resized_path != file_path:
                os.remove(file_path)
                file_path = resized_path
            
            file_hash = self.get_file_hash(file_path)
            
            return {
                "success": True,
                "file_path": file_path,
                "file_url": f"/uploads/cover_pictures/{os.path.basename(file_path)}",
                "file_size": os.path.getsize(file_path),
                "file_hash": file_hash
            }
            
        except Exception as e:
            print(f"Erreur upload_cover_picture: {e}")
            return {"success": False, "message": "Erreur lors de l'upload"}
    
    async def upload_portfolio_item(
        self,
        file_data: bytes,
        original_filename: str,
        user_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload d'un élément de portfolio (image ou vidéo)
        """
        try:
            secure_filename = generate_secure_filename(original_filename)
            file_path = f"{self.upload_dir}/portfolio/{secure_filename}"
            
            # Déterminer le type
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower().lstrip('.')
            file_type = "image" if ext in self.allowed_image_formats else "video"
            
            # Sauvegarder
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # Valider
            validation = self.validate_file(file_path, file_type)
            if not validation["valid"]:
                os.remove(file_path)
                return {"success": False, "message": validation["error"]}
            
            file_hash = self.get_file_hash(file_path)
            result = {
                "success": True,
                "file_path": file_path,
                "file_url": f"/uploads/portfolio/{os.path.basename(file_path)}",
                "file_type": file_type,
                "file_size": os.path.getsize(file_path),
                "file_hash": file_hash,
                "title": title,
                "description": description
            }
            
            # Traitement spécifique selon le type
            if file_type == "image":
                # Créer une vignette
                thumbnail_path = await self._create_thumbnail(file_path)
                if thumbnail_path:
                    result["thumbnail_path"] = thumbnail_path
                    result["thumbnail_url"] = f"/uploads/portfolio/thumbnails/{os.path.basename(thumbnail_path)}"
                
                result.update({
                    "width": validation.get("width"),
                    "height": validation.get("height")
                })
                
            elif file_type == "video":
                # Extraire métadonnées vidéo
                video_info = await self._get_video_info(file_path)
                if video_info:
                    result.update(video_info)
                
                # Créer une vignette vidéo
                thumbnail_path = await self._create_video_thumbnail(file_path)
                if thumbnail_path:
                    result["thumbnail_path"] = thumbnail_path
                    result["thumbnail_url"] = f"/uploads/portfolio/thumbnails/{os.path.basename(thumbnail_path)}"
            
            return result
            
        except Exception as e:
            print(f"Erreur upload_portfolio_item: {e}")
            return {"success": False, "message": "Erreur lors de l'upload"}

    async def upload_document_image(
        self,
        file_data: bytes,
        original_filename: str,
        user_id: int,
        document_type: str,  # 'cni' ou 'permis'
        document_side: str   # 'recto' ou 'verso'
    ) -> Dict[str, Any]:
        """
        Upload d'un document d'identité dans uploads/id_documents/
        Format: userId_documentType_documentSide_timestamp.jpg
        """
        try:
            # Générer un nom sécurisé et unique
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            secure_filename = f"{user_id}_{document_type}_{document_side}_{timestamp}.jpg"
            file_path = f"{self.upload_dir}/id_documents/{secure_filename}"
            
            # Sauvegarder le fichier
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            # Valider le fichier
            validation = self.validate_file(file_path, "image")
            if not validation["valid"]:
                os.remove(file_path)
                return {"success": False, "message": validation["error"]}
            
            # Redimensionner pour optimiser (max 1200x1600 pour documents)
            resized_path = await self._resize_document_image(file_path, 1200, 1600)
            
            # Si redimensionnement réussi, remplacer l'original
            if resized_path and resized_path != file_path:
                os.remove(file_path)
                file_path = resized_path
            
            # Calculer le hash pour éviter les doublons
            file_hash = self.get_file_hash(file_path)
            
            return {
                "success": True,
                "message": f"Document {document_side} uploadé avec succès",
                "file_path": file_path,
                "file_url": f"/uploads/id_documents/{os.path.basename(file_path)}",
                "file_size": os.path.getsize(file_path),
                "file_hash": file_hash,
                "document_type": document_type,
                "document_side": document_side,
                "width": validation.get("width"),
                "height": validation.get("height")
            }
            
        except Exception as e:
            print(f"Erreur upload_document_image: {e}")
            return {"success": False, "message": f"Erreur lors de l'upload: {str(e)}"}

    async def _resize_document_image(self, file_path: str, max_width: int, max_height: int) -> Optional[str]:
        """
        Redimensionner une image de document en gardant la qualité pour la lisibilité
        """
        try:
            with Image.open(file_path) as img:
                # Convertir en RGB si nécessaire
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Vérifier si redimensionnement nécessaire
                width, height = img.size
                if width <= max_width and height <= max_height:
                    return file_path  # Pas besoin de redimensionner
                
                # Calculer les nouvelles dimensions en gardant le ratio
                ratio = min(max_width / width, max_height / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                
                # Redimensionner avec haute qualité (LANCZOS pour documents)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Sauvegarder avec qualité élevée pour documents
                resized_path = file_path.replace('.jpg', '_resized.jpg')
                img.save(resized_path, "JPEG", quality=92, optimize=True)
                
                return resized_path
                
        except Exception as e:
            print(f"Erreur _resize_document_image: {e}")
            return None
    
    async def _resize_profile_image(self, file_path: str, size: int) -> Optional[str]:
        """
        Redimensionner une image de profil en carré
        """
        try:
            with Image.open(file_path) as img:
                # Convertir en RGB si nécessaire
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Redimensionner en gardant le ratio puis crop au carré
                img = ImageOps.fit(img, (size, size), Image.Resampling.LANCZOS)
                
                # Sauvegarder
                resized_path = file_path.replace('.', f'_resized.')
                img.save(resized_path, "JPEG", quality=85, optimize=True)
                
                return resized_path
                
        except Exception as e:
            print(f"Erreur _resize_profile_image: {e}")
            return None
    
    async def _resize_cover_image(self, file_path: str, width: int, height: int) -> Optional[str]:
        """
        Redimensionner une image de couverture
        """
        try:
            with Image.open(file_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Redimensionner en gardant le ratio puis crop
                img = ImageOps.fit(img, (width, height), Image.Resampling.LANCZOS)
                
                resized_path = file_path.replace('.', f'_cover.')
                img.save(resized_path, "JPEG", quality=90, optimize=True)
                
                return resized_path
                
        except Exception as e:
            print(f"Erreur _resize_cover_image: {e}")
            return None
    
    async def _create_thumbnail(self, image_path: str, size: int = 300) -> Optional[str]:
        """
        Créer une vignette d'image
        """
        try:
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Créer vignette en gardant le ratio
                img.thumbnail((size, size), Image.Resampling.LANCZOS)
                
                # Chemin de la vignette
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                thumbnail_path = f"{self.upload_dir}/portfolio/thumbnails/{base_name}_thumb.jpg"
                
                img.save(thumbnail_path, "JPEG", quality=80, optimize=True)
                return thumbnail_path
                
        except Exception as e:
            print(f"Erreur _create_thumbnail: {e}")
            return None
    
    async def _create_video_thumbnail(self, video_path: str) -> Optional[str]:
        """
        Créer une vignette à partir d'une vidéo (nécessite ffmpeg)
        """
        try:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            thumbnail_path = f"{self.upload_dir}/portfolio/thumbnails/{base_name}_thumb.jpg"
            
            # Commande ffmpeg pour extraire une frame à 2 secondes
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', '00:00:02',
                '-vframes', '1',
                '-vf', 'scale=300:200',
                '-y',  # Overwrite
                thumbnail_path
            ]
            
            # Exécuter la commande
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(thumbnail_path):
                return thumbnail_path
            else:
                print(f"Erreur ffmpeg: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Erreur _create_video_thumbnail: {e}")
            return None
    
    async def _get_video_info(self, video_path: str) -> Optional[Dict]:
        """
        Extraire les métadonnées d'une vidéo
        """
        try:
            # Utiliser ffprobe pour obtenir les infos
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                info = json.loads(result.stdout)
                
                # Extraire les infos pertinentes
                video_stream = next(
                    (s for s in info.get('streams', []) if s.get('codec_type') == 'video'),
                    None
                )
                
                if video_stream:
                    return {
                        "width": video_stream.get("width"),
                        "height": video_stream.get("height"),
                        "duration": float(info.get("format", {}).get("duration", 0)),
                        "bitrate": int(info.get("format", {}).get("bit_rate", 0)),
                        "codec": video_stream.get("codec_name")
                    }
            
            return None
            
        except Exception as e:
            print(f"Erreur _get_video_info: {e}")
            return None
    
    async def compress_image(self, image_path: str, quality: int = 70) -> Optional[str]:
        """
        Compresser une image
        """
        try:
            with Image.open(image_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Chemin du fichier compressé
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                compressed_path = f"{self.upload_dir}/portfolio/compressed/{base_name}_compressed.jpg"
                
                # Sauvegarder avec compression
                img.save(compressed_path, "JPEG", quality=quality, optimize=True)
                
                # Vérifier que la compression a réduit la taille
                original_size = os.path.getsize(image_path)
                compressed_size = os.path.getsize(compressed_path)
                
                if compressed_size < original_size:
                    return compressed_path
                else:
                    # Si pas d'amélioration, supprimer le fichier compressé
                    os.remove(compressed_path)
                    return None
                
        except Exception as e:
            print(f"Erreur compress_image: {e}")
            return None
    
    async def compress_video(self, video_path: str) -> Optional[str]:
        """
        Compresser une vidéo (nécessite ffmpeg)
        """
        try:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            compressed_path = f"{self.upload_dir}/portfolio/compressed/{base_name}_compressed.mp4"
            
            # Commande ffmpeg pour compression
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-c:v', 'libx264',
                '-crf', '28',  # Qualité de compression
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',  # Optimisation web
                '-y',  # Overwrite
                compressed_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(compressed_path):
                # Vérifier que la compression a réduit la taille
                original_size = os.path.getsize(video_path)
                compressed_size = os.path.getsize(compressed_path)
                
                if compressed_size < original_size:
                    return compressed_path
                else:
                    os.remove(compressed_path)
                    return None
            else:
                print(f"Erreur compression vidéo: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"Erreur compress_video: {e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Supprimer un fichier
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception as e:
            print(f"Erreur delete_file: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """
        Récupérer les informations d'un fichier
        """
        try:
            if not os.path.exists(file_path):
                return None
            
            stat = os.stat(file_path)
            _, ext = os.path.splitext(file_path)
            
            return {
                "path": file_path,
                "size": stat.st_size,
                "formatted_size": self._format_file_size(stat.st_size),
                "extension": ext.lower().lstrip('.'),
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime)
            }
            
        except Exception as e:
            print(f"Erreur get_file_info: {e}")
            return None
    
    def _format_file_size(self, size_bytes: int) -> str:
        """
        Formater la taille d'un fichier
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def cleanup_temp_files(self, older_than_hours: int = 24):
        """
        Nettoyer les fichiers temporaires
        """
        try:
            import time
            cutoff_time = time.time() - (older_than_hours * 3600)
            
            temp_dirs = [
                f"{self.upload_dir}/temp",
                f"{self.upload_dir}/portfolio/temp"
            ]
            
            cleaned_count = 0
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                            os.remove(file_path)
                            cleaned_count += 1
            
            return {"cleaned_files": cleaned_count}
            
        except Exception as e:
            print(f"Erreur cleanup_temp_files: {e}")
            return {"error": str(e)}