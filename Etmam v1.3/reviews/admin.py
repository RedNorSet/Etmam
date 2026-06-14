from django.contrib import admin
from .models import Grade, Feedback

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('project', 'type', 'supervisor_score', 'reviewer_score', 'final_score', 'letter_grade', 'graded_at')
    list_filter  = ('type',)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('project', 'given_by', 'created_at')
