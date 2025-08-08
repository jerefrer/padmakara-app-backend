from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model for Padmakara Buddhist retreat app
    Extends Django's built-in User with retreat-specific fields
    """
    
    LANGUAGE_CHOICES = [
        ('pt', 'Português'),
        ('en', 'English'),
    ]
    
    SUBSCRIPTION_STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('trial', _('Trial')),
        ('expired', _('Expired')),
    ]
    
    SUBSCRIPTION_PLAN_CHOICES = [
        ('basic', _('Basic')),
        ('premium', _('Premium')),
        ('lifetime', _('Lifetime')),
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
    birth_date = models.DateField(_('Birth Date'), null=True, blank=True)
    bio = models.TextField(_('Biography'), max_length=500, blank=True)
    website = models.URLField(_('Website'), blank=True)
    location = models.CharField(_('Location'), max_length=100, blank=True)
    
    
    # Subscription Information
    subscription_status = models.CharField(
        _('Subscription Status'),
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='trial'
    )
    subscription_plan = models.CharField(
        _('Subscription Plan'),
        max_length=20,
        choices=SUBSCRIPTION_PLAN_CHOICES,
        default='basic'
    )
    subscription_start_date = models.DateTimeField(_('Subscription Start Date'), null=True, blank=True)
    subscription_end_date = models.DateTimeField(_('Subscription End Date'), null=True, blank=True)
    
    # Preferences
    preferred_language = models.CharField(
        _('Preferred Language'),
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='en'
    )
    email_notifications = models.BooleanField(_('Email Notifications'), default=True)
    push_notifications = models.BooleanField(_('Push Notifications'), default=True)
    
    # Profile Picture
    avatar = models.ImageField(_('Avatar'), upload_to='avatars/', null=True, blank=True)
    
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
            return self.username

    @property
    def full_name(self):
        """Return full name"""
        return self.get_full_name()

    @property
    def is_subscription_active(self):
        """Check if subscription is currently active"""
        if self.subscription_status != 'active':
            return False
        if self.subscription_end_date and self.subscription_end_date < timezone.now():
            return False
        return True

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