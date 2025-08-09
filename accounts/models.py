from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid
import secrets


class UserManager(BaseUserManager):
    """
    Custom user manager for email-based authentication
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a User with the given email and password
        """
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model for Padmakara Buddhist retreat app
    Uses email as the primary authentication field instead of username
    """
    
    # Remove username field and use email for authentication
    username = None
    email = models.EmailField(_('Email Address'), unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Remove username from required fields
    
    objects = UserManager()
    
    LANGUAGE_CHOICES = [
        ('pt', 'Português'),
        ('en', 'English'),
    ]
    

    # Contact Information
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message=_("Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    )
    phone = models.CharField(_('Phone Number'), validators=[phone_regex], max_length=17, blank=True)
    
    # Profile Information
    dharma_name = models.CharField(_('Dharma Name'), max_length=100, blank=True, 
                                  help_text=_('Your Buddhist practice name'))
    
    
    
    # Preferences
    preferred_language = models.CharField(
        _('Preferred Language'),
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='en'
    )
    email_notifications = models.BooleanField(_('Email Notifications'), default=True)
    push_notifications = models.BooleanField(_('Push Notifications'), default=True)
    
    
    # Metadata
    is_verified = models.BooleanField(_('Email Verified'), default=False)
    last_activity = models.DateTimeField(_('Last Activity'), null=True, blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        """Return the best available display name"""
        if self.dharma_name:
            return self.dharma_name
        elif self.get_full_name():
            return self.get_full_name()
        else:
            return self.email

    @property
    def full_name(self):
        """Return full name"""
        return self.get_full_name()


    def update_last_activity(self):
        """Update last activity timestamp"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])


class UserPreferences(models.Model):
    """
    User preferences and settings
    """
    
    THEME_CHOICES = [
        ('light', _('Light')),
        ('dark', _('Dark')),
        ('auto', _('Auto')),
    ]
    
    QUALITY_CHOICES = [
        ('low', _('Low (64kbps)')),
        ('medium', _('Medium (128kbps)')),
        ('high', _('High (320kbps)')),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # Appearance
    theme = models.CharField(_('Theme'), max_length=10, choices=THEME_CHOICES, default='auto')
    
    # Audio Settings
    autoplay_next = models.BooleanField(_('Autoplay Next Track'), default=True)
    download_quality = models.CharField(_('Download Quality'), max_length=10, 
                                      choices=QUALITY_CHOICES, default='medium')
    playback_speed = models.FloatField(_('Playback Speed'), default=1.0,
                                     validators=[MinValueValidator(0.5), MaxValueValidator(2.0)])
    
    # Content Preferences
    show_transcripts = models.BooleanField(_('Show Transcripts by Default'), default=True)
    preferred_session_length = models.PositiveIntegerField(_('Preferred Session Length (minutes)'), 
                                                         default=30)
    
    # Notifications
    session_reminders = models.BooleanField(_('Daily Session Reminders'), default=True)
    reminder_time = models.TimeField(_('Reminder Time'), default='09:00')
    retreat_notifications = models.BooleanField(_('Retreat Notifications'), default=True)
    
    # Privacy
    profile_visibility = models.CharField(_('Profile Visibility'), max_length=10,
                                        choices=[('public', _('Public')), ('private', _('Private'))],
                                        default='private')
    
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('User Preferences')
        verbose_name_plural = _('User Preferences')

    def __str__(self):
        return f"Preferences for {self.user.get_display_name()}"


class UserActivity(models.Model):
    """
    Track user activity and engagement
    """
    
    ACTIVITY_TYPES = [
        ('login', _('Login')),
        ('logout', _('Logout')),
        ('track_play', _('Track Play')),
        ('track_complete', _('Track Complete')),
        ('bookmark_create', _('Bookmark Created')),
        ('retreat_join', _('Retreat Joined')),
        ('profile_update', _('Profile Updated')),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(_('Activity Type'), max_length=20, choices=ACTIVITY_TYPES)
    description = models.CharField(_('Description'), max_length=255, blank=True)
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)

    class Meta:
        verbose_name = _('User Activity')
        verbose_name_plural = _('User Activities')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['activity_type', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.get_activity_type_display()} - {self.timestamp}"


class UserGroupMembership(models.Model):
    """
    Track user membership in retreat groups with different states
    """
    
    STATUS_CHOICES = [
        ('requested', _('Requested')),
        ('confirmed', _('Confirmed')),
        ('cancelled', _('Cancelled')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    group = models.ForeignKey('retreats.RetreatGroup', on_delete=models.CASCADE, related_name='user_memberships')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='requested')
    
    # Dates
    requested_date = models.DateTimeField(_('Requested Date'), auto_now_add=True)
    confirmed_date = models.DateTimeField(_('Confirmed Date'), null=True, blank=True)
    cancelled_date = models.DateTimeField(_('Cancelled Date'), null=True, blank=True)
    
    # Notes
    notes = models.TextField(_('Notes'), blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    
    class Meta:
        verbose_name = _('User Group Membership')
        verbose_name_plural = _('User Group Memberships')
        unique_together = ['user', 'group']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['group', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.get_display_name()} - {self.group.name} ({self.get_status_display()})"
    
    def confirm_membership(self):
        """Confirm the membership"""
        self.status = 'confirmed'
        self.confirmed_date = timezone.now()
        self.save()
    
    def cancel_membership(self):
        """Cancel the membership"""
        self.status = 'cancelled'
        self.cancelled_date = timezone.now()
        self.save()


class DeviceActivation(models.Model):
    """
    Tracks activated devices for passwordless authentication
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_activations')
    device_fingerprint = models.CharField(_('Device Fingerprint'), max_length=255, unique=True)
    device_name = models.CharField(_('Device Name'), max_length=100, blank=True)
    device_type = models.CharField(_('Device Type'), max_length=50, blank=True)  # ios, android, web
    
    # Activation details
    activated_at = models.DateTimeField(_('Activated At'), auto_now_add=True)
    last_used = models.DateTimeField(_('Last Used'), auto_now=True)
    is_active = models.BooleanField(_('Is Active'), default=True)
    
    # Security
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)
    
    class Meta:
        verbose_name = _('Device Activation')
        verbose_name_plural = _('Device Activations')
        ordering = ['-activated_at']
        indexes = [
            models.Index(fields=['user', '-activated_at']),
            models.Index(fields=['device_fingerprint']),
        ]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.device_name or self.device_type or 'Unknown Device'}"

    def deactivate(self):
        """Deactivate this device"""
        self.is_active = False
        self.save(update_fields=['is_active'])


class MagicLinkToken(models.Model):
    """
    Single-use magic link tokens for device activation
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='magic_tokens')
    token = models.CharField(_('Token'), max_length=64, unique=True)
    
    # Request details
    email = models.EmailField(_('Email'))
    device_fingerprint = models.CharField(_('Device Fingerprint'), max_length=255)
    device_name = models.CharField(_('Device Name'), max_length=100, blank=True)
    device_type = models.CharField(_('Device Type'), max_length=50, blank=True)
    
    # Status and timing
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    expires_at = models.DateTimeField(_('Expires At'))
    used_at = models.DateTimeField(_('Used At'), null=True, blank=True)
    is_used = models.BooleanField(_('Is Used'), default=False)
    
    # Security
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)
    
    class Meta:
        verbose_name = _('Magic Link Token')
        verbose_name_plural = _('Magic Link Tokens')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Token for {self.email} - {self.created_at}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            # Token expires in 1 hour
            self.expires_at = timezone.now() + timezone.timedelta(hours=1)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if token is expired"""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired

    def use_token(self):
        """Mark token as used"""
        if not self.is_valid:
            raise ValueError("Token is already used or expired")
        
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])


class UserApprovalRequest(models.Model):
    """
    Requests for new user approval by admins
    """
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('Email'))
    first_name = models.CharField(_('First Name'), max_length=30)
    last_name = models.CharField(_('Last Name'), max_length=30)
    message = models.TextField(_('Message to Admin'), blank=True)
    
    # Status
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_message = models.TextField(_('Admin Message'), blank=True, 
                                   help_text=_('Optional message to send to user upon rejection'))
    
    # Dates
    requested_at = models.DateTimeField(_('Requested At'), auto_now_add=True)
    reviewed_at = models.DateTimeField(_('Reviewed At'), null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='reviewed_requests')
    
    # Device info from request
    device_fingerprint = models.CharField(_('Device Fingerprint'), max_length=255, blank=True)
    device_name = models.CharField(_('Device Name'), max_length=100, blank=True)
    device_type = models.CharField(_('Device Type'), max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)
    
    class Meta:
        verbose_name = _('User Approval Request')
        verbose_name_plural = _('User Approval Requests')
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', '-requested_at']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email}) - {self.get_status_display()}"

    def approve(self, admin_user):
        """Approve the request and create user"""
        if self.status != 'pending':
            raise ValueError("Request is not pending")
        
        # Create the user
        user = User.objects.create_user(
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            is_active=True
        )
        
        # Update request status
        self.status = 'approved'
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save(update_fields=['status', 'reviewed_at', 'reviewed_by'])
        
        return user

    def reject(self, admin_user, admin_message=''):
        """Reject the request"""
        if self.status != 'pending':
            raise ValueError("Request is not pending")
        
        self.status = 'rejected'
        self.admin_message = admin_message
        self.reviewed_at = timezone.now()
        self.reviewed_by = admin_user
        self.save(update_fields=['status', 'admin_message', 'reviewed_at', 'reviewed_by'])