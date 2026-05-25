from django.contrib import admin
from .models import Milestone, MilestoneTemplate


@admin.register(MilestoneTemplate)
class MilestoneTemplateAdmin(admin.ModelAdmin):
    list_display  = ('title', 'type', 'default_due_offset_days', 'default_weight', 'is_active')
    list_filter   = ('type', 'is_active')
    search_fields = ('title',)


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display  = ('title', 'project', 'template', 'due_date', 'status', 'weight')
    list_filter   = ('status', 'template')
    search_fields = ('title', 'project__title')
    ordering      = ('due_date',)
