from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.utils import timezone
import time
from django.contrib.auth import get_user_model
import logging

from .models import MagicLinkToken, DeviceActivation, UserApprovalRequest, AutoActivationToken
from .serializers import (
    EmailRequestSerializer, 
    UserApprovalRequestSerializer, 
    MagicLinkActivationSerializer,
    DeviceActivationSerializer
)
from padmakara.assets import LOGO_BASE64

User = get_user_model()
logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_magic_link(request):
    """
    Step 1: User enters email to request magic link
    Returns different responses based on user status
    """
    serializer = EmailRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': 'Invalid email address'}, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    device_fingerprint = request.data.get('device_fingerprint', '')
    device_name = request.data.get('device_name', '')
    device_type = request.data.get('device_type', '')
    language = request.data.get('language', 'en')  # Default to English if not provided
    
    try:
        # Check if user exists and is active
        user = User.objects.get(email=email, is_active=True)
        
        # Check if device is already activated
        existing_activation = DeviceActivation.objects.filter(
            user=user,
            device_fingerprint=device_fingerprint,
            is_active=True
        ).first()
        
        if existing_activation:
            # Device already activated, generate tokens directly
            refresh = RefreshToken.for_user(user)
            return Response({
                'status': 'already_activated',
                'message': 'This device is already activated',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.get_full_name() or user.email,
                    'dharma_name': user.dharma_name
                }
            })
        
        # Create magic link token
        magic_token = MagicLinkToken.objects.create(
            user=user,
            email=email,
            device_fingerprint=device_fingerprint,
            device_name=device_name,
            device_type=device_type,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Send magic link email - now points to Django backend for HTML activation
        magic_link = f"{settings.BACKEND_URL}/api/auth/activate/{magic_token.token}/?lang={language}"
        
        send_magic_link_email(user, magic_link, device_name or device_type or 'your device', language)
        
        return Response({
            'status': 'magic_link_sent',
            'message': 'Please check your email for the activation link',
            'expires_in': 3600  # 1 hour
        })
        
    except User.DoesNotExist:
        # User doesn't exist, need approval
        return Response({
            'status': 'approval_required',
            'message': 'Email not found. Please provide additional information for approval.',
            'email': email
        })
    
    except Exception as e:
        logger.error(f"Error in request_magic_link: {e}")
        return Response({'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def request_user_approval(request):
    """
    Step 2b: User requests approval from admin
    """
    serializer = UserApprovalRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    language = request.data.get('language', 'en')  # Default to English if not provided
    
    # Check if there's already a pending request for this email
    existing_request = UserApprovalRequest.objects.filter(
        email=data['email'],
        status='pending'
    ).first()
    
    if existing_request:
        return Response({
            'status': 'already_pending',
            'message': 'Your approval request is already being reviewed. We will contact you by email soon.'
        })
    
    # Create approval request
    approval_request = UserApprovalRequest.objects.create(
        email=data['email'],
        first_name=data['first_name'],
        last_name=data['last_name'],
        message=data.get('message', ''),
        device_fingerprint=data.get('device_fingerprint', ''),
        device_name=data.get('device_name', ''),
        device_type=data.get('device_type', ''),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Send notification email to admins
    send_admin_approval_notification(approval_request)
    
    return Response({
        'status': 'approval_requested',
        'message': 'Thank you for your request. Our team will review it and get back to you by email within 24 hours.'
    })


@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])
def activate_device(request, token):
    """
    Step 3: Activate device using magic link token
    Supports both HTML (browser) and JSON (API) responses
    """
    try:
        magic_token = get_object_or_404(MagicLinkToken, token=token)
        
        # Check if token is valid
        if not magic_token.is_valid:
            error_message = 'Token is invalid or expired'
            
            if request_wants_html(request):
                # Check for language parameter from URL first, then detect from browser
                url_language = request.GET.get('lang', '')
                if url_language in ['en', 'pt']:
                    detected_language = url_language
                else:
                    detected_language = detect_browser_language(request)
                
                return render(request, 'activation/activate.html', {
                    'status': 'error',
                    'error_message': error_message,
                    'frontend_url': settings.FRONTEND_URL,
                    'detected_language': detected_language,
                    'timestamp': int(time.time())
                })
            else:
                return Response({
                    'error': error_message,
                    'status': 'token_invalid'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark token as used
        magic_token.use_token()
        
        # Create or update device activation
        device_activation, created = DeviceActivation.objects.get_or_create(
            device_fingerprint=magic_token.device_fingerprint,
            defaults={
                'user': magic_token.user,
                'device_name': magic_token.device_name,
                'device_type': magic_token.device_type,
                'ip_address': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'is_active': True
            }
        )
        
        if not created:
            # Reactivate existing device
            device_activation.user = magic_token.user
            device_activation.is_active = True
            device_activation.save()
        
        # Generate auto-activation token for seamless web app access
        auto_token = AutoActivationToken.objects.create(
            user=magic_token.user,
            original_device_fingerprint=magic_token.device_fingerprint,
            original_ip=get_client_ip(request),
            original_user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Prepare response data
        user_name = magic_token.user.get_full_name() or magic_token.user.email
        device_name = device_activation.device_name or 'This Device'
        
        if request_wants_html(request):
            # Return HTML page for browser requests
            # Check for language parameter from URL first, then detect from browser
            url_language = request.GET.get('lang', '')
            if url_language in ['en', 'pt']:
                detected_language = url_language
            else:
                detected_language = detect_browser_language(request)
            
            return render(request, 'activation/activate.html', {
                'status': 'success',
                'user_name': user_name,
                'device_name': device_name,
                'frontend_url': settings.FRONTEND_URL,
                'detected_language': detected_language,
                'timestamp': int(time.time()),
                'auto_activation_token': auto_token.token
            })
        else:
            # Return JSON for API requests
            refresh = RefreshToken.for_user(magic_token.user)
            return Response({
                'status': 'device_activated',
                'message': 'Device successfully activated',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'id': magic_token.user.id,
                    'email': magic_token.user.email,
                    'name': user_name,
                    'dharma_name': magic_token.user.dharma_name
                },
                'device_activation': {
                    'id': str(device_activation.id),
                    'device_name': device_activation.device_name,
                    'device_type': device_activation.device_type,
                    'activated_at': device_activation.activated_at
                }
            })
        
    except Exception as e:
        logger.error(f"Error in activate_device: {e}")
        error_message = 'An error occurred during activation'
        
        if request_wants_html(request):
            detected_language = detect_browser_language(request)
            return render(request, 'activation/activate.html', {
                'status': 'error',
                'error_message': error_message,
                'frontend_url': settings.FRONTEND_URL,
                'detected_language': detected_language,
                'timestamp': int(time.time())
            })
        else:
            return Response({'error': error_message}, 
                           status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def deactivate_device(request):
    """
    Deactivate a specific device
    """
    device_fingerprint = request.data.get('device_fingerprint')
    if not device_fingerprint:
        return Response({'error': 'Device fingerprint required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        device_activation = DeviceActivation.objects.get(
            device_fingerprint=device_fingerprint,
            user=request.user,
            is_active=True
        )
        device_activation.deactivate()
        
        return Response({
            'status': 'deactivated',
            'message': 'Device deactivated successfully'
        })
        
    except DeviceActivation.DoesNotExist:
        return Response({'error': 'Device not found or already deactivated'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_user_devices(request):
    """
    List all activated devices for the user
    """
    devices = DeviceActivation.objects.filter(
        user=request.user,
        is_active=True
    ).order_by('-last_used')
    
    return Response({
        'devices': DeviceActivationSerializer(devices, many=True).data
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def discover_device_activation(request):
    """
    Discover if a device has been activated (unauthenticated endpoint for polling)
    Used by mobile app to detect when magic link was clicked from another device
    """
    device_fingerprint = request.data.get('device_fingerprint')
    if not device_fingerprint:
        return Response({'error': 'Device fingerprint required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Check if device exists and is activated
        device_activation = DeviceActivation.objects.filter(
            device_fingerprint=device_fingerprint,
            is_active=True
        ).first()
        
        if device_activation:
            # Device is activated - generate fresh tokens for this session
            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(device_activation.user)
            
            # Update last used time
            device_activation.last_used = timezone.now()
            device_activation.save(update_fields=['last_used'])
            
            return Response({
                'status': 'activated',
                'message': 'Device is activated',
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'id': device_activation.user.id,
                    'email': device_activation.user.email,
                    'name': device_activation.user.get_full_name() or device_activation.user.email,
                    'dharma_name': device_activation.user.dharma_name
                },
                'device': DeviceActivationSerializer(device_activation).data
            })
        else:
            # Device not activated yet
            return Response({
                'status': 'not_activated',
                'message': 'Device not activated yet'
            })
        
    except Exception as e:
        logger.error(f"Error in discover_device_activation: {e}")
        return Response({'error': 'An error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def request_wants_html(request):
    """
    Determine if the request expects HTML response based on Accept header
    """
    accept_header = request.META.get('HTTP_ACCEPT', '')
    
    # Check if browser Accept header (contains text/html)
    if 'text/html' in accept_header:
        return True
    
    # Check if it's a GET request (magic link clicked in browser)
    if request.method == 'GET':
        return True
        
    # Check User-Agent for common browsers
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    browser_indicators = ['mozilla', 'chrome', 'safari', 'firefox', 'edge']
    if any(indicator in user_agent for indicator in browser_indicators):
        return True
    
    # Default to JSON for API requests
    return False


def detect_browser_language(request):
    """
    Detect user's preferred language from browser headers
    """
    # Get Accept-Language header
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    
    # Parse language preferences (format: "en-US,en;q=0.9,pt;q=0.8")
    languages = []
    for lang_part in accept_language.split(','):
        if ';q=' in lang_part:
            lang, quality = lang_part.strip().split(';q=')
            languages.append((lang.strip(), float(quality)))
        else:
            languages.append((lang_part.strip(), 1.0))
    
    # Sort by quality (preference)
    languages.sort(key=lambda x: x[1], reverse=True)
    
    # Check for supported languages in order of preference
    supported_languages = ['en', 'pt']
    
    for lang_code, _ in languages:
        # Extract main language code (e.g., 'en' from 'en-US')
        main_lang = lang_code.split('-')[0].lower()
        if main_lang in supported_languages:
            return main_lang
    
    # Default to English
    return 'en'


def send_magic_link_email(user, magic_link, device_name, language='en'):
    """Send magic link email to user in the specified language"""
    try:
        # Select subject and templates based on language
        if language == 'pt':
            subject = 'Ative o seu app Padmakara'
            html_template = 'emails/magic_link_pt.html'
            txt_template = 'emails/magic_link_pt.txt'
        else:
            subject = 'Activate your Padmakara app'
            html_template = 'emails/magic_link_en.html'
            txt_template = 'emails/magic_link_en.txt'
        
        html_message = render_to_string(html_template, {
            'user': user,
            'magic_link': magic_link,
            'device_name': device_name,
            'site_name': settings.SITE_NAME,
            'logo_base64': LOGO_BASE64
        })
        
        plain_message = render_to_string(txt_template, {
            'user': user,
            'magic_link': magic_link,
            'device_name': device_name,
            'site_name': settings.SITE_NAME
        })
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Magic link email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send magic link email to {user.email}: {e}")


def send_admin_approval_notification(approval_request):
    """Send approval notification to admins"""
    try:
        admin_emails = User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
        
        if not admin_emails:
            logger.warning("No admin emails found for approval notification")
            return
        
        subject = f'New user approval request: {approval_request.first_name} {approval_request.last_name}'
        
        html_message = render_to_string('emails/admin_approval_request.html', {
            'approval_request': approval_request,
            'admin_url': f"{settings.BACKEND_URL}/admin/accounts/userapprovalrequest/{approval_request.id}/change/"
        })
        
        plain_message = render_to_string('emails/admin_approval_request.txt', {
            'approval_request': approval_request,
            'admin_url': f"{settings.BACKEND_URL}/admin/accounts/userapprovalrequest/{approval_request.id}/change/"
        })
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(admin_emails),
            html_message=html_message,
            fail_silently=False
        )
        
        logger.info(f"Admin approval notification sent for {approval_request.email}")
        
    except Exception as e:
        logger.error(f"Failed to send admin approval notification: {e}")


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def auto_activate_device(request):
    """
    Auto-activate a device using a short-lived auto-activation token
    """
    token_value = request.data.get('token', '')
    device_fingerprint = request.data.get('device_fingerprint', '')
    device_name = request.data.get('device_name', '')
    device_type = request.data.get('device_type', 'web')
    
    if not token_value:
        return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Find the auto-activation token
        auto_token = AutoActivationToken.objects.get(token=token_value)
        
        # Check if token is valid
        if not auto_token.is_valid:
            return Response({
                'error': 'Token is invalid or expired',
                'status': 'token_invalid'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Security check: ensure request comes from same IP
        request_ip = get_client_ip(request)
        if not auto_token.is_ip_match(request_ip):
            logger.warning(f"Auto-activation IP mismatch: original={auto_token.original_ip}, request={request_ip}")
            return Response({
                'error': 'Security validation failed',
                'status': 'security_failed'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Use the token (marks it as used)
        auto_token.use_token(
            ip_address=request_ip,
            device_fingerprint=device_fingerprint,
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Create or update device activation
        device_activation, created = DeviceActivation.objects.get_or_create(
            device_fingerprint=device_fingerprint,
            defaults={
                'user': auto_token.user,
                'device_name': device_name,
                'device_type': device_type,
                'ip_address': request_ip,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'is_active': True
            }
        )
        
        if not created:
            # Reactivate existing device for this user
            device_activation.user = auto_token.user
            device_activation.is_active = True
            device_activation.save()
        
        # Generate tokens for the user
        refresh = RefreshToken.for_user(auto_token.user)
        
        logger.info(f"Auto-activation successful for {auto_token.user.email} on {device_name}")
        
        return Response({
            'status': 'device_activated',
            'message': 'Device automatically activated',
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'id': auto_token.user.id,
                'email': auto_token.user.email,
                'name': auto_token.user.get_full_name() or auto_token.user.email,
                'dharma_name': auto_token.user.dharma_name
            },
            'device_activation': {
                'id': str(device_activation.id),
                'device_name': device_activation.device_name,
                'device_type': device_activation.device_type,
                'activated_at': device_activation.activated_at.isoformat(),
            }
        })
        
    except AutoActivationToken.DoesNotExist:
        return Response({
            'error': 'Token not found',
            'status': 'token_not_found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        logger.error(f"Auto-activation error: {e}")
        return Response({
            'error': 'Internal server error',
            'status': 'server_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)