from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ('username', 'full_name', 'email', 'role', 'department', 'can_review', 'is_active')
    list_filter   = ('role', 'department', 'is_active', 'can_review')
    search_fields = ('username', 'full_name', 'email', 'student_id')
    fieldsets     = UserAdmin.fieldsets + (
        ('GPMS Info', {'fields': ('role', 'full_name', 'student_id', 'department', 'avatar',
                                  'can_review', 'expertise', 'max_teams_supervise', 'max_teams_review', 'available')}),
    )
