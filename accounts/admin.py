from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from unfold.admin import ModelAdmin, StackedInline
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import User, UserPreferences, UserActivity, UserGroupMembership


class UserResource(resources.ModelResource):
    """Resource for importing/exporting users"""
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'dharma_name',
            'subscription_status', 'subscription_plan', 'preferred_language',
            'is_active', 'is_staff', 'date_joined'
        )
        export_order = fields


class UserPreferencesInline(StackedInline):
    """Inline for user preferences"""
    model = UserPreferences
    extra = 0
    classes = ['collapse']
    fieldsets = (
        (_('Appearance'), {
            'fields': ('theme',)
        }),
        (_('Audio Settings'), {
            'fields': ('autoplay_next', 'download_quality', 'playback_speed')
        }),
        (_('Content Preferences'), {
            'fields': ('show_transcripts', 'preferred_session_length')
        }),
        (_('Notifications'), {
            'fields': ('session_reminders', 'reminder_time', 'retreat_notifications')
        }),
        (_('Privacy'), {
            'fields': ('profile_visibility',)
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin, ImportExportModelAdmin):
    """Enhanced User admin with Buddhist retreat features"""
    
    resource_class = UserResource
    inlines = [UserPreferencesInline]
    
    list_display = [
        'get_display_name', 'email', 'dharma_name', 'subscription_status',
        'is_active', 'last_login', 'date_joined'
    ]
    
    list_filter = [
        'subscription_status', 'subscription_plan', 'is_active', 'is_staff',
        'preferred_language', 'date_joined', 'last_login'
    ]
    
    search_fields = [
        'username', 'email', 'first_name', 'last_name', 'dharma_name'
    ]
    
    ordering = ['-date_joined']
    
    readonly_fields = [
        'date_joined', 'last_login', 'last_activity', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('username', 'password', 'email', 'is_verified')
        }),
        (_('Personal Information'), {
            'fields': (
                ('first_name', 'last_name'),
                'dharma_name',
                'birth_date',
                'bio',
                ('website', 'location'),
                'avatar'
            )
        }),
        (_('Subscription'), {
            'fields': (
                ('subscription_status', 'subscription_plan'),
                ('subscription_start_date', 'subscription_end_date')
            ),
            'classes': ['collapse']
        }),
        (_('Preferences'), {
            'fields': (
                'preferred_language',
                ('email_notifications', 'push_notifications')
            )
        }),
        (_('Contact Information'), {
            'fields': ('phone',),
            'classes': ['collapse']
        }),
        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions'
            ),
            'classes': ['collapse']
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined', 'last_activity'),
            'classes': ['collapse']
        }),
    )
    
    add_fieldsets = (
        (_('Basic Information'), {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        (_('Personal Information'), {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'dharma_name'),
        }),
    )
    
    def get_display_name(self, obj):
        """Get user's display name with avatar"""
        name = obj.get_display_name()
        if obj.avatar:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius: 50%; margin-right: 10px;">{} <span style="color: #666;">(@{})</span>',
                obj.avatar.url, name, obj.username
            )
        return format_html('{} <span style="color: #666;">(@{})</span>', name, obj.username)
    
    get_display_name.short_description = _('User')
    get_display_name.admin_order_field = 'username'
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related('preferences')
    
    actions = ['activate_users', 'deactivate_users', 'reset_passwords']
    
    def activate_users(self, request, queryset):
        """Activate selected users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} utilizador(es) ativado(s) com sucesso.")
    activate_users.short_description = _("Activate selected users")
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} utilizador(es) desativado(s) com sucesso.")
    deactivate_users.short_description = _("Deactivate selected users")


@admin.register(UserGroupMembership)
class UserGroupMembershipAdmin(ModelAdmin):
    """User group membership admin"""
    
    list_display = [
        'user', 'group', 'get_status_badge', 'requested_date',
        'confirmed_date', 'cancelled_date'
    ]
    
    list_filter = [
        'status', 'requested_date', 'group'
    ]
    
    search_fields = [
        'user__username', 'user__email', 'user__dharma_name',
        'group__name', 'notes'
    ]
    
    date_hierarchy = 'requested_date'
    
    readonly_fields = [
        'requested_date', 'confirmed_date', 'cancelled_date',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Membership'), {
            'fields': (
                ('user', 'group'),
                'status',
                'requested_date'
            )
        }),
        (_('Status Dates'), {
            'fields': (
                'confirmed_date',
                'cancelled_date'
            )
        }),
        (_('Notes'), {
            'fields': ('notes',),
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
            'requested': '#007bff',
            'confirmed': '#28a745',
            'cancelled': '#dc3545'
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
        return super().get_queryset(request).select_related('user', 'group')
    
    actions = ['confirm_memberships', 'cancel_memberships']
    
    def confirm_memberships(self, request, queryset):
        """Confirm selected memberships"""
        for membership in queryset.filter(status='requested'):
            membership.confirm_membership()
        self.message_user(request, "Memberships confirmadas com sucesso.")
    confirm_memberships.short_description = _("Confirm selected memberships")
    
    def cancel_memberships(self, request, queryset):
        """Cancel selected memberships"""
        for membership in queryset.exclude(status='cancelled'):
            membership.cancel_membership()
        self.message_user(request, "Memberships canceladas com sucesso.")
    cancel_memberships.short_description = _("Cancel selected memberships")


@admin.register(UserPreferences)
class UserPreferencesAdmin(ModelAdmin):
    """User preferences admin"""
    
    list_display = [
        'user', 'theme', 'preferred_session_length', 'session_reminders',
        'autoplay_next', 'profile_visibility'
    ]
    
    list_filter = [
        'theme', 'autoplay_next', 'session_reminders', 'retreat_notifications',
        'profile_visibility', 'download_quality'
    ]
    
    search_fields = ['user__username', 'user__email', 'user__dharma_name']
    
    fieldsets = (
        (_('User'), {
            'fields': ('user',)
        }),
        (_('Appearance'), {
            'fields': ('theme',)
        }),
        (_('Audio Settings'), {
            'fields': (
                'autoplay_next',
                'download_quality',
                'playback_speed'
            )
        }),
        (_('Content Preferences'), {
            'fields': (
                'show_transcripts',
                'preferred_session_length'
            )
        }),
        (_('Notifications'), {
            'fields': (
                'session_reminders',
                'reminder_time',
                'retreat_notifications'
            )
        }),
        (_('Privacy'), {
            'fields': ('profile_visibility',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user')


@admin.register(UserActivity)
class UserActivityAdmin(ModelAdmin):
    """User activity tracking admin"""
    
    list_display = [
        'user', 'activity_type', 'description', 'timestamp', 'ip_address'
    ]
    
    list_filter = [
        'activity_type', 'timestamp'
    ]
    
    search_fields = [
        'user__username', 'user__email', 'description', 'ip_address'
    ]
    
    readonly_fields = [
        'user', 'activity_type', 'description', 'metadata',
        'ip_address', 'user_agent', 'timestamp'
    ]
    
    ordering = ['-timestamp']
    
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        """Disable adding activities manually"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing activities"""
        return False
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('user')
    
    fieldsets = (
        (_('Activity Information'), {
            'fields': ('user', 'activity_type', 'description', 'timestamp')
        }),
        (_('Technical Details'), {
            'fields': ('ip_address', 'user_agent', 'metadata'),
            'classes': ['collapse']
        }),
    )