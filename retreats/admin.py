from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone
from django import forms
from unfold.admin import ModelAdmin, TabularInline
from unfold.widgets import UnfoldAdminCheckboxSelectMultiple
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import RetreatGroup, Retreat, Session, Track, RetreatParticipation, Place, Teacher


class RetreatAdminForm(forms.ModelForm):
    """Custom form for Retreat admin with checkboxes for groups, places, and teachers"""
    
    groups = forms.ModelMultipleChoiceField(
        queryset=RetreatGroup.objects.all(),
        widget=UnfoldAdminCheckboxSelectMultiple,
        required=False,
        label=''  # Remove the label since fieldset already has the title
    )
    
    places = forms.ModelMultipleChoiceField(
        queryset=Place.objects.all(),
        widget=UnfoldAdminCheckboxSelectMultiple,
        required=False,
        label=''
    )
    
    teachers = forms.ModelMultipleChoiceField(
        queryset=Teacher.objects.all(),
        widget=UnfoldAdminCheckboxSelectMultiple,
        required=False,
        label=''
    )
    
    class Meta:
        model = Retreat
        fields = '__all__'


class RetreatGroupResource(resources.ModelResource):
    """Resource for importing/exporting retreat groups"""
    
    class Meta:
        model = RetreatGroup
        fields = (
            'id', 'name', 'description'
        )


class RetreatResource(resources.ModelResource):
    """Resource for importing/exporting retreats"""
    
    class Meta:
        model = Retreat
        fields = (
            'id', 'name', 'description', 'start_date', 'end_date',
            'retreat_type', 'status', 'is_public', 'location'
        )


class SessionInline(TabularInline):
    """Inline for retreat sessions"""
    model = Session
    extra = 1
    fields = ('session_number', 'title', 'session_date', 'time_period')
    ordering = ['session_number']


class TrackInline(TabularInline):
    """Inline for session tracks"""
    model = Track
    extra = 1
    fields = ('track_number', 'title', 'language', 'duration_minutes')
    ordering = ['track_number']


class RetreatParticipationInline(TabularInline):
    """Inline for retreat participants"""
    model = RetreatParticipation
    extra = 0
    fields = ('user', 'status', 'registration_date')
    readonly_fields = ('registration_date',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(RetreatGroup)
class RetreatGroupAdmin(ModelAdmin):
    """Retreat group admin"""
    
    resource_class = RetreatGroupResource
    
    list_display = [
        'order', 'name', 'retreats_count', 'created_at'
    ]
    
    list_display_links = ['name']
    
    list_filter = [
        'created_at'
    ]
    
    search_fields = [
        'name', 'description'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name',
                'description',
                'order',
                'logo'
            )
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def retreats_count(self, obj):
        """Get count of retreats"""
        count = obj.retreats.count()
        if count > 0:
            url = reverse('admin:retreats_retreat_changelist') + f'?groups__id__exact={obj.id}'
            return format_html('<a href="{}">{} retiros</a>', url, count)
        return '0 retiros'
    
    retreats_count.short_description = _('Retreats')
    
    def get_fieldsets(self, request, obj=None):
        """Conditionally show order field only when there are multiple groups"""
        fieldsets = list(super().get_fieldsets(request, obj))
        
        # Count total groups
        groups_count = RetreatGroup.objects.count()
        
        # If there's only one group (or this is a new group and would be the first), 
        # don't show the order field
        if groups_count <= 1:
            # Remove order from the basic information fields
            basic_info_fields = list(fieldsets[0][1]['fields'])
            if 'order' in basic_info_fields:
                basic_info_fields.remove('order')
                fieldsets[0] = (fieldsets[0][0], {
                    'fields': tuple(basic_info_fields)
                })
        
        return fieldsets


@admin.register(Retreat)
class RetreatAdmin(ModelAdmin):
    """Retreat admin - Step-by-step creation"""
    
    form = RetreatAdminForm
    resource_class = RetreatResource
    # Remove inlines for step-by-step workflow
    # inlines = [SessionInline, RetreatParticipationInline]
    
    list_display = [
        'name', 'get_groups_display', 'get_status_badge', 'start_date', 'end_date',
        'sessions_count', 'get_completion_status', 'retreat_type', 'is_public'
    ]
    
    list_filter = [
        'status', 'retreat_type', 'is_public',
        'start_date', 'groups'
    ]
    
    search_fields = [
        'name', 'description', 'groups__name', 'location'
    ]
    
    date_hierarchy = 'start_date'
    
    readonly_fields = [
        'created_at', 'updated_at', 'participants_count', 'duration_days', 
        'sessions_count', 'get_next_steps'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name',
                'description',
            )
        }),
        (_('Groups'), {
            'fields': (
                'groups',
            ),
        }),
        (_('Places & Teachers'), {
            'fields': (
                'places',
                'teachers',
            ),
        }),
        (_('Schedule'), {
            'fields': (
                ('start_date', 'end_date'),
                'duration_days'
            )
        }),
        (_('Type and Status'), {
            'fields': (
                ('retreat_type', 'status'),
                'is_public'
            )
        }),
        (_('Content Progress'), {
            'fields': (
                'sessions_count',
                'get_next_steps',
            )
        }),
        (_('Participation'), {
            'fields': (
                'participants_count',
            )
        }),
        (_('Location'), {
            'fields': (
                'location',
                'address'
            )
        }),
        (_('Additional Information'), {
            'fields': (
                'image',
            ),
            'classes': ['collapse']
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def get_status_badge(self, obj):
        """Get colored status badge"""
        colors = {
            'draft': '#6c757d',
            'upcoming': '#007bff',
            'ongoing': '#28a745',
            'completed': '#6f42c1',
            'cancelled': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    get_status_badge.short_description = _('Status')
    get_status_badge.admin_order_field = 'status'
    
    def get_groups_display(self, obj):
        """Display retreat groups"""
        groups = obj.groups.all()
        if not groups:
            return '-'
        if len(groups) == 1:
            return groups[0].name
        return f"{groups[0].name} (+{len(groups)-1})"
    
    get_groups_display.short_description = _('Groups')
    get_groups_display.admin_order_field = 'groups__name'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).prefetch_related('groups').annotate(
            participant_count=Count('participants', filter=Q(participants__status__in=['registered', 'confirmed'])),
            session_count=Count('sessions')
        )
    
    def sessions_count(self, obj):
        """Get count of sessions with link to add more"""
        count = getattr(obj, 'session_count', obj.sessions.count())
        if count > 0:
            url = reverse('admin:retreats_session_changelist') + f'?retreat__id__exact={obj.id}'
            return format_html('<a href="{}">{} sessions</a>', url, count)
        return '0 sessions'
    
    sessions_count.short_description = _('Sessions')
    sessions_count.admin_order_field = 'session_count'
    
    def get_completion_status(self, obj):
        """Get completion status badge"""
        sessions = obj.sessions.count()
        tracks_total = sum(session.tracks.count() for session in obj.sessions.all())
        
        if sessions == 0:
            color = '#dc3545'  # Red
            text = 'No Sessions'
        elif tracks_total == 0:
            color = '#fd7e14'  # Orange
            text = 'No Tracks'
        else:
            color = '#28a745'  # Green
            text = f'{tracks_total} Tracks'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, text
        )
    
    get_completion_status.short_description = _('Content Status')
    
    def get_next_steps(self, obj):
        """Show next steps with enhanced styling"""
        sessions_count = obj.sessions.count()
        
        if sessions_count == 0:
            # First step: add sessions
            add_session_url = reverse('admin:retreats_session_add') + f'?retreat={obj.id}'
            return format_html(
                '<div style="background: linear-gradient(135deg, #e3f2fd 0%, #f0f8ff 100%); '
                'border: 2px solid #007cba; border-radius: 8px; padding: 16px; margin: 8px 0;">'
                '<div style="font-size: 16px; font-weight: 600; color: #007cba; margin-bottom: 8px;">🚀 Ready to Add Sessions</div>'
                '<div style="color: #666; margin-bottom: 12px;">Create your first session to start organizing content</div>'
                '<a href="{}" style="background: #007cba; color: white; padding: 10px 20px; '
                'border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">+ Add First Session</a>'
                '</div>',
                add_session_url
            )
        else:
            # Show session management links with better styling
            sessions_url = reverse('admin:retreats_session_changelist') + f'?retreat__id__exact={obj.id}'
            add_session_url = reverse('admin:retreats_session_add') + f'?retreat={obj.id}'
            
            # Count tracks and get first session for quick upload
            tracks_total = sum(session.tracks.count() for session in obj.sessions.all())
            first_session = obj.sessions.first()
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #e8f5e8 0%, #f0fff0 100%); '
                'border: 2px solid #28a745; border-radius: 8px; padding: 16px; margin: 8px 0;">'
                '<div style="font-size: 16px; font-weight: 600; color: #28a745; margin-bottom: 8px;">'
                '✅ {} sessions • {} tracks</div>'
                '<div style="margin-top: 12px;">'
                '<a href="{}" style="background: #28a745; color: white; padding: 8px 16px; margin: 4px 4px 0 0; '
                'border-radius: 4px; text-decoration: none; font-size: 14px; display: inline-block;">📂 Quick Upload</a>'
                '<a href="{}" style="background: #007cba; color: white; padding: 8px 16px; margin: 4px 4px 0 0; '
                'border-radius: 4px; text-decoration: none; font-size: 14px; display: inline-block;">📋 Manage Sessions</a>'
                '<a href="{}" style="background: #ffc107; color: #000; padding: 8px 16px; margin: 4px 0 0 0; '
                'border-radius: 4px; text-decoration: none; font-size: 14px; display: inline-block;">+ Add Session</a>'
                '</div></div>',
                sessions_count, tracks_total,
                reverse('retreats:bulk_upload_tracks', kwargs={'session_id': first_session.id}),
                sessions_url, add_session_url
            )
    
    get_next_steps.short_description = _('Next Steps')
    
    actions = ['mark_as_upcoming', 'mark_as_ongoing', 'mark_as_completed']
    
    def mark_as_upcoming(self, request, queryset):
        """Mark retreats as upcoming"""
        updated = queryset.update(status='upcoming')
        self.message_user(request, f"{updated} retiro(s) marcado(s) como próximo(s).")
    mark_as_upcoming.short_description = _("Mark as upcoming")
    
    def mark_as_ongoing(self, request, queryset):
        """Mark retreats as ongoing"""
        updated = queryset.update(status='ongoing')
        self.message_user(request, f"{updated} retiro(s) marcado(s) como em andamento.")
    mark_as_ongoing.short_description = _("Mark as ongoing")
    
    def mark_as_completed(self, request, queryset):
        """Mark retreats as completed"""
        updated = queryset.update(status='completed')
        self.message_user(request, f"{updated} retiro(s) marcado(s) como concluído(s).")
    mark_as_completed.short_description = _("Mark as completed")


@admin.register(Session)
class SessionAdmin(ModelAdmin):
    """Session admin - Manage tracks step by step"""
    
    # Remove inline for step-by-step workflow
    # inlines = [TrackInline]
    
    list_display = [
        'title', 'retreat', 'session_number', 'session_date', 'time_period',
        'tracks_count', 'get_track_status'
    ]
    
    list_filter = [
        'time_period', 'session_date', 'retreat__groups'
    ]
    
    search_fields = [
        'title', 'description', 'retreat__name'
    ]
    
    date_hierarchy = 'session_date'
    
    readonly_fields = ['created_at', 'updated_at', 'tracks_count', 'get_tracks_next_steps']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'retreat',
                'session_number',
                'title',
                'description'
            )
        }),
        (_('Schedule'), {
            'fields': (
                'session_date',
                'time_period'
            )
        }),
        (_('Tracks Management'), {
            'fields': (
                'tracks_count',
                'get_tracks_next_steps',
            )
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('retreat').prefetch_related('retreat__groups').annotate(
            track_count=Count('tracks')
        )
    
    def get_track_status(self, obj):
        """Get track status badge"""
        track_count = getattr(obj, 'track_count', obj.tracks.count())
        
        if track_count == 0:
            color = '#dc3545'  # Red
            text = 'No Tracks'
        elif track_count < 3:
            color = '#fd7e14'  # Orange
            text = f'{track_count} Track{"s" if track_count != 1 else ""}'
        else:
            color = '#28a745'  # Green
            text = f'{track_count} Tracks'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, text
        )
    
    get_track_status.short_description = _('Track Status')
    
    def get_tracks_next_steps(self, obj):
        """Show next steps for track management with enhanced styling"""
        track_count = obj.tracks.count()
        
        if track_count == 0:
            # First step: add tracks with prominent styling
            from django.urls import reverse
            bulk_upload_url = reverse('retreats:bulk_upload_tracks', kwargs={'session_id': obj.id})
            add_track_url = reverse('admin:retreats_track_add') + f'?session={obj.id}'
            return format_html(
                '<div style="background: linear-gradient(135deg, #fff8e1 0%, #fffbf0 100%); '
                'border: 3px dashed #ffc107; border-radius: 12px; padding: 20px; margin: 8px 0; text-align: center;">'
                '<div style="font-size: 32px; margin-bottom: 12px;">🎵</div>'
                '<div style="font-size: 18px; font-weight: 600; color: #e65100; margin-bottom: 8px;">Ready for Audio Files</div>'
                '<div style="color: #666; margin-bottom: 16px;">Drag & drop MP3 files to create tracks automatically</div>'
                '<div style="margin-top: 16px;">'
                '<a href="{}" style="background: #28a745; color: white; padding: 14px 28px; margin-right: 12px; '
                'border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">🚀 Start Upload</a>'
                '<a href="{}" style="background: #6c757d; color: white; padding: 10px 20px; '
                'border-radius: 6px; text-decoration: none; font-size: 14px; display: inline-block;">+ Single Track</a>'
                '</div>'
                '</div>',
                bulk_upload_url, add_track_url
            )
        else:
            # Show track management links with success styling
            from django.urls import reverse
            tracks_url = reverse('admin:retreats_track_changelist') + f'?session__id__exact={obj.id}'
            bulk_upload_url = reverse('retreats:bulk_upload_tracks', kwargs={'session_id': obj.id})
            add_track_url = reverse('admin:retreats_track_add') + f'?session={obj.id}'
            
            return format_html(
                '<div style="background: linear-gradient(135deg, #e8f5e8 0%, #f0fff0 100%); '
                'border: 2px solid #28a745; border-radius: 8px; padding: 16px; margin: 8px 0;">'
                '<div style="font-size: 16px; font-weight: 600; color: #28a745; margin-bottom: 8px;">'
                '✅ {} track{} uploaded</div>'
                '<div style="margin-top: 12px;">'
                '<a href="{}" style="background: #28a745; color: white; padding: 8px 16px; margin: 4px 4px 0 0; '
                'border-radius: 4px; text-decoration: none; font-size: 14px; display: inline-block;">📂 Add More Files</a>'
                '<a href="{}" style="background: #007cba; color: white; padding: 8px 16px; margin: 4px 4px 0 0; '
                'border-radius: 4px; text-decoration: none; font-size: 14px; display: inline-block;">🎵 Manage Tracks</a>'
                '<a href="{}" style="background: #6c757d; color: white; padding: 8px 16px; margin: 4px 0 0 0; '
                'border-radius: 4px; text-decoration: none; font-size: 14px; display: inline-block;">+ Add Track</a>'
                '</div></div>',
                track_count, "s" if track_count != 1 else "", bulk_upload_url, tracks_url, add_track_url
            )
    
    get_tracks_next_steps.short_description = _('Track Management')


@admin.register(Track)
class TrackAdmin(ModelAdmin):
    """Track admin - File upload with progress"""
    
    list_display = [
        'title', 'session', 'track_number', 'language',
        'duration_minutes', 'get_upload_status', 'file_size_mb'
    ]
    
    list_filter = [
        'language', 'session__retreat__groups'
    ]
    
    search_fields = [
        'title', 'description', 'session__title', 'session__retreat__name'
    ]
    
    readonly_fields = [
        'created_at', 'updated_at', 'file_size_mb', 'audio_file_url', 'transcript_file_url'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'session',
                'track_number',
                'title',
                'description'
            )
        }),
        (_('Content'), {
            'fields': (
                'language',
                'duration_minutes'
            )
        }),
        (_('Files'), {
            'fields': (
                'audio_file',
                'audio_file_url',
                'transcript_file',
                'transcript_file_url',
                'file_size',
                'file_size_mb'
            )
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def get_upload_status(self, obj):
        """Show upload status for files"""
        has_audio = bool(obj.audio_file)
        has_transcript = bool(obj.transcript_file)
        
        if has_audio and has_transcript:
            color = '#28a745'  # Green
            text = '📁 Complete'
        elif has_audio:
            color = '#fd7e14'  # Orange
            text = '🎵 Audio Only'
        elif has_transcript:
            color = '#17a2b8'  # Blue
            text = '📄 Transcript Only'
        else:
            color = '#dc3545'  # Red
            text = '❌ No Files'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, text
        )
    
    get_upload_status.short_description = _('Upload Status')
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'session', 'session__retreat'
        ).prefetch_related('session__retreat__groups')


@admin.register(RetreatParticipation)
class RetreatParticipationAdmin(ModelAdmin):
    """Retreat participation admin"""
    
    list_display = [
        'user', 'retreat', 'get_status_badge', 'registration_date'
    ]
    
    list_filter = [
        'status', 'registration_date',
        'retreat__groups', 'retreat__status'
    ]
    
    search_fields = [
        'user__username', 'user__email',
        'retreat__name', 'notes'
    ]
    
    date_hierarchy = 'registration_date'
    
    readonly_fields = [
        'registration_date', 'updated_at'
    ]
    
    fieldsets = (
        (_('Participation'), {
            'fields': (
                ('user', 'retreat'),
                'status',
                'registration_date'
            )
        }),
        (_('Notes'), {
            'fields': (
                'notes',
            ),
            'classes': ['collapse']
        }),
        (_('Metadata'), {
            'fields': ('updated_at',),
            'classes': ['collapse']
        }),
    )
    
    def get_status_badge(self, obj):
        """Get colored status badge"""
        colors = {
            'requested': '#6c757d',
            'registered': '#007bff',
            'confirmed': '#17a2b8',
            'attended': '#28a745',
            'completed': '#6f42c1',
            'cancelled': '#dc3545',
            'no_show': '#fd7e14'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    get_status_badge.short_description = _('Status')
    get_status_badge.admin_order_field = 'status'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user', 'retreat').prefetch_related('retreat__groups')
    
    actions = ['confirm_participation', 'cancel_participation']
    
    def confirm_participation(self, request, queryset):
        """Confirm participation"""
        updated = queryset.filter(status='registered').update(
            status='confirmed'
        )
        self.message_user(request, f"{updated} participação(ões) confirmada(s).")
    confirm_participation.short_description = _("Confirm participation")
    
    def cancel_participation(self, request, queryset):
        """Cancel participation"""
        updated = queryset.exclude(status='cancelled').update(status='cancelled')
        self.message_user(request, f"{updated} participação(ões) cancelada(s).")
    cancel_participation.short_description = _("Cancel participation")


@admin.register(Place)
class PlaceAdmin(ModelAdmin):
    """Place admin"""
    
    list_display = [
        'name', 'abbreviation', 'retreats_count', 'created_at'
    ]
    
    list_display_links = ['name']
    
    search_fields = [
        'name', 'abbreviation'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name',
                'abbreviation',
            )
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def retreats_count(self, obj):
        """Get count of retreats"""
        count = obj.retreats.count()
        if count > 0:
            url = reverse('admin:retreats_retreat_changelist') + f'?places__id__exact={obj.id}'
            return format_html('<a href="{}">{} retreat{}</a>', url, count, "s" if count != 1 else "")
        return '0 retreats'
    
    retreats_count.short_description = _('Retreats')


@admin.register(Teacher)
class TeacherAdmin(ModelAdmin):
    """Teacher admin"""
    
    list_display = [
        'name', 'abbreviation', 'retreats_count', 'created_at'
    ]
    
    list_display_links = ['name']
    
    search_fields = [
        'name', 'abbreviation'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name',
                'abbreviation',
            )
        }),
        (_('Metadata'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
    
    def retreats_count(self, obj):
        """Get count of retreats"""
        count = obj.retreats.count()
        if count > 0:
            url = reverse('admin:retreats_retreat_changelist') + f'?teachers__id__exact={obj.id}'
            return format_html('<a href="{}">{} retreat{}</a>', url, count, "s" if count != 1 else "")
        return '0 retreats'
    
    retreats_count.short_description = _('Retreats')