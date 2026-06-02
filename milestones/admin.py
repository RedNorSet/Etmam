from django.contrib import admin
from .models import Milestone, ProjectGrade

@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display  = ('order', 'title', 'start_date', 'due_date', 'weight', 'has_split', 'is_active')
    list_filter   = ('is_active', 'has_split')
    search_fields = ('title', 'description')
    ordering      = ('order', 'due_date')

@admin.register(ProjectGrade)
class ProjectGradeAdmin(admin.ModelAdmin):
    list_display  = ('project', 'milestone', 'component', 'score', 'graded_by', 'graded_at')
    list_filter   = ('component', 'milestone')
    search_fields = ('project__title', 'milestone__title')
    ordering      = ('milestone__order', 'project__title')
