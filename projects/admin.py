from django.contrib import admin
from .models import Project, SupervisionRequest


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('title', 'team', 'supervisor', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('title', 'team__name')


@admin.register(SupervisionRequest)
class SupervisionRequestAdmin(admin.ModelAdmin):
    list_display = ('team', 'supervisor', 'status', 'created_at')
    list_filter  = ('status',)
