"""
Custom storage classes for S3 with organized directory structure
"""
import os
from storages.backends.s3boto3 import S3Boto3Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class RetreatMediaStorage(S3Boto3Storage):
    """
    Custom S3 storage for retreat media files with organized directory structure
    """
    file_overwrite = False
    default_acl = 'private'
    
    def __init__(self, *args, **kwargs):
        # Configure S3 settings from Django settings
        from django.conf import settings
        
        # Only configure S3 if it's enabled
        if getattr(settings, 'USE_S3_FOR_MEDIA', False):
            if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME'):
                kwargs.setdefault('bucket_name', settings.AWS_STORAGE_BUCKET_NAME)
            if hasattr(settings, 'AWS_S3_REGION_NAME'):
                kwargs.setdefault('region_name', settings.AWS_S3_REGION_NAME)
            if hasattr(settings, 'AWS_ACCESS_KEY_ID'):
                kwargs.setdefault('access_key', settings.AWS_ACCESS_KEY_ID)
            if hasattr(settings, 'AWS_SECRET_ACCESS_KEY'):
                kwargs.setdefault('secret_key', settings.AWS_SECRET_ACCESS_KEY)
            if hasattr(settings, 'AWS_S3_CUSTOM_DOMAIN'):
                kwargs.setdefault('custom_domain', settings.AWS_S3_CUSTOM_DOMAIN)
            
            # Set S3 specific options
            kwargs.setdefault('querystring_auth', True)
            kwargs.setdefault('querystring_expire', 3600)
        
        super().__init__(*args, **kwargs)
    
    def get_valid_name(self, name):
        """
        Return a filename that's suitable for use on the target storage system.
        """
        # Keep the original filename as much as possible, only basic validation
        name = super().get_valid_name(name)
        return name


def retreat_audio_upload_path(instance, filename):
    """
    Generate upload path for retreat audio files
    Format: "2025.07.09-15 - GROUP - PLACE - TEACHER/SESSION NAME/ORIGINAL_FILENAME.mp3"
    """
    # Get the retreat from the track's session
    retreat = instance.session.retreat
    
    # Format dates
    start_date = retreat.start_date.strftime('%Y.%m.%d')
    end_date = retreat.end_date.strftime('%d') if retreat.end_date else start_date.split('.')[-1]
    
    # Build folder name parts
    folder_parts = [f"{start_date}-{end_date}"]
    
    # Add group names (abbreviated if multiple)
    if retreat.groups.exists():
        groups = retreat.groups.all()
        if groups.count() == 1:
            folder_parts.append(groups.first().name)
        else:
            # If multiple groups, use first one or create abbreviated list
            folder_parts.append(groups.first().name)
    
    # Add place abbreviations
    if retreat.places.exists():
        place_abbrevs = [place.abbreviation for place in retreat.places.all()]
        folder_parts.append(' + '.join(place_abbrevs))
    
    # Add teacher abbreviations  
    if retreat.teachers.exists():
        teacher_abbrevs = [teacher.abbreviation for teacher in retreat.teachers.all()]
        folder_parts.append(' + '.join(teacher_abbrevs))
    
    # Create retreat folder name
    retreat_folder = ' - '.join(folder_parts)
    
    # Clean session name
    session_name = instance.session.title.replace('/', '-').replace('\\', '-')
    
    # Use original filename (preserve original name)
    original_filename = os.path.basename(filename)
    
    return f"{retreat_folder}/{session_name}/{original_filename}"


def retreat_transcript_upload_path(instance, filename):
    """
    Generate upload path for retreat transcript files
    Same structure as audio but in transcripts folder
    """
    audio_path = retreat_audio_upload_path(instance, filename)
    return f"transcripts/{audio_path}"


def retreat_image_upload_path(instance, filename):
    """
    Generate upload path for retreat images
    """
    # Format dates
    start_date = instance.start_date.strftime('%Y.%m.%d')
    end_date = instance.end_date.strftime('%d') if instance.end_date else start_date.split('.')[-1]
    
    # Clean retreat name
    retreat_name = instance.name.replace('/', '-').replace('\\', '-')
    
    # Create directory structure
    retreat_folder = f"{start_date}-{end_date} — {retreat_name}"
    
    # Get file extension
    file_extension = os.path.splitext(filename)[1]
    
    return f"{retreat_folder}/images/{instance.name.replace('/', '-').replace('\\', '-')}{file_extension}"