from django.contrib import admin
from .models import Meeting


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display  = ('title', 'project', 'type', 'datetime')
    list_filter   = ('type',)
    search_fields = ('title', 'project__title')
