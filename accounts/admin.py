from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from unfold.admin import ModelAdmin, StackedInline
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from .models import User, UserPreferences, UserActivity, UserGroupMembership, DeviceActivation, MagicLinkToken, UserApprovalRequest


class UserResource(resources.ModelResource):
    """Resource for importing/exporting users"""
    
    class Meta:
        model = User
        fields = (
            'id', 'email', 'first_name', 'last_name', 'dharma_name',
            'preferred_language', 'is_active', 'is_staff', 'date_joined'
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
class UserAdmin(BaseUserAdmin, ModelAdmin, ImportExportModelAdmin):
    """Enhanced User admin with Buddhist retreat features"""
    
    # Use Unfold-specific forms for proper styling
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    
    resource_class = UserResource
    inlines = [UserPreferencesInline]
    
    list_display = [
        'get_display_name', 'email', 'dharma_name', 'is_active', 
        'last_login', 'date_joined'
    ]
    
    list_filter = [
        'is_active', 'is_staff', 'preferred_language', 'date_joined', 'last_login'
    ]
    
    search_fields = [
        'email', 'first_name', 'last_name', 'dharma_name'
    ]
    
    ordering = ['-date_joined']
    
    readonly_fields = [
        'date_joined', 'last_login', 'last_activity', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('email', 'password', 'is_verified')
        }),
        (_('Personal Information'), {
            'fields': (
                ('first_name', 'last_name'),
                'dharma_name'
            )
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
            'fields': ('email', 'password1', 'password2'),
        }),
        (_('Personal Information'), {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'dharma_name'),
        }),
    )
    
    def get_display_name(self, obj):
        """Get user's display name"""
        name = obj.get_display_name()
        return format_html('{} <span style="color: #666;">({})</span>', name, obj.email)
    
    get_display_name.short_description = _('User')
    get_display_name.admin_order_field = 'email'
    
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
        'user__email', 'user__dharma_name',
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


@admin.register(DeviceActivation)
class DeviceActivationAdmin(ModelAdmin):
    """Device activation admin"""
    
    list_display = [
        'user', 'device_name', 'device_type', 'get_status_badge', 
        'activated_at', 'last_used'
    ]
    
    list_filter = [
        'device_type', 'is_active', 'activated_at'
    ]
    
    search_fields = [
        'user__email', 'user__dharma_name',
        'device_name', 'device_fingerprint'
    ]
    
    date_hierarchy = 'activated_at'
    
    readonly_fields = [
        'id', 'activated_at', 'last_used', 'device_fingerprint', 
        'ip_address', 'user_agent'
    ]
    
    fieldsets = (
        (_('Device'), {
            'fields': (
                'user',
                ('device_name', 'device_type'),
                'device_fingerprint',
                'is_active'
            )
        }),
        (_('Activation Details'), {
            'fields': (
                'activated_at',
                'last_used',
                'ip_address'
            )
        }),
        (_('Technical'), {
            'fields': ('user_agent',),
            'classes': ['collapse']
        }),
    )
    
    def get_status_badge(self, obj):
        """Get colored status badge"""
        if obj.is_active:
            color = '#28a745'
            text = 'Active'
        else:
            color = '#dc3545'
            text = 'Deactivated'
            
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, text
        )
    
    get_status_badge.short_description = _('Status')
    get_status_badge.admin_order_field = 'is_active'
    
    actions = ['deactivate_devices', 'activate_devices']
    
    def deactivate_devices(self, request, queryset):
        """Deactivate selected devices"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} device(s) deactivated successfully.")
    deactivate_devices.short_description = _("Deactivate selected devices")
    
    def activate_devices(self, request, queryset):
        """Activate selected devices"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} device(s) activated successfully.")
    activate_devices.short_description = _("Activate selected devices")


@admin.register(MagicLinkToken)
class MagicLinkTokenAdmin(ModelAdmin):
    """Magic link token admin"""
    
    list_display = [
        'email', 'user', 'get_status_badge', 'created_at', 'expires_at', 'used_at'
    ]
    
    list_filter = [
        'is_used', 'created_at', 'expires_at', 'device_type'
    ]
    
    search_fields = [
        'email', 'user__email', 'token'
    ]
    
    date_hierarchy = 'created_at'
    
    readonly_fields = [
        'id', 'token', 'created_at', 'expires_at', 'used_at',
        'device_fingerprint', 'ip_address', 'user_agent'
    ]
    
    fieldsets = (
        (_('Token'), {
            'fields': (
                'user',
                'email',
                'token',
                ('created_at', 'expires_at'),
                'is_used',
                'used_at'
            )
        }),
        (_('Device Information'), {
            'fields': (
                ('device_name', 'device_type'),
                'device_fingerprint'
            )
        }),
        (_('Technical'), {
            'fields': (
                'ip_address',
                'user_agent'
            ),
            'classes': ['collapse']
        }),
    )
    
    def get_status_badge(self, obj):
        """Get colored status badge"""
        if obj.is_used:
            color = '#28a745'
            text = 'Used'
        elif obj.is_expired:
            color = '#dc3545'
            text = 'Expired'
        else:
            color = '#007bff'
            text = 'Valid'
            
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, text
        )
    
    get_status_badge.short_description = _('Status')
    
    def has_add_permission(self, request):
        """Disable manual creation of tokens"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Make tokens read-only"""
        return False


@admin.register(UserApprovalRequest)
class UserApprovalRequestAdmin(ModelAdmin):
    """User approval request admin with actions"""
    
    list_display = [
        'get_user_info', 'email', 'get_status_badge', 'requested_at', 
        'reviewed_by', 'reviewed_at'
    ]
    
    list_filter = [
        'status', 'requested_at', 'reviewed_at'
    ]
    
    search_fields = [
        'first_name', 'last_name', 'email', 'message'
    ]
    
    date_hierarchy = 'requested_at'
    
    readonly_fields = [
        'id', 'requested_at', 'reviewed_at', 'device_fingerprint',
        'ip_address', 'user_agent'
    ]
    
    fieldsets = (
        (_('User Request'), {
            'fields': (
                ('first_name', 'last_name'),
                'email',
                'message',
                'requested_at'
            )
        }),
        (_('Admin Review'), {
            'fields': (
                'status',
                'admin_message',
                ('reviewed_by', 'reviewed_at')
            )
        }),
        (_('Device Information'), {
            'fields': (
                ('device_name', 'device_type'),
                'device_fingerprint'
            ),
            'classes': ['collapse']
        }),
        (_('Technical'), {
            'fields': (
                'ip_address',
                'user_agent'
            ),
            'classes': ['collapse']
        }),
    )
    
    def get_user_info(self, obj):
        """Get formatted user name"""
        return format_html(
            '<strong>{} {}</strong>',
            obj.first_name, obj.last_name
        )
    
    get_user_info.short_description = _('Name')
    get_user_info.admin_order_field = 'first_name'
    
    def get_status_badge(self, obj):
        """Get colored status badge"""
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    
    get_status_badge.short_description = _('Status')
    get_status_badge.admin_order_field = 'status'
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        """Approve selected requests"""
        from .views import send_magic_link_email
        from .models import MagicLinkToken
        from django.conf import settings
        
        approved_count = 0
        for approval_request in queryset.filter(status='pending'):
            try:
                # Create the new user
                user = approval_request.approve(request.user)
                
                # Create a magic link token for the new user
                magic_token = MagicLinkToken.objects.create(
                    user=user,
                    email=approval_request.email,
                    device_fingerprint=approval_request.device_fingerprint,
                    device_name=approval_request.device_name,
                    device_type=approval_request.device_type,
                    ip_address=approval_request.ip_address,
                    user_agent=approval_request.user_agent
                )
                
                # Generate magic link
                magic_link = f"{settings.FRONTEND_URL}/activate/{magic_token.token}"
                
                # Send welcome email with magic link
                send_magic_link_email(user, magic_link, approval_request.device_name or approval_request.device_type or 'your device')
                
                approved_count += 1
                
            except Exception as e:
                self.message_user(request, f"Error approving {approval_request.email}: {e}", level='error')
        
        if approved_count:
            self.message_user(request, f"{approved_count} request(s) approved successfully. Welcome emails have been sent.")
    
    approve_requests.short_description = _("Approve selected requests")
    
    def reject_requests(self, request, queryset):
        """Reject selected requests"""
        rejected_count = 0
        for approval_request in queryset.filter(status='pending'):
            try:
                approval_request.reject(request.user, "Thank you for your interest. Unfortunately, we cannot approve your request at this time.")
                rejected_count += 1
            except Exception as e:
                self.message_user(request, f"Error rejecting {approval_request.email}: {e}", level='error')
        
        if rejected_count:
            self.message_user(request, f"{rejected_count} request(s) rejected.")
    
    reject_requests.short_description = _("Reject selected requests")


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
    
    search_fields = ['user__email', 'user__dharma_name']
    
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
        'user__email', 'description', 'ip_address'
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