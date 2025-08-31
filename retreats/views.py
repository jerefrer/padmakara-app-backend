"""
Custom admin views for retreat management and API endpoints
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
from django.utils import timezone
from django.db import models
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import Session, Track, Retreat, RetreatGroup, RetreatParticipation, DownloadRequest
from utils.track_parser import parse_track_filename, validate_audio_file, get_file_size_mb

# Set up logging
logger = logging.getLogger(__name__)


def check_s3_file_exists(s3_key, bucket_name=None):
    """
    Validate if an S3 file exists and is accessible.
    
    Args:
        s3_key (str): The S3 key/path to check
        bucket_name (str): S3 bucket name (defaults to temp downloads bucket)
        
    Returns:
        dict: {
            'exists': bool,
            'accessible': bool, 
            'error': str or None,
            'file_size': int or None
        }
    """
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    from django.conf import settings
    
    # Default to temp downloads bucket
    if not bucket_name:
        bucket_name = 'padmakara-pt-temp-downloads'
    
    try:
        # Create S3 client with explicit credentials
        s3_client = boto3.client(
            's3',
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
            region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'eu-west-3')
        )
        
        # Check if file exists by getting object metadata
        response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        
        logger.info(f"S3 file validation successful: {s3_key} ({response.get('ContentLength', 0)} bytes)")
        
        return {
            'exists': True,
            'accessible': True,
            'error': None,
            'file_size': response.get('ContentLength', 0)
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        
        if error_code == '404':
            # File doesn't exist
            logger.warning(f"S3 file not found: {s3_key} in bucket {bucket_name}")
            return {
                'exists': False,
                'accessible': False,
                'error': 'File not found',
                'file_size': None
            }
        elif error_code == '403':
            # Permission denied
            logger.error(f"S3 access denied: {s3_key} in bucket {bucket_name}")
            return {
                'exists': True,  # File exists but not accessible
                'accessible': False,
                'error': 'Access denied',
                'file_size': None
            }
        else:
            # Other S3 error
            logger.error(f"S3 error checking {s3_key}: {error_code} - {e}")
            return {
                'exists': False,
                'accessible': False,
                'error': f"S3 error: {error_code}",
                'file_size': None
            }
    
    except NoCredentialsError:
        logger.error(f"AWS credentials not available for S3 validation")
        return {
            'exists': False,
            'accessible': False,
            'error': 'AWS credentials not configured',
            'file_size': None
        }
    
    except Exception as e:
        logger.error(f"Unexpected error validating S3 file {s3_key}: {str(e)}")
        return {
            'exists': False,
            'accessible': False,
            'error': f"Validation error: {str(e)}",
            'file_size': None
        }


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
        
        # Extract client-computed duration and metadata
        client_duration_seconds = data.get('client_duration_seconds')
        client_metadata = data.get('client_metadata', {})
        
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
                    
                    # Create track with S3 file reference and client-computed duration
                    from utils.storage import RetreatMediaStorage
                    storage = RetreatMediaStorage()
                    
                    # Prepare track creation data
                    track_data = {
                        'session': locked_session,
                        'title': track_info['title'],
                        'track_number': track_info['track_number'],
                        'file_size': file_size,
                        'language': language
                    }
                    
                    # Include client-computed duration if available
                    if client_duration_seconds and client_duration_seconds > 0:
                        track_data['duration_seconds'] = client_duration_seconds
                        track_data['duration_minutes'] = max(1, round(client_duration_seconds / 60))
                        logger.info(f"Using client-computed duration: {client_duration_seconds}s")
                    else:
                        logger.info("No client duration provided, will use server-side calculation later")
                    
                    track = Track.objects.create(**track_data)
                    
                    # Set the file field manually to point to the S3 object
                    track.audio_file.name = s3_key
                    track.save()
                    
                    # Log client metadata for debugging
                    if client_metadata:
                        logger.info(f"Client metadata for track {track.id}: {json.dumps(client_metadata)}")
                    
                    logger.info(f"Track created successfully: ID={track.id}, S3 Key={s3_key}, Duration={track.duration_seconds}s")
                    
                    return JsonResponse({
                        'success': True,
                        'track': {
                            'id': track.id,
                            'title': track.title,
                            'track_number': track.track_number,
                            'file_size_mb': track.file_size_mb,
                            'duration_seconds': track.duration_seconds,
                            'filename': track_info['original_filename'],
                            's3_url': track.audio_file.url if track.audio_file else None,
                            'client_computed': bool(client_duration_seconds)
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


# API Endpoints for Frontend
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_retreats(request):
    """
    Get all retreats for which the authenticated user has a Retreat Participation with status 'attended'
    """
    try:
        user = request.user
        
        # Get all retreats where user has 'attended' participation status
        attended_retreats = Retreat.objects.filter(
            participants__user=user,
            participants__status='attended'
        ).prefetch_related(
            'groups',
            'places', 
            'teachers',
            'sessions__tracks'
        ).distinct().order_by('-start_date')
        
        # Build retreat groups structure
        retreat_groups_data = []
        
        # Group retreats by their retreat groups
        groups_dict = {}
        for retreat in attended_retreats:
            for group in retreat.groups.all():
                if group.id not in groups_dict:
                    groups_dict[group.id] = {
                        'group': group,
                        'retreats': []
                    }
                groups_dict[group.id]['retreats'].append(retreat)
        
        # Build the response structure
        for group_id, group_data in groups_dict.items():
            group = group_data['group']
            retreats = group_data['retreats']
            
            gatherings = []
            for retreat in retreats:
                # Build sessions data
                sessions_data = []
                for session in retreat.sessions.all().order_by('session_number'):
                    # Build tracks data
                    tracks_data = []
                    for track in session.tracks.all().order_by('track_number'):
                        # Use a default duration if none is set (approximately 30 minutes)
                        duration_seconds = track.duration_minutes * 60 if track.duration_minutes > 0 else 1800
                        tracks_data.append({
                            'id': str(track.id),
                            'title': track.title,
                            'duration': duration_seconds,  # Convert to seconds
                            'audioUrl': '',  # Will be provided via presigned URLs
                            'transcriptUrl': '',  # Will be provided via presigned URLs
                            'order': track.track_number
                        })
                    
                    sessions_data.append({
                        'id': str(session.id),
                        'name': session.title,
                        'type': session.get_time_period_display().lower(),
                        'date': session.session_date.isoformat(),
                        'tracks': tracks_data
                    })
                
                # Determine season based on start date
                season = 'spring' if retreat.start_date.month in [3, 4, 5, 6] else 'fall'
                
                gatherings.append({
                    'id': str(retreat.id),
                    'name': retreat.name,
                    'season': season,
                    'year': retreat.start_date.year,
                    'startDate': retreat.start_date.isoformat(),
                    'endDate': retreat.end_date.isoformat(),
                    'sessions': sessions_data
                })
            
            retreat_groups_data.append({
                'id': str(group.id),
                'name': group.name,
                'description': group.description,
                'gatherings': gatherings
            })
        
        # Calculate total stats
        total_gatherings = sum(len(group_data['gatherings']) for group_data in retreat_groups_data)
        total_tracks = 0
        for group_data in retreat_groups_data:
            for gathering in group_data['gatherings']:
                for session in gathering['sessions']:
                    total_tracks += len(session['tracks'])
        
        # Get recent gatherings (last 3)
        recent_gatherings = []
        all_gatherings = []
        for group_data in retreat_groups_data:
            all_gatherings.extend(group_data['gatherings'])
        
        # Sort by start date and take last 3
        all_gatherings.sort(key=lambda x: x['startDate'], reverse=True)
        recent_gatherings = all_gatherings[:3]
        
        response_data = {
            'retreat_groups': retreat_groups_data,
            'recent_gatherings': recent_gatherings,
            'total_stats': {
                'total_groups': len(retreat_groups_data),
                'total_gatherings': total_gatherings,
                'total_tracks': total_tracks,
                'completed_tracks': int(total_tracks * 0.3)  # Mock completion percentage
            }
        }
        
        logger.info(f"Retrieved {len(retreat_groups_data)} retreat groups for user {user.id}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving user retreats: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve retreats'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def retreat_details(request, retreat_id):
    """
    Get detailed information about a specific retreat including all sessions and tracks
    """
    try:
        user = request.user
        
        # Get retreat with user access check
        retreat = get_object_or_404(
            Retreat.objects.filter(
                participants__user=user,
                participants__status='attended'
            ).prefetch_related(
                'groups',
                'places',
                'teachers', 
                'sessions__tracks'
            ),
            id=retreat_id
        )
        
        # Build sessions data
        sessions_data = []
        for session in retreat.sessions.all().order_by('session_number'):
            # Build tracks data
            tracks_data = []
            for track in session.tracks.all().order_by('track_number'):
                # Use a default duration if none is set (approximately 30 minutes)
                duration_seconds = track.duration_minutes * 60 if track.duration_minutes > 0 else 1800
                tracks_data.append({
                    'id': str(track.id),
                    'title': track.title,
                    'duration': duration_seconds,  # Convert to seconds
                    'audioUrl': '',  # Will be provided via presigned URLs
                    'transcriptUrl': '',  # Will be provided via presigned URLs
                    'order': track.track_number
                })
            
            sessions_data.append({
                'id': str(session.id),
                'name': session.title,
                'type': session.get_time_period_display().lower(),
                'date': session.session_date.isoformat(),
                'tracks': tracks_data
            })
        
        # Get retreat group info
        retreat_group = retreat.groups.first()
        
        # Determine season based on start date
        season = 'spring' if retreat.start_date.month in [3, 4, 5, 6] else 'fall'
        
        response_data = {
            'id': str(retreat.id),
            'name': retreat.name,
            'season': season,
            'year': retreat.start_date.year,
            'startDate': retreat.start_date.isoformat(),
            'endDate': retreat.end_date.isoformat(),
            'sessions': sessions_data,
            'retreat_group': {
                'id': str(retreat_group.id) if retreat_group else '',
                'name': retreat_group.name if retreat_group else ''
            }
        }
        
        logger.info(f"Retrieved retreat details for retreat {retreat_id} for user {user.id}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving retreat details: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve retreat details'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_details(request, session_id):
    """
    Get detailed information about a specific session including all tracks
    """
    try:
        user = request.user
        
        # Get session with user access check (through retreat participation)
        session = get_object_or_404(
            Session.objects.filter(
                retreat__participants__user=user,
                retreat__participants__status='attended'
            ).prefetch_related(
                'tracks',
                'retreat__groups'
            ),
            id=session_id
        )
        
        # Build tracks data
        tracks_data = []
        for track in session.tracks.all().order_by('track_number'):
            # Use a default duration if none is set (approximately 30 minutes)
            duration_seconds = track.duration_minutes * 60 if track.duration_minutes > 0 else 1800
            tracks_data.append({
                'id': str(track.id),
                'title': track.title,
                'duration': duration_seconds,  # Convert to seconds
                'audioUrl': '',  # Will be provided via presigned URLs
                'transcriptUrl': '',  # Will be provided via presigned URLs
                'order': track.track_number
            })
        
        response_data = {
            'id': str(session.id),
            'name': session.title,
            'type': session.get_time_period_display().lower(),
            'date': session.session_date.isoformat(),
            'tracks': tracks_data,
            'gathering': {
                'id': str(session.retreat.id),
                'name': session.retreat.name
            }
        }
        
        logger.info(f"Retrieved session details for session {session_id} for user {user.id}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving session details: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve session details'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def track_presigned_url(request, track_id):
    """
    Get presigned URL for audio track access
    """
    logger.info(f"🔍 [DEBUG] Starting presigned URL request for track {track_id}")
    logger.info(f"🔍 [DEBUG] User: {request.user.email}, User ID: {request.user.id}")
    
    try:
        user = request.user
        
        # Get track with user access check
        track = get_object_or_404(
            Track.objects.filter(
                session__retreat__participants__user=user,
                session__retreat__participants__status='attended'
            ),
            id=track_id
        )
        
        logger.info(f"🔍 [DEBUG] Track found: {track.title}")
        logger.info(f"🔍 [DEBUG] Track audio_file.name: {track.audio_file.name}")
        logger.info(f"🔍 [DEBUG] Track audio_file.url: {track.audio_file.url}")
        
        if not track.audio_file:
            logger.warning(f"🔍 [DEBUG] No audio file for track {track_id}")
            return Response(
                {'error': 'Audio file not available'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate actual presigned URL for S3 access
        try:
            import boto3
            from django.conf import settings
            
            logger.info(f"🔍 [DEBUG] S3 Configuration:")
            logger.info(f"🔍 [DEBUG] - Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
            logger.info(f"🔍 [DEBUG] - Region: {settings.AWS_S3_REGION_NAME}")
            logger.info(f"🔍 [DEBUG] - Key ID: {settings.AWS_ACCESS_KEY_ID[:8]}...{settings.AWS_ACCESS_KEY_ID[-4:]}")
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            
            logger.info(f"🔍 [DEBUG] S3 client created successfully")
            
            # Generate presigned URL (valid for 1 hour)
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': track.audio_file.name  # S3 key from FileField
                },
                ExpiresIn=3600  # 1 hour expiration
            )
            
            logger.info(f"🔍 [DEBUG] Generated presigned URL: {presigned_url[:100]}...")
            logger.info(f"🔍 [DEBUG] URL contains AWS signature: {'Signature=' in presigned_url}")
            logger.info(f"🔍 [DEBUG] URL contains expiration: {'Expires=' in presigned_url}")
            
            # Test the presigned URL immediately
            logger.info(f"🔍 [DEBUG] Testing presigned URL...")
            try:
                import requests
                test_response = requests.head(presigned_url, timeout=10)
                logger.info(f"🔍 [DEBUG] Test response status: {test_response.status_code}")
                logger.info(f"🔍 [DEBUG] Test response headers: {dict(test_response.headers)}")
                
                if test_response.status_code == 200:
                    logger.info(f"✅ [DEBUG] Presigned URL test PASSED")
                else:
                    logger.error(f"❌ [DEBUG] Presigned URL test FAILED: {test_response.status_code}")
                    
            except Exception as test_error:
                logger.error(f"❌ [DEBUG] Presigned URL test error: {test_error}")
            
            return Response({
                'presigned_url': presigned_url
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"❌ [DEBUG] Error generating presigned URL for track {track_id}: {str(e)}")
            logger.error(f"❌ [DEBUG] Exception type: {type(e).__name__}")
            return Response(
                {'error': 'Failed to generate audio URL'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Exception as e:
        logger.error(f"❌ [DEBUG] Error retrieving track presigned URL: {str(e)}")
        logger.error(f"❌ [DEBUG] Exception type: {type(e).__name__}")
        return Response(
            {'error': 'Failed to get audio URL'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ==============================================================================
# Lambda Integration Functions
# ==============================================================================

def trigger_lambda_zip_generation(download_request):
    """Trigger AWS Lambda function for ZIP generation"""
    import boto3
    import json
    from django.conf import settings
    
    try:
        # Get all audio files for this retreat
        audio_files = []
        for session in download_request.retreat.sessions.all():
            for track in session.tracks.filter(audio_file__isnull=False):
                audio_files.append(track.audio_file.name)
        
        if not audio_files:
            download_request.mark_as_failed("No audio files found")
            return False
        
        # Prepare Lambda payload
        webhook_url = f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/api/retreats/download-webhook/"
        
        payload = {
            'request_id': download_request.id,
            'retreat_name': download_request.retreat.name,
            'audio_files': audio_files,
            'webhook_url': webhook_url
        }
        
        logger.info(f"Triggering Lambda with {len(audio_files)} audio files for request {download_request.id}")
        logger.info(f"Lambda payload: {json.dumps(payload)}")
        
        # Invoke Lambda function
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        response = lambda_client.invoke(
            FunctionName=getattr(settings, 'AWS_LAMBDA_FUNCTION_NAME', 'padmakara-zip-generator'),
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(payload)
        )
        
        if response['StatusCode'] == 202:
            logger.info(f"Lambda function triggered successfully for request {download_request.id}")
            return True
        else:
            logger.error(f"Lambda invocation failed: {response}")
            download_request.mark_as_failed(f"Lambda invocation failed: status {response['StatusCode']}")
            return False
        
    except Exception as e:
        logger.error(f"Failed to trigger Lambda: {str(e)}")
        download_request.mark_as_failed(f"Lambda trigger failed: {str(e)}")
        return False


# ==============================================================================
# Download ZIP Endpoints
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_retreat_download(request, retreat_id):
    """
    Create a new download request for retreat ZIP file
    """
    try:
        user = request.user
        
        # Get retreat with user access check
        retreat = get_object_or_404(
            Retreat.objects.filter(
                participants__user=user,
                participants__status='attended'
            ).prefetch_related('sessions__tracks'),
            id=retreat_id
        )
        
        # Check if user already has a pending/processing/ready request for this retreat
        existing_request = DownloadRequest.objects.filter(
            user=user,
            retreat=retreat,
            status__in=['pending', 'processing', 'ready']
        ).first()
        
        if existing_request:
            # If existing request is expired, allow new request
            if existing_request.is_expired:
                existing_request.status = 'expired'
                existing_request.save()
            else:
                # Return existing request details
                return Response({
                    'request_id': existing_request.id,
                    'status': existing_request.status,
                    'created_at': existing_request.created_at.isoformat(),
                    'expires_at': existing_request.expires_at.isoformat() if existing_request.expires_at else None,
                    'message': 'Download request already exists'
                }, status=status.HTTP_200_OK)
        
        # Clean up any stuck processing requests (older than 30 minutes)
        stuck_requests = DownloadRequest.objects.filter(
            retreat=retreat,
            status='processing',
            processing_started_at__lt=timezone.now() - timezone.timedelta(minutes=30)
        )
        
        for stuck_request in stuck_requests:
            stuck_request.mark_as_failed("Processing abandoned after 30 minutes")
            logger.info(f"Cleaned up stuck request {stuck_request.id}")
        
        # Check if there's already a ZIP being generated for this retreat (global lock)
        active_generation = DownloadRequest.objects.filter(
            retreat=retreat,
            status__in=['pending', 'processing']
        ).first()
        
        if active_generation:
            # Join the existing generation - create a request that waits for the same ZIP
            new_request = DownloadRequest.objects.create(
                user=user,
                retreat=retreat,
                status='processing',  # Will be updated when shared ZIP completes
                processing_started_at=timezone.now()
            )
            
            logger.info(f"Joining existing ZIP generation for retreat {retreat_id}, request {new_request.id} waiting for {active_generation.id}")
            
            return Response({
                'request_id': new_request.id,
                'status': 'processing',
                'message': f'ZIP generation already in progress. Your request has been queued.',
                'created_at': new_request.created_at.isoformat(),
                'shared_with_request': active_generation.id
            }, status=status.HTTP_201_CREATED)

        # Check for existing shared ZIP that can be reused (but not currently being generated)
        existing_shared_zip = DownloadRequest.find_existing_shared_zip(retreat)
        
        if existing_shared_zip:
            # Reuse existing shared ZIP
            download_request = DownloadRequest.create_shared_zip_request(user, retreat, existing_shared_zip)
            logger.info(f"Created shared download request {download_request.id} using existing ZIP for retreat {retreat_id}")
            
            return Response({
                'request_id': download_request.id,
                'status': download_request.status,
                'created_at': download_request.created_at.isoformat(),
                'expires_at': download_request.expires_at.isoformat() if download_request.expires_at else None,
                'message': 'Download ready (using existing ZIP)',
                'shared': True,
                'download_count': existing_shared_zip.download_count + 1
            }, status=status.HTTP_201_CREATED)
        else:
            # Create new shared ZIP request - this becomes the primary request that triggers Lambda
            download_request = DownloadRequest.create_shared_zip_request(user, retreat)
            
            # Trigger Lambda function for ZIP generation
            if not trigger_lambda_zip_generation(download_request):
                download_request.mark_as_failed("Failed to start Lambda function")
                return Response(
                    {'error': 'Failed to start ZIP generation'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            logger.info(f"Created new shared ZIP request {download_request.id} for retreat {retreat_id} by user {user.id} and triggered Lambda")
            
            return Response({
                'request_id': download_request.id,
                'status': download_request.status,
                'created_at': download_request.created_at.isoformat(),
                'expires_at': download_request.expires_at.isoformat() if download_request.expires_at else None,
                'message': 'ZIP generation started',
                'shared': True,
                'estimated_time': '30-60 seconds'
            }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating download request: {str(e)}")
        return Response(
            {'error': 'Failed to create download request'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_request_status(request, request_id):
    """
    Get status of a download request
    """
    try:
        user = request.user
        
        # Get download request with user ownership check
        download_request = get_object_or_404(
            DownloadRequest.objects.select_related('retreat'),
            id=request_id,
            user=user
        )
        
        # Check if request has expired or timed out
        if download_request.is_expired and download_request.status != 'expired':
            download_request.status = 'expired'
            download_request.save()
        
        # Check if processing has been running too long (30 minutes max)
        if download_request.status == 'processing' and download_request.processing_started_at:
            processing_duration = timezone.now() - download_request.processing_started_at
            if processing_duration.total_seconds() > 1800:  # 30 minutes
                download_request.mark_as_failed("Processing timed out after 30 minutes")
                logger.warning(f"Download request {download_request.id} timed out after {processing_duration}")
        
        response_data = {
            'request_id': download_request.id,
            'status': download_request.status,
            'retreat': {
                'id': download_request.retreat.id,
                'name': download_request.retreat.name
            },
            'created_at': download_request.created_at.isoformat(),
            'updated_at': download_request.updated_at.isoformat(),
            'expires_at': download_request.expires_at.isoformat() if download_request.expires_at else None,
            'processing_started_at': download_request.processing_started_at.isoformat() if download_request.processing_started_at else None,
            'processing_completed_at': download_request.processing_completed_at.isoformat() if download_request.processing_completed_at else None,
        }
        
        # Add download information if ready
        if download_request.status == 'ready':
            response_data.update({
                'download_url': request.build_absolute_uri(
                    f'/retreats/download-requests/{download_request.id}/download/'
                ),
                'file_size': download_request.file_size,
                'file_size_mb': download_request.file_size_mb,
                'time_until_expiry': download_request.time_until_expiry.total_seconds() if download_request.time_until_expiry else None
            })
        
        # Add progress information if processing
        if download_request.status == 'processing':
            # Add fields if they exist in the model
            progress_fields = {}
            if hasattr(download_request, 'progress_percent') and download_request.progress_percent is not None:
                progress_fields['progress_percent'] = download_request.progress_percent
            if hasattr(download_request, 'processed_files') and download_request.processed_files is not None:
                progress_fields['processed_files'] = download_request.processed_files
            if hasattr(download_request, 'total_files') and download_request.total_files is not None:
                progress_fields['total_files'] = download_request.total_files
            
            if progress_fields:
                response_data.update(progress_fields)
        
        # Add error information if failed
        if download_request.status == 'failed':
            response_data.update({
                'error_message': download_request.error_message,
                'retry_count': download_request.retry_count,
                'can_retry': download_request.can_retry()
            })
        
        # Add performance metrics if available
        if download_request.status == 'ready':
            perf_fields = {}
            if hasattr(download_request, 'processing_time_seconds') and download_request.processing_time_seconds:
                perf_fields['processing_time_seconds'] = download_request.processing_time_seconds
            if hasattr(download_request, 'compression_ratio') and download_request.compression_ratio is not None:
                perf_fields['compression_ratio'] = download_request.compression_ratio
            
            if perf_fields:
                response_data.update(perf_fields)
        
        # Add processing duration if completed
        if download_request.processing_duration:
            response_data['processing_duration_seconds'] = download_request.processing_duration
        
        # Add enhanced progress information if available
        if hasattr(download_request, 'progress_percent'):
            response_data['progress_percent'] = download_request.progress_percent
        
        if hasattr(download_request, 'processed_files') and download_request.processed_files > 0:
            response_data['processed_files'] = download_request.processed_files
        
        if hasattr(download_request, 'total_files') and download_request.total_files:
            response_data['total_files'] = download_request.total_files
        
        # Add performance metrics if completed
        if download_request.status == 'ready':
            if hasattr(download_request, 'original_size') and download_request.original_size:
                response_data['original_size'] = download_request.original_size
                response_data['original_size_mb'] = round(download_request.original_size / (1024 * 1024), 2)
            
            if hasattr(download_request, 'compression_ratio') and download_request.compression_ratio is not None:
                response_data['compression_ratio'] = download_request.compression_ratio
            
            if hasattr(download_request, 'processing_time_seconds') and download_request.processing_time_seconds:
                response_data['processing_time_seconds'] = download_request.processing_time_seconds
            
            if hasattr(download_request, 'performance_metrics') and download_request.performance_metrics:
                response_data['performance_metrics'] = download_request.performance_metrics
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving download request status: {str(e)}")
        return Response(
            {'error': 'Failed to retrieve download request status'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_file(request, request_id):
    """
    Download the actual ZIP file
    """
    try:
        user = request.user
        
        # Get download request with user ownership check
        download_request = get_object_or_404(
            DownloadRequest.objects.select_related('retreat'),
            id=request_id,
            user=user
        )
        
        # Check if request is ready for download
        if download_request.status != 'ready':
            return Response(
                {'error': f'Download not ready. Status: {download_request.status}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if request has expired
        if download_request.is_expired:
            download_request.status = 'expired'
            download_request.save()
            return Response(
                {'error': 'Download has expired'}, 
                status=status.HTTP_410_GONE
            )
        
        # Validate S3 file existence before serving download URL
        if download_request.s3_key:
            logger.info(f"Validating S3 file existence for request {request_id}: {download_request.s3_key}")
            
            s3_validation = check_s3_file_exists(download_request.s3_key)
            
            if not s3_validation['exists'] or not s3_validation['accessible']:
                # S3 file is missing or inaccessible - trigger auto-recovery
                logger.warning(f"S3 file validation failed for request {request_id}: {s3_validation['error']}")
                
                # Mark current request as expired
                download_request.status = 'expired'
                download_request.error_message = f"S3 file not accessible: {s3_validation['error']}"
                download_request.save()
                
                # Check if we can auto-recover by creating a new download request
                try:
                    logger.info(f"Auto-recovery: Creating fresh download request for retreat {download_request.retreat.id}")
                    
                    # Create new download request for same retreat
                    new_download_request = DownloadRequest.create_shared_zip_request(user, download_request.retreat)
                    
                    # Trigger Lambda function for fresh ZIP generation
                    if trigger_lambda_zip_generation(new_download_request):
                        logger.info(f"Auto-recovery successful: New request {new_download_request.id} created and Lambda triggered")
                        
                        # Return response indicating file is being regenerated
                        return Response({
                            'success': False,
                            'regenerating': True,
                            'new_request_id': new_download_request.id,
                            'message': 'File was missing and is being regenerated. Please check again in 30-60 seconds.',
                            'original_request_id': request_id,
                            'estimated_time': '30-60 seconds'
                        }, status=status.HTTP_202_ACCEPTED)
                    else:
                        # Lambda trigger failed
                        new_download_request.mark_as_failed("Failed to trigger ZIP generation")
                        logger.error(f"Auto-recovery failed: Could not trigger Lambda for request {new_download_request.id}")
                        
                        return Response({
                            'error': 'File missing and regeneration failed. Please try downloading again later.',
                            'regeneration_failed': True,
                            'original_error': s3_validation['error']
                        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                        
                except Exception as recovery_error:
                    logger.error(f"Auto-recovery error for request {request_id}: {str(recovery_error)}")
                    return Response({
                        'error': 'File missing and auto-recovery failed. Please try downloading again.',
                        'recovery_error': str(recovery_error),
                        'original_error': s3_validation['error']
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            else:
                # S3 file exists and is accessible
                logger.info(f"S3 file validation successful for request {request_id} ({s3_validation['file_size']} bytes)")
        
        # Use the presigned URL provided by Lambda function (already stored in download_url field)
        if not download_request.download_url:
            logger.error(f"No download URL available for request {request_id}")
            return Response(
                {'error': 'Download URL not available. Please try generating a new ZIP file.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        logger.info(f"Returning Lambda-provided download URL for request {request_id} by user {user.id}")
        
        # Record download and extend lifecycle
        download_request.record_download()
        
        # Return the presigned URL that Lambda already generated for the temp downloads bucket
        return Response({
            'success': True,
            'download_url': download_request.download_url,  # Use Lambda-provided URL
            'file_size': download_request.file_size,
            'file_name': f"{download_request.retreat.name}.zip",
            'expires_in_seconds': 172800  # 48 hours (Lambda URL expiration)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error processing download request: {str(e)}")
        return Response(
            {'error': 'Failed to process download request'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def extend_zip_lifecycle(request, request_id):
    """
    Extend the lifecycle of a ZIP file
    """
    try:
        user = request.user
        
        # Get download request with user ownership check
        download_request = get_object_or_404(
            DownloadRequest.objects.select_related('retreat'),
            id=request_id,
            user=user
        )
        
        # Check if request is ready and not expired
        if download_request.status != 'ready':
            return Response(
                {'error': f'Cannot extend lifecycle. Status: {download_request.status}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if download_request.is_expired:
            return Response(
                {'error': 'Cannot extend expired ZIP'}, 
                status=status.HTTP_410_GONE
            )
        
        # Get extension days from request (default: 2 days)
        extension_days = request.data.get('days', 2)
        if not isinstance(extension_days, int) or extension_days < 1 or extension_days > 7:
            return Response(
                {'error': 'Extension days must be between 1 and 7'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store old expiry for comparison
        old_expiry = download_request.expires_at
        
        # Extend lifecycle
        download_request.extend_lifecycle(days=extension_days)
        
        # Calculate actual extension granted
        if old_expiry:
            actual_extension = (download_request.expires_at - old_expiry).days
        else:
            actual_extension = extension_days
        
        logger.info(f"Extended lifecycle for request {request_id} by {actual_extension} days")
        
        return Response({
            'success': True,
            'request_id': download_request.id,
            'old_expires_at': old_expiry.isoformat() if old_expiry else None,
            'new_expires_at': download_request.expires_at.isoformat(),
            'extension_days': actual_extension,
            'time_until_expiry_hours': download_request.time_until_expiry.total_seconds() / 3600 if download_request.time_until_expiry else None
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error extending ZIP lifecycle: {str(e)}")
        return Response(
            {'error': 'Failed to extend ZIP lifecycle'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@require_http_methods(["POST"])
def download_webhook(request):
    """
    Webhook endpoint for AWS Lambda to notify about download completion
    """
    try:
        # Parse webhook payload
        payload = json.loads(request.body)
        
        request_id = payload.get('request_id')
        status_update = payload.get('status')
        
        if not request_id or not status_update:
            return JsonResponse(
                {'error': 'Missing request_id or status in payload'}, 
                status=400
            )
        
        # Get download request
        try:
            download_request = DownloadRequest.objects.get(id=request_id)
        except DownloadRequest.DoesNotExist:
            return JsonResponse(
                {'error': 'Download request not found'}, 
                status=404
            )
        
        # Update request status based on webhook
        if status_update == 'ready':
            download_url = payload.get('download_url')
            s3_key = payload.get('s3_key')
            file_size = payload.get('file_size')
            lambda_request_id = payload.get('lambda_request_id')
            
            # Extract performance metrics
            original_size = payload.get('original_size')
            compression_ratio = payload.get('compression_ratio')
            processing_time = payload.get('processing_time_seconds')
            files_processed = payload.get('files_processed')
            performance_data = payload.get('performance')
            
            if not all([download_url, s3_key, file_size]):
                return JsonResponse(
                    {'error': 'Missing required fields for ready status'}, 
                    status=400
                )
            
            # Update shared ZIP information (this will update all waiting requests)
            download_request.update_shared_zip_info(s3_key, download_url, file_size)
            download_request.mark_as_ready(download_url, s3_key, file_size)
            
            # Update all waiting requests for the same retreat
            waiting_requests = DownloadRequest.objects.filter(
                retreat=download_request.retreat,
                status='processing'
            ).exclude(id=download_request.id)
            
            for waiting_request in waiting_requests:
                waiting_request.mark_as_ready(download_url, s3_key, file_size)
                logger.info(f"Updated waiting request {waiting_request.id} with shared ZIP for retreat {download_request.retreat.id}")
            
            # Store performance metrics if fields exist
            update_fields = ['lambda_request_id']
            try:
                if lambda_request_id:
                    download_request.lambda_request_id = lambda_request_id
                
                if hasattr(download_request, 'original_size') and original_size:
                    download_request.original_size = original_size
                    update_fields.append('original_size')
                
                if hasattr(download_request, 'compression_ratio') and compression_ratio is not None:
                    download_request.compression_ratio = compression_ratio
                    update_fields.append('compression_ratio')
                
                if hasattr(download_request, 'processing_time_seconds') and processing_time:
                    download_request.processing_time_seconds = processing_time
                    update_fields.append('processing_time_seconds')
                
                if hasattr(download_request, 'processed_files') and files_processed:
                    download_request.processed_files = files_processed
                    update_fields.append('processed_files')
                
                if hasattr(download_request, 'progress_percent'):
                    download_request.progress_percent = 100  # Complete
                    update_fields.append('progress_percent')
                
                if hasattr(download_request, 'performance_metrics') and performance_data:
                    download_request.performance_metrics = performance_data
                    update_fields.append('performance_metrics')
                
                download_request.save(update_fields=update_fields)
            except Exception as metrics_error:
                logger.warning(f"Failed to store performance metrics: {str(metrics_error)}")
                # Continue with basic save
                if lambda_request_id:
                    download_request.lambda_request_id = lambda_request_id
                    download_request.save(update_fields=['lambda_request_id'])
            
            logger.info(f"Download request {request_id} marked as ready and shared ZIP updated - Performance: {processing_time}s, {compression_ratio}% compression")
            
        elif status_update == 'failed':
            error_message = payload.get('error_message', 'Unknown error')
            lambda_request_id = payload.get('lambda_request_id')
            
            # Mark primary request as failed
            download_request.mark_as_failed(error_message)
            if lambda_request_id:
                download_request.lambda_request_id = lambda_request_id
                download_request.save(update_fields=['lambda_request_id'])
            
            # Mark all waiting requests for the same retreat as failed
            waiting_requests = DownloadRequest.objects.filter(
                retreat=download_request.retreat,
                status__in=['pending', 'processing']
            ).exclude(id=download_request.id)
            
            for request in waiting_requests:
                request.mark_as_failed(f"Shared ZIP generation failed: {error_message}")
                logger.info(f"Marked waiting request {request.id} as failed")
            
            logger.error(
                f"ZIP generation failed for request {request_id}: {error_message}. "
                f"Marked {len(waiting_requests) + 1} requests as failed."
            )
            
        elif status_update == 'processing':
            lambda_request_id = payload.get('lambda_request_id')
            
            # Extract enhanced progress data
            progress_percent = payload.get('progress_percent', 0)
            processed_files = payload.get('processed_files', 0)
            total_files = payload.get('total_files')
            total_size_mb = payload.get('total_size_mb', 0)
            
            download_request.mark_as_processing(lambda_request_id)
            
            # Update progress fields if they exist
            try:
                if hasattr(download_request, 'progress_percent'):
                    download_request.progress_percent = progress_percent
                if hasattr(download_request, 'processed_files'):
                    download_request.processed_files = processed_files
                if hasattr(download_request, 'total_files') and total_files:
                    download_request.total_files = total_files
                
                download_request.save(update_fields=[
                    field for field in ['progress_percent', 'processed_files', 'total_files'] 
                    if hasattr(download_request, field)
                ])
            except Exception as progress_error:
                logger.warning(f"Failed to update progress fields: {str(progress_error)}")
            
            logger.info(f"Download request {request_id} marked as processing - Progress: {progress_percent}% ({processed_files}/{total_files or '?'} files)")
            
        else:
            return JsonResponse(
                {'error': f'Invalid status: {status_update}'}, 
                status=400
            )
        
        return JsonResponse({'success': True})
        
    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid JSON payload'}, 
            status=400
        )
    except Exception as e:
        logger.error(f"Error processing download webhook: {str(e)}")
        return JsonResponse(
            {'error': 'Internal server error'}, 
            status=500
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def debug_download_requests(request):
    """Debug endpoint to see all download requests for debugging"""
    if not request.user.is_staff:
        return Response({'error': 'Admin access required'}, status=403)
    
    requests = DownloadRequest.objects.all().order_by('-created_at')[:50]
    debug_data = []
    
    for req in requests:
        age_minutes = (timezone.now() - req.created_at).total_seconds() / 60
        processing_time = None
        if req.processing_started_at:
            processing_time = (timezone.now() - req.processing_started_at).total_seconds() / 60
        
        debug_data.append({
            'id': req.id,
            'user': req.user.username,
            'retreat': req.retreat.name,
            'status': req.status,
            'created_ago_minutes': round(age_minutes, 1),
            'processing_time_minutes': round(processing_time, 1) if processing_time else None,
            'error_message': req.error_message if req.status == 'failed' else None,
            'shared_zip_key': req.shared_zip_key,
            'lambda_request_id': getattr(req, 'lambda_request_id', None)
        })
    
    return Response({
        'total_requests': len(debug_data),
        'active_processing': len([r for r in debug_data if r['status'] == 'processing']),
        'requests': debug_data
    })