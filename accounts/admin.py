from django.contrib import admin
from .models import CustomUser, Follow, BlockedUser
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone


# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    CustomUser = get_user_model()
    list_display = ('id' ,'username', 'email', 'first_name', 'last_name', 'profile_picture', 'bio', 'location', 'created_at', 'updated_at', 'block_status')
    list_filter = ('is_blocked', 'created_at', 'updated_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'bio', 'location', 'profile_picture')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
        ('Block Management', {'fields': ('is_blocked', 'blocked_reason', 'blocked_date')}),
    )
    
    def block_status(self, obj):
        if obj.is_blocked:
            return format_html('<span style="color: red; font-weight: bold;">🔒 BLOCKED</span>')
        else:
            return format_html('<span style="color: green; font-weight: bold;">✓ Active</span>')
    block_status.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if change:  # Editing existing user
            original = CustomUser.objects.get(pk=obj.pk)
            # If status changed to blocked
            if not original.is_blocked and obj.is_blocked:
                obj.blocked_date = timezone.now()
                BlockedUser.objects.create(
                    user=obj,
                    blocked_by=request.user,
                    reason=obj.blocked_reason
                )
            # If status changed to unblocked
            elif original.is_blocked and not obj.is_blocked:
                BlockedUser.objects.filter(user=obj, is_active=True).update(
                    is_active=False,
                    unblocked_at=timezone.now()
                )
                obj.blocked_reason = ""
                obj.blocked_date = None
        
        super().save_model(request, obj, form, change)


@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'blocked_by', 'blocked_at', 'reason_preview', 'status')
    list_filter = ('is_active', 'blocked_at', 'unblocked_at')
    search_fields = ('user__username', 'user__email', 'reason')
    readonly_fields = ('blocked_at', 'unblocked_at')
    
    fieldsets = (
        ('Block Information', {'fields': ('user', 'blocked_by', 'reason')}),
        ('Timestamps', {'fields': ('blocked_at', 'unblocked_at')}),
        ('Status', {'fields': ('is_active',)}),
    )
    
    def reason_preview(self, obj):
        if obj.reason:
            preview = obj.reason[:50] + '...' if len(obj.reason) > 50 else obj.reason
            return preview
        return '-'
    reason_preview.short_description = 'Reason'
    
    def status(self, obj):
        if obj.is_active:
            return format_html('<span style="color: red; font-weight: bold;">🔒 ACTIVE</span>')
        else:
            return format_html('<span style="color: green;">✓ Unblocked</span>')
    status.short_description = 'Status'


admin.site.register(Follow)

