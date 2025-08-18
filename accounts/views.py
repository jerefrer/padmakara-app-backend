from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
import logging

from .models import MagicLinkToken, DeviceActivation, UserApprovalRequest
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
        
        # Send magic link email
        magic_link = f"{settings.FRONTEND_URL}/activate/{magic_token.token}"
        
        send_magic_link_email(user, magic_link, device_name or device_type or 'your device')
        
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


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def activate_device(request, token):
    """
    Step 3: Activate device using magic link token
    """
    try:
        magic_token = get_object_or_404(MagicLinkToken, token=token)
        
        if not magic_token.is_valid:
            return Response({
                'error': 'Token is invalid or expired',
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
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(magic_token.user)
        
        return Response({
            'status': 'device_activated',
            'message': 'Device successfully activated',
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'id': magic_token.user.id,
                'email': magic_token.user.email,
                'name': magic_token.user.get_full_name() or magic_token.user.email,
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
        return Response({'error': 'An error occurred during activation'}, 
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


def send_magic_link_email(user, magic_link, device_name):
    """Send magic link email to user"""
    try:
        subject = 'Activate your Padmakara app'
        
        html_message = render_to_string('emails/magic_link.html', {
            'user': user,
            'magic_link': magic_link,
            'device_name': device_name,
            'site_name': settings.SITE_NAME,
            'logo_base64': LOGO_BASE64
        })
        
        plain_message = render_to_string('emails/magic_link.txt', {
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