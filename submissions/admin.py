from django.contrib import admin
from .models import Submission, SubmissionFile


class SubmissionFileInline(admin.TabularInline):
    model = SubmissionFile
    extra = 0


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display  = ('milestone', 'submitted_by', 'version', 'status', 'review_score', 'is_latest', 'submitted_at')
    list_filter   = ('status', 'is_latest')
    search_fields = ('milestone__title', 'submitted_by__username', 'submitted_by__full_name')
    inlines       = [SubmissionFileInline]


@admin.register(SubmissionFile)
class SubmissionFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'submission', 'file_type', 'file_size', 'uploaded_at')
