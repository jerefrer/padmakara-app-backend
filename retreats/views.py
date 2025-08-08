"""
Custom admin views for retreat management
"""
import json
import logging
import time
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.db import transaction, connection
from django.db import models
from .models import Session, Track
from utils.track_parser import parse_track_filename, validate_audio_file, get_file_size_mb

# Set up logging
logger = logging.getLogger(__name__)


@staff_member_required
def bulk_upload_tracks_view(request, session_id):
    """
    Bulk upload tracks view using proper Django admin integration
    """
    from django.contrib import admin
    from django.contrib.admin.views.decorators import staff_member_required
    
    session = get_object_or_404(Session, id=session_id)
    
    # Get the admin context for proper Unfold integration
    admin_site = admin.site
    model_admin = admin_site._registry.get(Track)
    
    if not model_admin:
        # Fallback if Track is not registered
        from retreats.admin import TrackAdmin
        model_admin = TrackAdmin(Track, admin_site)
    
    # Create context with admin site integration and Unfold-specific settings
    context = {
        'session': session,
        'title': f'Upload Tracks for {session.title}',
        'existing_tracks': session.tracks.all().order_by('track_number'),
        # Full admin site context
        'opts': Track._meta,
        'app_label': Track._meta.app_label,
        'model_name': Track._meta.model_name,
        'verbose_name': Track._meta.verbose_name,
        'verbose_name_plural': Track._meta.verbose_name_plural,
        'has_view_permission': model_admin.has_view_permission(request),
        'has_add_permission': model_admin.has_add_permission(request),
        'has_change_permission': model_admin.has_change_permission(request),
        'has_delete_permission': model_admin.has_delete_permission(request),
        'site_title': admin_site.site_title,
        'site_header': admin_site.site_header,
        'site_url': admin_site.site_url,
        'has_permission': admin_site.has_permission(request),
        'available_apps': admin_site.get_app_list(request),
        'is_popup': False,
        # Add admin site each_context for proper Unfold integration
        **admin_site.each_context(request),
    }
    
    return render(request, 'admin/retreats/bulk_upload_tracks.html', context)


@staff_member_required
def bulk_upload_tracks(request, session_id):
    """
    Legacy function-based view - redirect to class-based view
    """
    # For now, keep the old implementation for backward compatibility
    session = get_object_or_404(Session, id=session_id)
    
    if request.method == 'GET':
        # Show upload interface with proper admin context
        from .models import Track
        from django.contrib import admin
        from django.contrib.admin.views.main import ChangeList
        
        # Get the admin context like a normal admin view
        admin_site = admin.site
        model_admin = admin_site._registry[Track]
        
        # Create context with admin site integration and Unfold-specific settings
        context = {
            'session': session,
            'title': f'Upload Tracks for {session.title}',
            'existing_tracks': session.tracks.all().order_by('track_number'),
            # Full admin site context
            'opts': Track._meta,
            'app_label': Track._meta.app_label,
            'model_name': Track._meta.model_name,
            'verbose_name': Track._meta.verbose_name,
            'verbose_name_plural': Track._meta.verbose_name_plural,
            'has_view_permission': model_admin.has_view_permission(request),
            'has_add_permission': model_admin.has_add_permission(request),
            'has_change_permission': model_admin.has_change_permission(request),
            'has_delete_permission': model_admin.has_delete_permission(request),
            'site_title': admin_site.site_title,
            'site_header': admin_site.site_header,
            'site_url': admin_site.site_url,
            'has_permission': admin_site.has_permission(request),
            'available_apps': admin_site.get_app_list(request),
            'is_popup': False,
            # Unfold-specific context
            'is_nav_sidebar_enabled': True,  # Enable sidebar
            'cl': None,  # No changelist but needed for some templates
        }
        return render(request, 'admin/retreats/bulk_upload_tracks.html', context)
    
    return redirect('admin:retreats_session_change', session_id)


@staff_member_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_s3_presigned_url(request, session_id):
    """
    Generate presigned URL for direct S3 upload
    """
    session = get_object_or_404(Session, id=session_id)
    
    try:
        import boto3
        from django.conf import settings
        import uuid
        from utils.track_parser import parse_track_filename
        from utils.storage import retreat_audio_upload_path
        
        data = json.loads(request.body)
        filename = data.get('filename')
        file_size = data.get('file_size')
        
        if not filename:
            return JsonResponse({'error': 'Filename is required'}, status=400)
        
        # Parse filename to get track info
        track_info = parse_track_filename(filename)
        
        # Create a temporary track instance to generate the S3 path
        temp_track = Track(session=session, track_number=track_info['track_number'])
        s3_key = retreat_audio_upload_path(temp_track, filename)
        
        # Generate presigned URL
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        upload_id = str(uuid.uuid4())
        
        presigned_post = s3_client.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=s3_key,
            Fields={"acl": "private"},
            Conditions=[
                {"acl": "private"},
                ["content-length-range", 1, file_size * 2]  # Allow up to 2x the reported file size
            ],
            ExpiresIn=3600  # 1 hour
        )
        
        return JsonResponse({
            'presigned_post': presigned_post,
            's3_key': s3_key,
            'upload_id': upload_id,
            'track_info': track_info
        })
        
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return JsonResponse({'error': f'Failed to generate upload URL: {str(e)}'}, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["POST"])
def complete_s3_upload(request, session_id):
    """
    Complete S3 upload by creating Track record
    """
    session = get_object_or_404(Session, id=session_id)
    
    try:
        data = json.loads(request.body)
        s3_key = data.get('s3_key')
        upload_id = data.get('upload_id')
        track_info = data.get('track_info')
        file_size = data.get('file_size')
        
        if not all([s3_key, track_info]):
            return JsonResponse({'error': 'Missing required data'}, status=400)
        
        # Use database-level locking to prevent conflicts
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    locked_session = Session.objects.select_for_update().get(id=session_id)
                    
                    # Check if track number already exists
                    existing_track = locked_session.tracks.filter(track_number=track_info['track_number']).first()
                    if existing_track:
                        max_track = locked_session.tracks.aggregate(max_num=models.Max('track_number'))['max_num'] or 0
                        track_info['track_number'] = max_track + 1
                        logger.info(f"Track number conflict resolved, using: {track_info['track_number']}")
                    
                    # Determine language
                    language = 'en'
                    if locked_session.retreat.groups.exists():
                        first_group = locked_session.retreat.groups.first().name.lower()
                        if first_group.startswith('pt') or 'portuguese' in first_group or 'português' in first_group:
                            language = 'pt'
                    
                    # Create track with S3 file reference
                    from utils.storage import RetreatMediaStorage
                    storage = RetreatMediaStorage()
                    
                    track = Track.objects.create(
                        session=locked_session,
                        title=track_info['title'],
                        track_number=track_info['track_number'],
                        file_size=file_size,
                        language=language
                    )
                    
                    # Set the file field manually to point to the S3 object
                    track.audio_file.name = s3_key
                    track.save()
                    
                    logger.info(f"Track created successfully: ID={track.id}, S3 Key={s3_key}")
                    
                    return JsonResponse({
                        'success': True,
                        'track': {
                            'id': track.id,
                            'title': track.title,
                            'track_number': track.track_number,
                            'file_size_mb': track.file_size_mb,
                            'filename': track_info['original_filename'],
                            's3_url': track.audio_file.url if track.audio_file else None,
                        }
                    })
                    
                break  # Success, exit retry loop
                
            except Exception as db_error:
                logger.error(f"Database error on attempt {attempt + 1}: {str(db_error)}")
                if attempt == max_retries - 1:
                    raise db_error
                else:
                    time.sleep(0.1 * (attempt + 1))
        
    except Exception as e:
        logger.error(f"Error completing S3 upload: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'Upload completion failed: {str(e)}'}, status=500)


@staff_member_required
@csrf_exempt
@require_http_methods(["POST"])
def upload_track_file(request, session_id):
    """
    Handle individual file upload with progress tracking and S3 storage
    """
    session = get_object_or_404(Session, id=session_id)
    start_time = time.time()
    
    file_name = request.FILES.get('file').name if 'file' in request.FILES else 'unknown'
    logger.info(f"Starting upload for session {session_id}, file: {file_name}")
    
    try:
        if 'file' not in request.FILES:
            logger.error("No file provided in request")
            return JsonResponse({'error': 'No file provided'}, status=400)
        
        uploaded_file = request.FILES['file']
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        logger.info(f"Processing file: {uploaded_file.name}, size: {file_size_mb:.2f} MB")
        
        # Validate file type
        if not validate_audio_file(uploaded_file.name):
            logger.error(f"Invalid file type: {uploaded_file.name}")
            return JsonResponse({
                'error': f'Unsupported file type: {uploaded_file.name}'
            }, status=400)
        
        # Parse filename to get track info
        track_info = parse_track_filename(uploaded_file.name)
        logger.info(f"Parsed track info: {track_info}")
        
        # Use database-level locking to prevent conflicts
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # Use select_for_update to lock the session during track number assignment
                    locked_session = Session.objects.select_for_update().get(id=session_id)
                    
                    # Check if track number already exists
                    existing_track = locked_session.tracks.filter(track_number=track_info['track_number']).first()
                    if existing_track:
                        # Find next available track number
                        max_track = locked_session.tracks.aggregate(max_num=models.Max('track_number'))['max_num'] or 0
                        track_info['track_number'] = max_track + 1
                        logger.info(f"Track number conflict resolved, using: {track_info['track_number']}")
                    
                    # Determine language
                    language = 'en'  # default
                    if locked_session.retreat.groups.exists():
                        first_group = locked_session.retreat.groups.first().name.lower()
                        if first_group.startswith('pt') or 'portuguese' in first_group or 'português' in first_group:
                            language = 'pt'
                    
                    logger.info(f"Creating track with S3 upload - Track #{track_info['track_number']}: {track_info['title']}")
                    
                    # Create track - the audio_file field will automatically upload to S3
                    # via our custom upload_to function
                    track = Track.objects.create(
                        session=locked_session,
                        title=track_info['title'],
                        track_number=track_info['track_number'],
                        audio_file=uploaded_file,  # This triggers S3 upload automatically
                        file_size=uploaded_file.size,
                        language=language
                    )
                    
                    # Log the actual file path/URL to verify S3 upload
                    logger.info(f"Track created. S3 Path: {track.audio_file.name}")
                    
                    # Check if file was actually saved to S3
                    if hasattr(track.audio_file.storage, 'bucket_name'):
                        logger.info(f"✅ S3 Upload successful. Bucket: {track.audio_file.storage.bucket_name}")
                    else:
                        logger.warning("❌ Local file storage - S3 upload failed")
                    
                    # Log successful creation
                    upload_time = time.time() - start_time
                    logger.info(f"Track created successfully: ID={track.id}, S3 URL={track.audio_file.url if track.audio_file else 'None'}")
                    logger.info(f"Upload completed in {upload_time:.2f} seconds")
                    
                    return JsonResponse({
                        'success': True,
                        'track': {
                            'id': track.id,
                            'title': track.title,
                            'track_number': track.track_number,
                            'file_size_mb': track.file_size_mb,
                            'filename': track_info['original_filename'],
                            's3_url': track.audio_file.url if track.audio_file else None,
                            'upload_time': f"{upload_time:.2f}s"
                        }
                    })
                    
                break  # Success, exit retry loop
                
            except Exception as db_error:
                logger.error(f"Database error on attempt {attempt + 1}: {str(db_error)}")
                if attempt == max_retries - 1:
                    # Last attempt failed
                    raise db_error
                else:
                    # Wait before retry
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
        
    except Exception as e:
        upload_time = time.time() - start_time
        logger.error(f"Upload failed after {upload_time:.2f}s: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Upload failed: {str(e)}'
        }, status=500)


@staff_member_required
def check_upload_progress(request, session_id):
    """
    Check upload progress (for future enhancement with async uploads)
    """
    session = get_object_or_404(Session, id=session_id)
    
    tracks = list(session.tracks.values(
        'id', 'title', 'track_number', 'file_size', 'audio_file'
    ))
    
    return JsonResponse({
        'session_id': session_id,
        'tracks_count': len(tracks),
        'tracks': tracks
    })