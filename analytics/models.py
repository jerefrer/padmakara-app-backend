from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class DailyUsageStats(models.Model):
    """
    Daily aggregated usage statistics for analytics dashboard
    """
    
    date = models.DateField(_('Date'), unique=True)
    
    # User Statistics
    total_users = models.PositiveIntegerField(_('Total Users'), default=0)
    active_users = models.PositiveIntegerField(_('Active Users'), default=0)
    new_users = models.PositiveIntegerField(_('New Users'), default=0)
    
    # Content Statistics
    tracks_played = models.PositiveIntegerField(_('Tracks Played'), default=0)
    total_listening_time = models.PositiveIntegerField(_('Total Listening Time (minutes)'), default=0)
    pdfs_opened = models.PositiveIntegerField(_('PDFs Opened'), default=0)
    bookmarks_created = models.PositiveIntegerField(_('Bookmarks Created'), default=0)
    highlights_created = models.PositiveIntegerField(_('Highlights Created'), default=0)
    downloads_requested = models.PositiveIntegerField(_('Downloads Requested'), default=0)
    
    # Platform Breakdown
    ios_sessions = models.PositiveIntegerField(_('iOS Sessions'), default=0)
    android_sessions = models.PositiveIntegerField(_('Android Sessions'), default=0)
    web_sessions = models.PositiveIntegerField(_('Web Sessions'), default=0)
    
    # Engagement Metrics
    average_session_duration = models.PositiveIntegerField(_('Average Session Duration (minutes)'), default=0)
    completion_rate = models.FloatField(_('Completion Rate (%)'), default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Daily Usage Stats')
        verbose_name_plural = _('Daily Usage Stats')
        ordering = ['-date']

    def __str__(self):
        return f"Usage Stats for {self.date}"

    @classmethod
    def get_or_create_today(cls):
        """Get or create today's stats record"""
        today = timezone.now().date()
        stats, created = cls.objects.get_or_create(date=today)
        return stats


class PopularContent(models.Model):
    """
    Track popular content for recommendations and analytics
    """
    
    track = models.OneToOneField('retreats.Track', on_delete=models.CASCADE, 
                                related_name='popularity_stats', verbose_name=_('Track'))
    
    # Play Statistics
    total_plays = models.PositiveIntegerField(_('Total Plays'), default=0)
    unique_listeners = models.PositiveIntegerField(_('Unique Listeners'), default=0)
    completion_rate = models.FloatField(_('Completion Rate (%)'), default=0.0,
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])
    average_listening_time = models.PositiveIntegerField(_('Average Listening Time (minutes)'), default=0)
    
    # Engagement Metrics
    bookmarks_count = models.PositiveIntegerField(_('Bookmarks Count'), default=0)
    highlights_count = models.PositiveIntegerField(_('Highlights Count'), default=0)
    downloads_count = models.PositiveIntegerField(_('Downloads Count'), default=0)
    notes_count = models.PositiveIntegerField(_('Notes Count'), default=0)
    
    # Rating and Feedback
    average_rating = models.FloatField(_('Average Rating'), default=0.0,
                                     validators=[MinValueValidator(0), MaxValueValidator(5)])
    total_ratings = models.PositiveIntegerField(_('Total Ratings'), default=0)
    
    # Time-based Metrics
    last_played = models.DateTimeField(_('Last Played'), null=True, blank=True)
    trending_score = models.FloatField(_('Trending Score'), default=0.0)
    
    # Metadata
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('Popular Content')
        verbose_name_plural = _('Popular Content')
        ordering = ['-trending_score', '-total_plays']

    def __str__(self):
        return f"Popularity stats for {self.track.title}"

    def calculate_trending_score(self):
        """Calculate trending score based on recent activity"""
        # Get recent plays (last 7 days)
        recent_date = timezone.now() - timedelta(days=7)
        
        # Get recent activity data
        from content.models import UserProgress
        recent_plays = UserProgress.objects.filter(
            track=self.track,
            last_played__gte=recent_date
        ).count()
        
        # Calculate score based on recent plays, completion rate, and engagement
        engagement_score = (self.bookmarks_count + self.highlights_count + self.downloads_count) * 0.1
        rating_score = self.average_rating * 20 if self.total_ratings > 0 else 0
        
        score = (recent_plays * 0.4) + (self.completion_rate * 0.3) + (engagement_score * 0.2) + (rating_score * 0.1)
        
        self.trending_score = round(score, 2)
        self.save(update_fields=['trending_score'])
        return self.trending_score

    def update_stats(self):
        """Update all statistics for this track"""
        from content.models import UserProgress, Bookmark, PDFHighlight, DownloadedContent, UserNotes
        
        # Basic play statistics
        progress_records = UserProgress.objects.filter(track=self.track)
        self.total_plays = progress_records.aggregate(total=models.Sum('play_count'))['total'] or 0
        self.unique_listeners = progress_records.count()
        
        # Completion rate
        if self.unique_listeners > 0:
            completed_count = progress_records.filter(is_completed=True).count()
            self.completion_rate = (completed_count / self.unique_listeners) * 100
        
        # Average listening time
        avg_time = progress_records.aggregate(avg=models.Avg('total_listening_time'))['avg']
        self.average_listening_time = round((avg_time or 0) / 60)  # Convert to minutes
        
        # Engagement metrics
        self.bookmarks_count = Bookmark.objects.filter(track=self.track).count()
        self.highlights_count = PDFHighlight.objects.filter(track=self.track).count()
        self.downloads_count = DownloadedContent.objects.filter(track=self.track).count()
        self.notes_count = UserNotes.objects.filter(track=self.track).count()
        
        # Last played
        last_progress = progress_records.order_by('-last_played').first()
        if last_progress:
            self.last_played = last_progress.last_played
        
        self.save()
        self.calculate_trending_score()


class UserEngagement(models.Model):
    """
    Track individual user engagement patterns and metrics
    """
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                               related_name='engagement_stats', verbose_name=_('User'))
    
    # Activity Metrics
    total_sessions = models.PositiveIntegerField(_('Total Sessions'), default=0)
    total_listening_time = models.PositiveIntegerField(_('Total Listening Time (minutes)'), default=0)
    average_session_duration = models.PositiveIntegerField(_('Average Session Duration (minutes)'), default=0)
    
    # Content Interaction
    tracks_started = models.PositiveIntegerField(_('Tracks Started'), default=0)
    tracks_completed = models.PositiveIntegerField(_('Tracks Completed'), default=0)
    bookmarks_created = models.PositiveIntegerField(_('Bookmarks Created'), default=0)
    highlights_created = models.PositiveIntegerField(_('Highlights Created'), default=0)
    notes_created = models.PositiveIntegerField(_('Notes Created'), default=0)
    
    # Engagement Levels
    engagement_score = models.FloatField(_('Engagement Score'), default=0.0)
    last_active_date = models.DateField(_('Last Active Date'), null=True, blank=True)
    current_streak = models.PositiveIntegerField(_('Current Streak (days)'), default=0)
    longest_streak = models.PositiveIntegerField(_('Longest Streak (days)'), default=0)
    
    # Preferences (learned from behavior)
    preferred_session_length = models.PositiveIntegerField(_('Preferred Session Length (minutes)'), default=30)
    most_active_hour = models.PositiveIntegerField(_('Most Active Hour'), null=True, blank=True,
                                                 validators=[MinValueValidator(0), MaxValueValidator(23)])
    preferred_content_type = models.CharField(_('Preferred Content Type'), max_length=50, blank=True)
    
    # Retreat Participation
    retreats_joined = models.PositiveIntegerField(_('Retreats Joined'), default=0)
    retreats_completed = models.PositiveIntegerField(_('Retreats Completed'), default=0)
    
    # Metadata
    updated_at = models.DateTimeField(_('Updated At'), auto_now=True)

    class Meta:
        verbose_name = _('User Engagement')
        verbose_name_plural = _('User Engagement')
        ordering = ['-engagement_score']

    def __str__(self):
        return f"Engagement stats for {self.user.get_display_name()}"

    def calculate_engagement_score(self):
        """Calculate overall engagement score (0-1000 scale)"""
        # Activity score (0-300 points)
        activity_score = min(self.total_sessions * 2, 300)
        
        # Completion score (0-300 points)
        completion_rate = (self.tracks_completed / max(self.tracks_started, 1)) * 100
        completion_score = min(completion_rate * 3, 300)
        
        # Streak score (0-200 points)
        streak_score = min(self.current_streak * 5, 200)
        
        # Interaction score (0-200 points)
        interaction_score = min((self.bookmarks_created + self.highlights_created + self.notes_created) * 2, 200)
        
        total_score = activity_score + completion_score + streak_score + interaction_score
        self.engagement_score = min(total_score, 1000)
        self.save(update_fields=['engagement_score'])
        return self.engagement_score

    def update_streak(self):
        """Update user's streak based on activity"""
        today = timezone.now().date()
        
        if self.last_active_date:
            days_diff = (today - self.last_active_date).days
            
            if days_diff == 1:
                # Consecutive day - increment streak
                self.current_streak += 1
                if self.current_streak > self.longest_streak:
                    self.longest_streak = self.current_streak
            elif days_diff > 1:
                # Streak broken
                self.current_streak = 1
            # If days_diff == 0, user already active today, no change needed
        else:
            # First activity
            self.current_streak = 1
            self.longest_streak = 1
        
        self.last_active_date = today
        self.save()

    def update_stats(self):
        """Update all engagement statistics"""
        from content.models import UserProgress, Bookmark, PDFHighlight, UserNotes
        from retreats.models import RetreatParticipation
        
        # Content statistics
        progress_records = UserProgress.objects.filter(user=self.user)
        self.tracks_started = progress_records.count()
        self.tracks_completed = progress_records.filter(is_completed=True).count()
        self.total_listening_time = progress_records.aggregate(
            total=models.Sum('total_listening_time')
        )['total'] or 0
        self.total_listening_time = round(self.total_listening_time / 60)  # Convert to minutes
        
        # Interaction statistics
        self.bookmarks_created = Bookmark.objects.filter(user=self.user).count()
        self.highlights_created = PDFHighlight.objects.filter(user=self.user).count()
        self.notes_created = UserNotes.objects.filter(user=self.user).count()
        
        # Retreat statistics
        participations = RetreatParticipation.objects.filter(user=self.user)
        self.retreats_joined = participations.count()
        self.retreats_completed = participations.filter(status='completed').count()
        
        self.save()
        self.calculate_engagement_score()


class ContentRecommendation(models.Model):
    """
    Store personalized content recommendations for users
    """
    
    RECOMMENDATION_TYPES = [
        ('popular', _('Popular Content')),
        ('similar', _('Similar Content')),
        ('continue', _('Continue Listening')),
        ('new', _('New Content')),
        ('curated', _('Curated by Teacher')),
        ('trending', _('Trending')),
        ('based_on_history', _('Based on Your History')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    track = models.ForeignKey('retreats.Track', on_delete=models.CASCADE, related_name='recommendations')
    
    # Recommendation Data
    recommendation_type = models.CharField(_('Recommendation Type'), max_length=20, 
                                         choices=RECOMMENDATION_TYPES)
    score = models.FloatField(_('Recommendation Score'), default=0.0)
    reason = models.TextField(_('Recommendation Reason'), blank=True)
    
    # Tracking
    shown_at = models.DateTimeField(_('Shown At'), null=True, blank=True)
    clicked_at = models.DateTimeField(_('Clicked At'), null=True, blank=True)
    is_dismissed = models.BooleanField(_('Is Dismissed'), default=False)
    
    # Metadata
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    expires_at = models.DateTimeField(_('Expires At'), null=True, blank=True)

    class Meta:
        verbose_name = _('Content Recommendation')
        verbose_name_plural = _('Content Recommendations')
        unique_together = ['user', 'track', 'recommendation_type']
        ordering = ['-score', '-created_at']

    def __str__(self):
        return f"{self.get_recommendation_type_display()} for {self.user.get_display_name()}: {self.track.title}"

    @property
    def is_clicked(self):
        return self.clicked_at is not None

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def mark_shown(self):
        """Mark recommendation as shown to user"""
        if not self.shown_at:
            self.shown_at = timezone.now()
            self.save(update_fields=['shown_at'])

    def mark_clicked(self):
        """Mark recommendation as clicked by user"""
        if not self.clicked_at:
            self.clicked_at = timezone.now()
            self.save(update_fields=['clicked_at'])


class SystemHealth(models.Model):
    """
    System health and performance monitoring
    """
    
    timestamp = models.DateTimeField(_('Timestamp'), auto_now_add=True)
    
    # Performance Metrics
    average_response_time = models.FloatField(_('Average Response Time (ms)'), default=0.0)
    error_rate = models.FloatField(_('Error Rate (%)'), default=0.0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)])
    uptime_percentage = models.FloatField(_('Uptime Percentage'), default=100.0,
                                        validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Resource Usage
    cpu_usage = models.FloatField(_('CPU Usage (%)'), default=0.0,
                                validators=[MinValueValidator(0), MaxValueValidator(100)])
    memory_usage = models.FloatField(_('Memory Usage (%)'), default=0.0,
                                   validators=[MinValueValidator(0), MaxValueValidator(100)])
    disk_usage = models.FloatField(_('Disk Usage (%)'), default=0.0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Database Metrics
    database_connections = models.PositiveIntegerField(_('Database Connections'), default=0)
    slow_queries_count = models.PositiveIntegerField(_('Slow Queries Count'), default=0)
    database_size_mb = models.FloatField(_('Database Size (MB)'), default=0.0)
    
    # Storage Metrics
    total_storage_used = models.PositiveBigIntegerField(_('Total Storage Used (bytes)'), default=0)
    audio_files_count = models.PositiveIntegerField(_('Audio Files Count'), default=0)
    transcript_files_count = models.PositiveIntegerField(_('Transcript Files Count'), default=0)
    
    # API Metrics
    api_requests_count = models.PositiveIntegerField(_('API Requests Count'), default=0)
    api_errors_count = models.PositiveIntegerField(_('API Errors Count'), default=0)

    class Meta:
        verbose_name = _('System Health')
        verbose_name_plural = _('System Health')
        ordering = ['-timestamp']

    def __str__(self):
        return f"System Health - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @property
    def storage_used_gb(self):
        """Get storage used in GB"""
        return round(self.total_storage_used / (1024**3), 2)

    @property
    def is_healthy(self):
        """Check if system is in healthy state"""
        return (
            self.error_rate < 5.0 and
            self.uptime_percentage > 95.0 and
            self.cpu_usage < 80.0 and
            self.memory_usage < 80.0 and
            self.disk_usage < 85.0
        )