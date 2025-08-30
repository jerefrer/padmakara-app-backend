import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models.signals import pre_delete, post_delete
from django.dispatch import receiver
from utils.storage import retreat_audio_upload_path, retreat_transcript_upload_path, retreat_image_upload_path, RetreatMediaStorage

User = get_user_model()
logger = logging.getLogger(__name__)


class Place(models.Model):
    """
    Places where retreats can be held
    """
    name = models.CharField(_('Place Name'), max_length=200)
    abbreviation = models.CharField(_('Abbreviation'), max_length=50, help_text=_('Short form like "CCA", "NYC", etc.'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Place')
        verbose_name_plural = _('Places')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class Teacher(models.Model):
    """
    Teachers who can lead retreats
    """
    name = models.CharField(_('Teacher Name'), max_length=200)
    abbreviation = models.CharField(_('Abbreviation'), max_length=50, help_text=_('Short form like "JKR", "MW", etc.'))
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Teacher')
        verbose_name_plural = _('Teachers')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class RetreatGroup(models.Model):
    """
    Groups that organize retreats (e.g., specific Buddhist centers or teachers)
    """
    
    name = models.CharField(_('Group Name'), max_length=200)
    description = models.TextField(_('Description'), blank=True)
    order = models.PositiveIntegerField(_('Display Order'), default=0, help_text=_('Order in which this group appears in forms'))
    
    # Metadata
    logo = models.ImageField(_('Logo'), upload_to='group_logos/', null=True, blank=True)
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Group')
        verbose_name_plural = _('Groups')
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    @property
    def retreats_count(self):
        return self.retreats.count()


class Retreat(models.Model):
    """
    Individual retreat events
    """
    
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('upcoming', _('Upcoming')),
        ('ongoing', _('Ongoing')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]
    
    TYPE_CHOICES = [
        ('online', _('Online')),
        ('in_person', _('In Person')),
        ('hybrid', _('Hybrid')),
    ]

    # Basic Information
    name = models.CharField(_('Retreat Name'), max_length=200)
    description = models.TextField(_('Description'))
    groups = models.ManyToManyField(RetreatGroup, related_name='retreats', verbose_name=_('Groups'))
    places = models.ManyToManyField(Place, related_name='retreats', verbose_name=_('Places'), blank=True)
    teachers = models.ManyToManyField(Teacher, related_name='retreats', verbose_name=_('Teachers'), blank=True)
    
    # Dates and Duration
    start_date = models.DateField(_('Start Date'))
    end_date = models.DateField(_('End Date'))
    
    # Type and Status
    retreat_type = models.CharField(_('Type'), max_length=20, choices=TYPE_CHOICES, default='online')
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Participation
    is_public = models.BooleanField(_('Is Public'), default=True)
    
    # Location (for in-person retreats)
    location = models.CharField(_('Location'), max_length=200, blank=True)
    address = models.TextField(_('Address'), blank=True)
    
    # Media
    image = models.ImageField(_('Retreat Image'), upload_to=retreat_image_upload_path, storage=RetreatMediaStorage(), null=True, blank=True)
    
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Retreat')
        verbose_name_plural = _('Retreats')
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.start_date})"


    @property
    def duration_days(self):
        """Calculate retreat duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None

    @property
    def participants_count(self):
        return self.participants.filter(status__in=['registered', 'confirmed']).count()

    def delete(self, using=None, keep_parents=False):
        """Override delete to clean up all S3 files for this retreat"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Deleting retreat {self.id}: {self.name}")
        
        # Store all file information before deletion
        files_to_delete = []
        
        # Collect all track files
        for session in self.sessions.all():
            for track in session.tracks.all():
                if track.audio_file:
                    files_to_delete.append(track.audio_file.name)
                if track.transcript_file:
                    files_to_delete.append(track.transcript_file.name)
        
        # Also collect retreat image if it exists
        if self.image:
            files_to_delete.append(self.image.name)
        
        # Generate retreat folder name for complete cleanup
        start_date = self.start_date.strftime('%Y.%m.%d')
        end_date = self.end_date.strftime('%d') if self.end_date else start_date.split('.')[-1]
        folder_parts = [f"{start_date}-{end_date}"]
        
        if self.groups.exists():
            folder_parts.append(self.groups.first().name)
        if self.places.exists():
            place_abbrevs = [place.abbreviation for place in self.places.all()]
            folder_parts.append(' + '.join(place_abbrevs))
        if self.teachers.exists():
            teacher_abbrevs = [teacher.abbreviation for teacher in self.teachers.all()]
            folder_parts.append(' + '.join(teacher_abbrevs))
            
        retreat_folder = ' - '.join(folder_parts)
        
        # Delete the model instance (this will cascade delete sessions and tracks)
        super().delete(using=using, keep_parents=keep_parents)
        
        # Clean up all S3 files
        try:
            from utils.storage import RetreatMediaStorage
            storage = RetreatMediaStorage()
            
            # Delete individual files
            for file_name in files_to_delete:
                if file_name:
                    logger.info(f"Deleting S3 file: {file_name}")
                    storage.delete(file_name)
            
            # Delete entire retreat folder if it exists on S3
            import boto3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=storage.access_key,
                aws_secret_access_key=storage.secret_key,
                region_name=storage.region_name
            )
            bucket_name = storage.bucket_name
            
            # List and delete all objects in the retreat folder
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=f"{retreat_folder}/")
            
            for page in pages:
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects_to_delete:
                        s3_client.delete_objects(
                            Bucket=bucket_name,
                            Delete={'Objects': objects_to_delete}
                        )
                        logger.info(f"Deleted {len(objects_to_delete)} objects from {retreat_folder}/")
                
        except Exception as e:
            logger.error(f"Error cleaning up S3 files for retreat {self.id}: {str(e)}")



class Session(models.Model):
    """
    Individual sessions within a retreat (e.g., daily teachings)
    """
    
    TIME_PERIOD_CHOICES = [
        ('morning', _('Morning')),
        ('evening', _('Evening')),
        ('full_day', _('Full Day')),
    ]
    
    retreat = models.ForeignKey(Retreat, on_delete=models.CASCADE, related_name='sessions')
    title = models.CharField(_('Session Title'), max_length=200)
    description = models.TextField(_('Description'), blank=True)
    
    # Scheduling
    session_date = models.DateField(_('Session Date'))
    time_period = models.CharField(_('Time Period'), max_length=20, choices=TIME_PERIOD_CHOICES, default='morning')
    session_number = models.PositiveIntegerField(_('Session Number'), default=1)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Session')
        verbose_name_plural = _('Sessions')
        ordering = ['retreat', 'session_number']
        unique_together = ['retreat', 'session_number']

    def __str__(self):
        return f"{self.retreat.name} - Session {self.session_number}: {self.title}"

    @property
    def tracks_count(self):
        return self.tracks.count()
    
    @property
    def duration_minutes(self):
        """Calculate session duration from tracks"""
        return self.tracks.aggregate(total=models.Sum('duration_minutes'))['total'] or 0

    def delete(self, using=None, keep_parents=False):
        """Override delete to clean up S3 files for all tracks in session"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Deleting session {self.id}: {self.title}")
        
        # Store track information before deletion
        tracks_info = []
        for track in self.tracks.all():
            tracks_info.append({
                'audio_file': track.audio_file.name if track.audio_file else None,
                'transcript_file': track.transcript_file.name if track.transcript_file else None,
            })
        
        retreat = self.retreat
        
        # Delete the model instance (this will cascade delete tracks)
        super().delete(using=using, keep_parents=keep_parents)
        
        # Clean up S3 files for all tracks that were in this session
        try:
            from utils.storage import RetreatMediaStorage
            storage = RetreatMediaStorage()
            
            for track_info in tracks_info:
                if track_info['audio_file']:
                    logger.info(f"Deleting S3 audio file: {track_info['audio_file']}")
                    storage.delete(track_info['audio_file'])
                    
                if track_info['transcript_file']:
                    logger.info(f"Deleting S3 transcript file: {track_info['transcript_file']}")
                    storage.delete(track_info['transcript_file'])
            
            # Check if retreat folder should be cleaned up
            self._cleanup_empty_retreat_folder(retreat)
            
        except Exception as e:
            logger.error(f"Error cleaning up S3 files for session {self.id}: {str(e)}")
    
    def _cleanup_empty_retreat_folder(self, retreat):
        """Clean up retreat folder if no tracks remain in any session"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Check if any sessions in this retreat still have tracks
            if any(session.tracks.exists() for session in retreat.sessions.all()):
                return  # Still has tracks, don't clean up
                
            # No tracks left in entire retreat, check S3 folder
            import boto3
            from django.conf import settings
            
            # Create S3 client directly
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                
            # Generate the retreat folder name
            start_date = retreat.start_date.strftime('%Y.%m.%d')
            end_date = retreat.end_date.strftime('%d') if retreat.end_date else start_date.split('.')[-1]
            folder_parts = [f"{start_date}-{end_date}"]
            
            if retreat.groups.exists():
                folder_parts.append(retreat.groups.first().name)
            if retreat.places.exists():
                place_abbrevs = [place.abbreviation for place in retreat.places.all()]
                folder_parts.append(' + '.join(place_abbrevs))
            if retreat.teachers.exists():
                teacher_abbrevs = [teacher.abbreviation for teacher in retreat.teachers.all()]
                folder_parts.append(' + '.join(teacher_abbrevs))
                
            retreat_folder = ' - '.join(folder_parts)
            
            # Check if retreat folder is empty on S3
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=f"{retreat_folder}/",
                MaxKeys=1
            )
            
            if response.get('KeyCount', 0) == 0:
                logger.info(f"Retreat folder is empty and cleaned up: {retreat_folder}")
                
        except Exception as e:
            logger.error(f"Error during retreat folder cleanup: {str(e)}")


class Track(models.Model):
    """
    Individual audio/video tracks within a session
    """
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('pt', 'Português'),
    ]
    

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='tracks')
    title = models.CharField(_('Track Title'), max_length=200)
    description = models.TextField(_('Description'), blank=True)
    
    # Content
    language = models.CharField(_('Language'), max_length=5, choices=LANGUAGE_CHOICES, default='en')
    
    # Files
    audio_file = models.FileField(_('Audio File'), upload_to=retreat_audio_upload_path, storage=RetreatMediaStorage(), max_length=500, null=True, blank=True)
    transcript_file = models.FileField(_('Transcript (PDF)'), upload_to=retreat_transcript_upload_path, 
                                     storage=RetreatMediaStorage(), max_length=500, null=True, blank=True)
    
    # Metadata
    duration_minutes = models.PositiveIntegerField(_('Duration (minutes)'), default=0)
    duration_seconds = models.PositiveIntegerField(_('Duration (seconds)'), default=0, help_text=_('Accurate duration in seconds'))
    track_number = models.PositiveIntegerField(_('Track Number'), default=1)
    file_size = models.PositiveBigIntegerField(_('File Size (bytes)'), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Track')
        verbose_name_plural = _('Tracks')
        ordering = ['session', 'track_number']
        unique_together = ['session', 'track_number']

    def __str__(self):
        return f"{self.session.title} - Track {self.track_number}: {self.title}"

    @property
    def audio_file_url(self):
        """Get audio file URL if exists"""
        return self.audio_file.url if self.audio_file else None

    @property
    def transcript_file_url(self):
        """Get transcript file URL if exists"""
        return self.transcript_file.url if self.transcript_file else None

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None
    
    @property
    def duration(self):
        """Get accurate duration in seconds, fallback to minutes if not available"""
        if self.duration_seconds > 0:
            return self.duration_seconds
        elif self.duration_minutes > 0:
            return self.duration_minutes * 60  # Convert minutes to seconds
        return 1800  # Default fallback to 30 minutes if no duration available

    def update_duration(self, duration_seconds):
        """Update track duration (called by admin interface or API)"""
        if duration_seconds and duration_seconds > 0:
            self.duration_seconds = duration_seconds
            self.duration_minutes = max(1, round(duration_seconds / 60))
            self.save(update_fields=['duration_seconds', 'duration_minutes'])
            return True
        return False

    def delete(self, using=None, keep_parents=False):
        """Override delete to clean up S3 files and empty folders"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Store file paths before deletion
        audio_file_name = self.audio_file.name if self.audio_file else None
        transcript_file_name = self.transcript_file.name if self.transcript_file else None
        session = self.session
        
        # Delete the model instance first
        super().delete(using=using, keep_parents=keep_parents)
        
        # Clean up S3 files if they exist
        try:
            if audio_file_name and hasattr(self.audio_file.storage, 'delete'):
                logger.info(f"Deleting S3 audio file: {audio_file_name}")
                self.audio_file.storage.delete(audio_file_name)
                
            if transcript_file_name and hasattr(self.transcript_file.storage, 'delete'):
                logger.info(f"Deleting S3 transcript file: {transcript_file_name}")
                self.transcript_file.storage.delete(transcript_file_name)
                
            # Clean up empty folders
            self._cleanup_empty_s3_folders(session, audio_file_name or transcript_file_name)
            
        except Exception as e:
            logger.error(f"Error cleaning up S3 files for track {self.id}: {str(e)}")

    def _cleanup_empty_s3_folders(self, session, file_path):
        """Clean up empty S3 folders after file deletion"""
        if not file_path:
            return
            
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            import boto3
            from botocore.exceptions import ClientError
            from django.conf import settings
            
            # Create S3 client directly
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            
            # Extract folder paths from the file path
            # file_path format: "2025.04.12-13 - GROUP - PLACE - TEACHER/SESSION NAME/filename.mp3"
            path_parts = file_path.split('/')
            if len(path_parts) < 3:
                return
                
            retreat_folder = path_parts[0]
            session_folder = f"{retreat_folder}/{path_parts[1]}"
            
            # Check if session folder is empty (no other tracks in this session)
            if not session.tracks.exists():
                logger.info(f"Session folder is empty, checking for cleanup: {session_folder}")
                
                # List objects in session folder
                try:
                    response = s3_client.list_objects_v2(
                        Bucket=bucket_name,
                        Prefix=f"{session_folder}/",
                        MaxKeys=1
                    )
                    
                    # If no objects found in session folder, it's safe to clean up
                    if response.get('KeyCount', 0) == 0:
                        logger.info(f"Session folder is empty, no cleanup needed: {session_folder}")
                        
                        # Check if retreat folder should also be cleaned up
                        # (no other sessions with tracks in this retreat)
                        retreat = session.retreat
                        if not any(s.tracks.exists() for s in retreat.sessions.all()):
                            logger.info(f"Retreat folder is also empty, checking: {retreat_folder}")
                            
                            # Check if retreat folder is empty
                            retreat_response = s3_client.list_objects_v2(
                                Bucket=bucket_name,
                                Prefix=f"{retreat_folder}/",
                                MaxKeys=1
                            )
                            
                            if retreat_response.get('KeyCount', 0) == 0:
                                logger.info(f"Retreat folder is empty and cleaned up: {retreat_folder}")
                                
                except ClientError as e:
                    logger.warning(f"Could not check S3 folder contents: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error during S3 folder cleanup: {str(e)}")


class RetreatParticipation(models.Model):
    """
    User participation in retreats
    """
    
    STATUS_CHOICES = [
        ('requested', _('Requested')),
        ('registered', _('Registered')),
        ('confirmed', _('Confirmed')),
        ('attended', _('Attended')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='retreat_participations')
    retreat = models.ForeignKey(Retreat, on_delete=models.CASCADE, related_name='participants')
    
    # Status and Dates
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='requested')
    registration_date = models.DateTimeField(_('Registration Date'), auto_now_add=True)
    
    # Feedback
    notes = models.TextField(_('Notes'), blank=True)
    
    # Metadata
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Retreat Participation')
        verbose_name_plural = _('Retreat Participations')
        unique_together = ['user', 'retreat']
        ordering = ['-registration_date']

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.retreat.name} ({self.get_status_display()})"


    @property
    def is_active(self):
        """Check if participation is active"""
        return self.status in ['registered', 'confirmed', 'attended']


class DownloadRequest(models.Model):
    """
    Tracks ZIP file generation requests for retreat downloads
    """
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('ready', _('Ready')),
        ('failed', _('Failed')),
        ('expired', _('Expired')),
    ]
    
    # Core fields
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='download_requests')
    retreat = models.ForeignKey(Retreat, on_delete=models.CASCADE, related_name='download_requests')
    
    # Status tracking
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File information
    file_size = models.PositiveBigIntegerField(_('File Size (bytes)'), null=True, blank=True)
    download_url = models.URLField(_('Download URL'), max_length=1000, null=True, blank=True)
    s3_key = models.CharField(_('S3 Key'), max_length=500, null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(_('Error Message'), blank=True)
    retry_count = models.PositiveSmallIntegerField(_('Retry Count'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)
    expires_at = models.DateTimeField(_('Expires At'), null=True, blank=True)
    
    # Processing metadata
    lambda_request_id = models.CharField(_('Lambda Request ID'), max_length=100, null=True, blank=True)
    processing_started_at = models.DateTimeField(_('Processing Started At'), null=True, blank=True)
    processing_completed_at = models.DateTimeField(_('Processing Completed At'), null=True, blank=True)
    
    # ZIP sharing metadata
    is_shared = models.BooleanField(_('Is Shared ZIP'), default=False, help_text=_('Whether this ZIP is shared among multiple users'))
    shared_zip_key = models.CharField(_('Shared ZIP Key'), max_length=500, null=True, blank=True, help_text=_('S3 key for shared ZIP file'))
    download_count = models.PositiveIntegerField(_('Download Count'), default=0, help_text=_('Number of times this ZIP has been downloaded'))
    last_accessed_at = models.DateTimeField(_('Last Accessed At'), null=True, blank=True, help_text=_('When this ZIP was last downloaded'))
    popularity_score = models.FloatField(_('Popularity Score'), default=0.0, help_text=_('Calculated popularity for lifecycle decisions'))

    class Meta:
        verbose_name = _('Download Request')
        verbose_name_plural = _('Download Requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['retreat', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['expires_at']),
            # Sharing-related indexes
            models.Index(fields=['retreat', 'is_shared', 'status'], name='ret_dl_sharing_lookup'),
            models.Index(fields=['shared_zip_key'], name='ret_dl_shared_key'),
            models.Index(fields=['last_accessed_at'], name='ret_dl_last_accessed'),
            models.Index(fields=['popularity_score', 'retreat'], name='ret_dl_popularity'),
        ]

    def __str__(self):
        return f"Download {self.retreat.name} by {self.user.email} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Set expiration time when creating request
        if not self.expires_at and self.status == 'pending':
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=48)
            
        # Update processing timestamps
        if self.pk:  # Existing object
            old_instance = DownloadRequest.objects.get(pk=self.pk)
            if old_instance.status != self.status:
                if self.status == 'processing' and not self.processing_started_at:
                    self.processing_started_at = timezone.now()
                elif self.status in ['ready', 'failed'] and not self.processing_completed_at:
                    self.processing_completed_at = timezone.now()
                    
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if download request has expired"""
        return self.expires_at and timezone.now() > self.expires_at

    @property
    def file_size_mb(self):
        """Get file size in MB"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None

    @property
    def processing_duration(self):
        """Get processing duration in seconds"""
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None

    @property
    def time_until_expiry(self):
        """Get time until expiration"""
        if self.expires_at:
            remaining = self.expires_at - timezone.now()
            if remaining.total_seconds() > 0:
                return remaining
        return None

    def mark_as_processing(self, lambda_request_id=None):
        """Mark request as processing"""
        self.status = 'processing'
        self.processing_started_at = timezone.now()
        if lambda_request_id:
            self.lambda_request_id = lambda_request_id
        self.save(update_fields=['status', 'processing_started_at', 'lambda_request_id'])

    def mark_as_ready(self, download_url, s3_key, file_size):
        """Mark request as ready for download"""
        self.status = 'ready'
        self.download_url = download_url
        self.s3_key = s3_key
        self.file_size = file_size
        self.processing_completed_at = timezone.now()
        self.save(update_fields=[
            'status', 'download_url', 's3_key', 'file_size', 'processing_completed_at'
        ])

    def mark_as_failed(self, error_message):
        """Mark request as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.processing_completed_at = timezone.now()
        self.retry_count += 1
        self.save(update_fields=[
            'status', 'error_message', 'processing_completed_at', 'retry_count'
        ])

    def can_retry(self, max_retries=3):
        """Check if request can be retried"""
        return self.status == 'failed' and self.retry_count < max_retries and not self.is_expired

    # ==============================================================================
    # ZIP Sharing Methods
    # ==============================================================================

    @classmethod
    def find_existing_shared_zip(cls, retreat):
        """Find an existing valid shared ZIP for this retreat"""
        return cls.objects.filter(
            retreat=retreat,
            is_shared=True,
            status='ready',
            expires_at__gt=timezone.now()
        ).order_by('-last_accessed_at').first()

    @classmethod
    def create_shared_zip_request(cls, user, retreat, existing_zip=None):
        """Create a new download request that shares an existing ZIP or creates a new shared ZIP"""
        if existing_zip:
            # Create request that points to existing shared ZIP
            new_request = cls.objects.create(
                user=user,
                retreat=retreat,
                is_shared=True,
                shared_zip_key=existing_zip.shared_zip_key,
                status='ready',
                file_size=existing_zip.file_size,
                download_url=existing_zip.download_url,
                s3_key=existing_zip.s3_key,
                expires_at=existing_zip.expires_at
            )
            
            # Extend lifecycle of the shared ZIP
            existing_zip.extend_lifecycle()
            logger.info(f"Created shared download request {new_request.id} using existing ZIP {existing_zip.shared_zip_key}")
            return new_request
        else:
            # Create request for new shared ZIP
            new_request = cls.objects.create(
                user=user,
                retreat=retreat,
                is_shared=True
            )
            logger.info(f"Created new shared ZIP request {new_request.id} for retreat {retreat.id}")
            return new_request

    def extend_lifecycle(self, days=2):
        """Extend the lifecycle of this ZIP by specified days"""
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=days)
        else:
            # Extend but cap at maximum of 14 days from now
            max_expiry = timezone.now() + timezone.timedelta(days=14)
            new_expiry = self.expires_at + timezone.timedelta(days=days)
            self.expires_at = min(new_expiry, max_expiry)
        
        self.save(update_fields=['expires_at'])
        logger.info(f"Extended lifecycle for download request {self.id} to {self.expires_at}")

    def record_download(self):
        """Record a download event and update popularity metrics"""
        self.download_count += 1
        self.last_accessed_at = timezone.now()
        
        # Calculate popularity score based on downloads and recency
        hours_since_creation = (timezone.now() - self.created_at).total_seconds() / 3600
        self.popularity_score = self.download_count / max(hours_since_creation, 1.0)
        
        self.save(update_fields=['download_count', 'last_accessed_at', 'popularity_score'])
        
        # Auto-extend lifecycle for popular ZIPs
        if self.download_count >= 3:  # Popular threshold
            self.extend_lifecycle(days=3)
        elif self.download_count >= 5:  # Very popular
            self.extend_lifecycle(days=5)
            
        logger.info(f"Recorded download for request {self.id} (count: {self.download_count}, popularity: {self.popularity_score:.2f})")

    def update_shared_zip_info(self, s3_key, download_url, file_size):
        """Update shared ZIP information when Lambda completes"""
        self.shared_zip_key = s3_key
        self.s3_key = s3_key
        self.download_url = download_url
        self.file_size = file_size
        self.save(update_fields=['shared_zip_key', 's3_key', 'download_url', 'file_size'])
        
        # Update all other requests waiting for this shared ZIP
        cls = self.__class__
        waiting_requests = cls.objects.filter(
            retreat=self.retreat,
            is_shared=True,
            status__in=['pending', 'processing'],
            shared_zip_key__isnull=True
        ).exclude(id=self.id)
        
        for request in waiting_requests:
            request.shared_zip_key = s3_key
            request.s3_key = s3_key
            request.download_url = download_url
            request.file_size = file_size
            request.status = 'ready'
            request.processing_completed_at = timezone.now()
            request.save(update_fields=[
                'shared_zip_key', 's3_key', 'download_url', 'file_size', 
                'status', 'processing_completed_at'
            ])
            
        logger.info(f"Updated {len(waiting_requests)} waiting requests with shared ZIP info")

    @classmethod
    def cleanup_expired(cls):
        """Clean up expired download requests"""
        expired_requests = cls.objects.filter(
            expires_at__lt=timezone.now()
        ).exclude(status='expired')
        
        for request in expired_requests:
            # Clean up S3 file if it exists
            if request.s3_key:
                try:
                    from utils.storage import RetreatMediaStorage
                    storage = RetreatMediaStorage()
                    storage.delete(request.s3_key)
                except Exception as e:
                    logger.error(f"Error cleaning up expired download file {request.s3_key}: {e}")
            
            # Mark as expired
            request.status = 'expired'
            request.save(update_fields=['status'])
        
        return expired_requests.count()


# Signal handlers for bulk deletions
@receiver(pre_delete, sender=Track)
def track_pre_delete_handler(sender, instance, **kwargs):
    """Store file information before track deletion for bulk operations"""
    if not hasattr(instance, '_files_to_cleanup'):
        instance._files_to_cleanup = {
            'audio_file': instance.audio_file.name if instance.audio_file else None,
            'transcript_file': instance.transcript_file.name if instance.transcript_file else None,
            'session': instance.session,
        }


@receiver(post_delete, sender=Track)
def track_post_delete_handler(sender, instance, **kwargs):
    """Clean up S3 files after track deletion for bulk operations"""
    if not hasattr(instance, '_files_to_cleanup'):
        return
        
    import logging
    logger = logging.getLogger(__name__)
    
    files_info = instance._files_to_cleanup
    
    try:
        from utils.storage import RetreatMediaStorage
        storage = RetreatMediaStorage()
        
        if files_info['audio_file']:
            logger.info(f"Deleting S3 audio file (bulk): {files_info['audio_file']}")
            storage.delete(files_info['audio_file'])
            
        if files_info['transcript_file']:
            logger.info(f"Deleting S3 transcript file (bulk): {files_info['transcript_file']}")
            storage.delete(files_info['transcript_file'])
            
    except Exception as e:
        logger.error(f"Error cleaning up S3 files for track (bulk operation): {str(e)}")


@receiver(pre_delete, sender=Session) 
def session_pre_delete_handler(sender, instance, **kwargs):
    """Store track information before session deletion for bulk operations"""
    if not hasattr(instance, '_tracks_to_cleanup'):
        instance._tracks_to_cleanup = []
        for track in instance.tracks.all():
            instance._tracks_to_cleanup.append({
                'audio_file': track.audio_file.name if track.audio_file else None,
                'transcript_file': track.transcript_file.name if track.transcript_file else None,
            })


@receiver(pre_delete, sender=Retreat)
def retreat_pre_delete_handler(sender, instance, **kwargs):
    """Store all file information before retreat deletion for bulk operations"""
    if not hasattr(instance, '_files_to_cleanup'):
        instance._files_to_cleanup = []
        
        # Collect all files from all sessions and tracks
        for session in instance.sessions.all():
            for track in session.tracks.all():
                if track.audio_file:
                    instance._files_to_cleanup.append(track.audio_file.name)
                if track.transcript_file:
                    instance._files_to_cleanup.append(track.transcript_file.name)
        
        # Include retreat image
        if instance.image:
            instance._files_to_cleanup.append(instance.image.name)
        
        # Store folder name for complete cleanup
        start_date = instance.start_date.strftime('%Y.%m.%d')
        end_date = instance.end_date.strftime('%d') if instance.end_date else start_date.split('.')[-1]
        folder_parts = [f"{start_date}-{end_date}"]
        
        if instance.groups.exists():
            folder_parts.append(instance.groups.first().name)
        if instance.places.exists():
            place_abbrevs = [place.abbreviation for place in instance.places.all()]
            folder_parts.append(' + '.join(place_abbrevs))
        if instance.teachers.exists():
            teacher_abbrevs = [teacher.abbreviation for teacher in instance.teachers.all()]
            folder_parts.append(' + '.join(teacher_abbrevs))
            
        instance._retreat_folder = ' - '.join(folder_parts)


@receiver(post_delete, sender=Retreat)
def retreat_post_delete_handler(sender, instance, **kwargs):
    """Clean up entire S3 retreat folder after deletion"""
    if not hasattr(instance, '_files_to_cleanup'):
        return
        
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from utils.storage import RetreatMediaStorage
        storage = RetreatMediaStorage()
        
        # Delete individual files
        for file_name in instance._files_to_cleanup:
            if file_name:
                logger.info(f"Deleting S3 file (bulk retreat): {file_name}")
                storage.delete(file_name)
        
        # Delete entire retreat folder
        if hasattr(instance, '_retreat_folder'):
            import boto3
            from django.conf import settings
            
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            
            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name, Prefix=f"{instance._retreat_folder}/")
            
            for page in pages:
                if 'Contents' in page:
                    objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects_to_delete:
                        s3_client.delete_objects(
                            Bucket=bucket_name,
                            Delete={'Objects': objects_to_delete}
                        )
                        logger.info(f"Deleted {len(objects_to_delete)} objects from {instance._retreat_folder}/ (bulk)")
                        
    except Exception as e:
        logger.error(f"Error cleaning up S3 files for retreat (bulk operation): {str(e)}")