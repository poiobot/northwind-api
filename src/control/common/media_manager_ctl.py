from domain.common.media import Media
from data.generic_dao import GenericDAO
from services.storage.storage_service_factory import StorageServiceFactory
from api import settings

from fastapi import UploadFile
from io import BytesIO
from typing import Tuple, Union, List, Dict, Any, Optional
from PIL import Image
import shutil
import os
from bson import ObjectId

# Supported MIME types for different media categories
IMAGE_MIME_TYPES = [
    "image/jpeg", "image/png", "image/gif", "image/bmp",
    "image/webp", "image/heic", "image/heif",
    "image/tiff", "image/x-icon", "image/svg+xml"
]

VIDEO_MIME_TYPES = [
    "video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo",  # avi
    "video/x-ms-wmv", "video/webm", "video/ogg", "video/3gpp",
    "video/3gpp2", "video/x-matroska"  # mkv
]

AUDIO_MIME_TYPES = [
    "audio/mp4", "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/ogg", "audio/webm", "audio/mp4", "audio/aac",
    "audio/x-ms-wma", "audio/flac", "audio/amr", "audio/3gpp",
    "audio/3gpp2", "audio/midi", "audio/x-midi"
]

DOCUMENT_MIME_TYPES = [
    "text/plain", "application/pdf", "application/rtf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/csv", "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation"
]


# Combined list of all supported media MIME types
ALL_MEDIA_MIME_TYPES = IMAGE_MIME_TYPES + VIDEO_MIME_TYPES + AUDIO_MIME_TYPES + DOCUMENT_MIME_TYPES


class MediaManagerCTL:
    """
    Controller for managing media file operations including upload, storage, and URL generation.

    Handles the complete lifecycle of media files from upload to cloud storage,
    including validation, temporary storage, cloud upload, and database persistence.
    """

    dao = GenericDAO()
    storage = StorageServiceFactory().get_service(provider=settings.STORAGE_PROVIDER)

    @staticmethod
    def resize_image(file_path: str, max_size: int, quality: int = 85) -> bool:
        """
        Resize an image to fit within a square while maintaining aspect ratio.

        :param file_path: Path to the image file to resize
        :param max_size: Maximum dimension (width or height) in pixels
        :param quality: JPEG quality (1-100), default 85
        :return: True if resized successfully, False otherwise
        """
        try:
            # Open the image
            with Image.open(file_path) as img:
                # Convert RGBA to RGB if saving as JPEG
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create a white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Get original dimensions
                width, height = img.size

                # Check if resizing is needed
                if width <= max_size and height <= max_size:
                    return True  # No resize needed

                # Calculate new dimensions maintaining aspect ratio
                if width > height:
                    new_width = max_size
                    new_height = int((max_size / width) * height)
                else:
                    new_height = max_size
                    new_width = int((max_size / height) * width)

                # Resize image using high-quality resampling
                resized_img = img.resize((new_width, new_height), Image.LANCZOS)

                # Save the resized image
                resized_img.save(file_path, format='JPEG', quality=quality, optimize=True)

                return True

        except Exception as e:
            print(f"Error resizing image: {e}")
            return False

    @classmethod
    def upload(cls, user_id: str, parent_dir: str, file: Union[UploadFile, BytesIO], max_image_size: Optional[int] = 1920, image_quality: int = 85) -> Tuple[str, Union[str, Media]]:
        """
        Upload a media file to cloud storage and create a database record.
        Images are automatically resized to fit within max_image_size while maintaining aspect ratio.

        :param user_id: ID of the user uploading the file
        :param parent_dir: Parent directory path in cloud storage
        :param file: File object to upload (FastAPI UploadFile or BytesIO)
        :param max_image_size: Maximum width/height for images in pixels (default 1920). Set to None to disable resizing.
        :param image_quality: JPEG quality for resized images (1-100, default 85)
        :return: Tuple containing status ("MEDIA_UPLOADED" or "UNSUPPORTED_MEDIA_FORMAT") and Media object (None if error)
        """
        # Validate file type against supported MIME types
        if file.content_type not in ALL_MEDIA_MIME_TYPES:
            return "UNSUPPORTED_MEDIA_FORMAT", None

        # Extract file extension from MIME type
        extension = file.content_type.split("/")[-1]
        file_path = os.path.join(settings.LOCAL_STORAGE_PATH, f"{str(ObjectId())}.{extension}")

        # Ensure directory exists
        os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)

        # Save file after seeking back
        file.file.seek(0)
        with open(file_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        # Resize ONLY if it's an image type and max_image_size is set
        is_image = file.content_type in IMAGE_MIME_TYPES
        is_video = file.content_type in VIDEO_MIME_TYPES
        is_audio = file.content_type in AUDIO_MIME_TYPES

        if is_image and max_image_size is not None:
            # Only apply resizing to images, skip videos and audio
            resize_success = cls.resize_image(file_path, max_image_size, image_quality)
            if not resize_success:
                # If resize fails, continue with original file
                print(f"Warning: Failed to resize image {file.filename}, uploading original")
        elif is_video or is_audio:
            # Videos and audio files are uploaded as-is without any processing
            pass

        target_path = f"{parent_dir}/{user_id.split('/')[-1]}"

        # Upload to cloud storage
        media_id = cls.storage.upload(file_path=file_path, target_path=target_path, volume=settings.STORAGE_VOLUME)
        url = cls.storage.get_file_url(volume=settings.STORAGE_VOLUME, file_path=media_id, expires=1440)

        # Clean up
        os.remove(file_path)

        _media = Media(
            owner=user_id,
            provider=settings.STORAGE_PROVIDER,
            volume=settings.STORAGE_VOLUME,
            oid=media_id,
            url=url,
            type=file.content_type
        )

        # Create media object storing cloud storage data
        media = cls.dao.insert(entity=Media, data=_media)

        return "MEDIA_UPLOADED", media

    @classmethod
    def get_url(cls, media: Union[str, Media]) -> Tuple[str, Media or None]:
        """
        Generate or retrieve an accessible URL for a media file.

        :param media: Either a media ID string or Media object
        :return: Tuple containing status ("MEDIA_URL" or "NO_MEDIA_FOUND") and URL string (None if error)
        """
        if isinstance(media, str):
            media = cls.dao.find_by_id(entity=Media, id=media)
        if not isinstance(media, Media):
            return "NO_MEDIA_FOUND", None
        # media_id = media.oid
        # media_id = media_id[1:] if media_id[0] == "/" else media_id
        media.url = cls.storage.get_file_url(volume=settings.STORAGE_VOLUME, file_path=media.oid, expires=1440)
        return "MEDIA", media