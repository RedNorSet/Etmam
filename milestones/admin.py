from django.contrib import admin
from .models import Milestone


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display  = ('title', 'project', 'due_date', 'status', 'weight')
    list_filter   = ('status',)
    search_fields = ('title', 'project__title')
    ordering      = ('due_date',)
