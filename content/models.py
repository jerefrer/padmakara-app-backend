from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

User = get_user_model()


class UserProgress(models.Model):
    """
    Track user progress through audio tracks
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='progress')
    
    # Progress Data
    current_position = models.PositiveIntegerField(_('Current Position (seconds)'), default=0)
    completion_percentage = models.FloatField(_('Completion Percentage'), default=0.0,
                                            validators=[MinValueValidator(0), MaxValueValidator(100)])
    play_count = models.PositiveIntegerField(_('Play Count'), default=0)
    total_listening_time = models.PositiveIntegerField(_('Total Listening Time (seconds)'), default=0)
    
    # Status
    is_completed = models.BooleanField(_('Is Completed'), default=False)
    is_favorited = models.BooleanField(_('Is Favorited'), default=False)
    
    # Timestamps
    first_played = models.DateTimeField(_('First Played'), auto_now_add=True)
    last_played = models.DateTimeField(_('Last Played'), auto_now=True)
    completed_at = models.DateTimeField(_('Completed At'), null=True, blank=True)

    class Meta:
        verbose_name = _('User Progress')
        verbose_name_plural = _('User Progress')
        unique_together = ['user', 'track']
        indexes = [
            models.Index(fields=['user', '-last_played']),
            models.Index(fields=['track', '-completion_percentage']),
        ]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.track.title} ({self.completion_percentage:.1f}%)"

    def update_progress(self, position_seconds, duration_seconds=None):
        """Update progress based on current position"""
        self.current_position = position_seconds
        self.play_count += 1
        
        if duration_seconds:
            self.completion_percentage = min((position_seconds / duration_seconds) * 100, 100)
            
            # Mark as completed if over 95%
            if self.completion_percentage >= 95 and not self.is_completed:
                self.is_completed = True
                self.completed_at = timezone.now()
        
        self.save()

    @property
    def listening_time_minutes(self):
        """Get total listening time in minutes"""
        return round(self.total_listening_time / 60, 1)


class Bookmark(models.Model):
    """
    User bookmarks for specific positions in tracks
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='bookmarks')
    
    # Bookmark Data
    position_seconds = models.PositiveIntegerField(_('Position (seconds)'))
    title = models.CharField(_('Bookmark Title'), max_length=200, blank=True)
    notes = models.TextField(_('Notes'), blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Bookmark')
        verbose_name_plural = _('Bookmarks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['track', 'position_seconds']),
        ]

    def __str__(self):
        position_min = self.position_seconds // 60
        position_sec = self.position_seconds % 60
        return f"{self.user.get_display_name()} - {self.track.title} @ {position_min}:{position_sec:02d}"

    @property
    def position_formatted(self):
        """Get position in MM:SS format"""
        minutes = self.position_seconds // 60
        seconds = self.position_seconds % 60
        return f"{minutes}:{seconds:02d}"

    def save(self, *args, **kwargs):
        # Generate title if not provided
        if not self.title:
            self.title = f"Bookmark at {self.position_formatted}"
        super().save(*args, **kwargs)


class PDFProgress(models.Model):
    """
    Track user progress through PDF transcripts
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pdf_progress')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='pdf_progress')
    
    # Progress Data
    current_page = models.PositiveIntegerField(_('Current Page'), default=1)
    total_pages = models.PositiveIntegerField(_('Total Pages'), default=1)
    completion_percentage = models.FloatField(_('Completion Percentage'), default=0.0,
                                            validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Metadata
    last_accessed = models.DateTimeField(_('Last Accessed'), auto_now=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)

    class Meta:
        verbose_name = _('PDF Progress')
        verbose_name_plural = _('PDF Progress')
        unique_together = ['user', 'track']

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.track.title} PDF (Page {self.current_page}/{self.total_pages})"

    def update_progress(self, current_page, total_pages=None):
        """Update PDF reading progress"""
        self.current_page = current_page
        if total_pages:
            self.total_pages = total_pages
        
        self.completion_percentage = min((current_page / self.total_pages) * 100, 100)
        self.save()


class PDFHighlight(models.Model):
    """
    User highlights in PDF transcripts
    """
    
    COLOR_CHOICES = [
        ('yellow', _('Yellow')),
        ('green', _('Green')),
        ('blue', _('Blue')),
        ('pink', _('Pink')),
        ('orange', _('Orange')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pdf_highlights')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='pdf_highlights')
    
    # Highlight Data
    page_number = models.PositiveIntegerField(_('Page Number'))
    highlighted_text = models.TextField(_('Highlighted Text'))
    color = models.CharField(_('Highlight Color'), max_length=10, choices=COLOR_CHOICES, default='yellow')
    notes = models.TextField(_('Notes'), blank=True)
    
    # Position data (for precise highlighting)
    start_position = models.JSONField(_('Start Position'), default=dict, blank=True)
    end_position = models.JSONField(_('End Position'), default=dict, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('PDF Highlight')
        verbose_name_plural = _('PDF Highlights')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['track', 'page_number']),
        ]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.track.title} (Page {self.page_number})"

    @property
    def preview_text(self):
        """Get preview of highlighted text (first 100 chars)"""
        return self.highlighted_text[:100] + "..." if len(self.highlighted_text) > 100 else self.highlighted_text


class DownloadedContent(models.Model):
    """
    Track user's downloaded content for offline access
    """
    
    CONTENT_TYPE_CHOICES = [
        ('audio', _('Audio Only')),
        ('transcript', _('Transcript Only')),
        ('both', _('Audio + Transcript')),
    ]
    
    STATUS_CHOICES = [
        ('requested', _('Requested')),
        ('downloading', _('Downloading')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('expired', _('Expired')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='downloads')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='downloads')
    
    # Download Info
    content_type = models.CharField(_('Content Type'), max_length=20, choices=CONTENT_TYPE_CHOICES)
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='requested')
    
    # File Info
    file_size = models.PositiveBigIntegerField(_('File Size (bytes)'), null=True, blank=True)
    local_path = models.CharField(_('Local Path'), max_length=500, blank=True)
    download_url = models.URLField(_('Download URL'), blank=True)
    
    # Metadata
    requested_at = models.DateTimeField(_('Requested At'), auto_now_add=True)
    downloaded_at = models.DateTimeField(_('Downloaded At'), null=True, blank=True)
    expires_at = models.DateTimeField(_('Expires At'), null=True, blank=True)
    last_accessed = models.DateTimeField(_('Last Accessed'), null=True, blank=True)

    class Meta:
        verbose_name = _('Downloaded Content')
        verbose_name_plural = _('Downloaded Content')
        unique_together = ['user', 'track', 'content_type']
        ordering = ['-requested_at']

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.track.title} ({self.get_content_type_display()})"

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None

    @property
    def is_expired(self):
        """Check if download has expired"""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def mark_completed(self, file_size=None, local_path=None):
        """Mark download as completed"""
        self.status = 'completed'
        self.downloaded_at = timezone.now()
        if file_size:
            self.file_size = file_size
        if local_path:
            self.local_path = local_path
        self.save()

    def update_last_accessed(self):
        """Update last accessed timestamp"""
        self.last_accessed = timezone.now()
        self.save(update_fields=['last_accessed'])


class UserNotes(models.Model):
    """
    User's personal notes for tracks or retreats
    """
    
    NOTE_TYPE_CHOICES = [
        ('track', _('Track Note')),
        ('retreat', _('Retreat Note')),
        ('general', _('General Note')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='user_notes', 
                            null=True, blank=True)
    retreat = models.ForeignKey('retreats.Retreat', on_delete=models.CASCADE, related_name='user_notes',
                              null=True, blank=True)
    
    # Note Data
    note_type = models.CharField(_('Note Type'), max_length=20, choices=NOTE_TYPE_CHOICES, default='general')
    title = models.CharField(_('Title'), max_length=200, blank=True)
    content = models.TextField(_('Content'))
    is_private = models.BooleanField(_('Is Private'), default=True)
    
    # Tags for organization
    tags = models.JSONField(_('Tags'), default=list, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('User Note')
        verbose_name_plural = _('User Notes')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['note_type', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.title or 'Note'}"

    def save(self, *args, **kwargs):
        # Generate title if not provided
        if not self.title:
            if self.track:
                self.title = f"Note for {self.track.title}"
            elif self.retreat:
                self.title = f"Note for {self.retreat.name}"
            else:
                self.title = f"Note from {self.created_at.strftime('%Y-%m-%d')}"
        super().save(*args, **kwargs)