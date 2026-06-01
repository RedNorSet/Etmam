from django.contrib import admin
from django.utils.html import format_html
from .models import Project, SupervisionRequest, SystemConfig


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    fields         = ('phase', 'phase_switched_at', 'phase2_auto_activate_info')
    readonly_fields = ('phase2_auto_activate_info',)

    def phase2_auto_activate_info(self, obj):
        from milestones.models import Milestone
        first = Milestone.objects.order_by('order', 'id').first()
        if first is None:
            return 'No milestones exist yet.'
        if first.start_date:
            return format_html(
                'Will auto-activate on <strong>{}</strong>'
                ' &mdash; linked to first milestone: &ldquo;{}&rdquo;',
                first.start_date.strftime('%b %d, %Y'),
                first.title,
            )
        return format_html(
            'No start date set on first milestone (&ldquo;{}&rdquo;).',
            first.title,
        )

    phase2_auto_activate_info.short_description = 'Phase 2 Auto-Activate Date'


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ('title', 'team', 'supervisor', 'status', 'created_at')
    list_filter   = ('status',)
    search_fields = ('title', 'team__name')


@admin.register(SupervisionRequest)
class SupervisionRequestAdmin(admin.ModelAdmin):
    list_display = ('team', 'supervisor', 'status', 'created_at')
    list_filter  = ('status',)
