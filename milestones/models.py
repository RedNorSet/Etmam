from django.db import models
from django.conf import settings


class Milestone(models.Model):
    """Global milestone / objective — shared across all projects."""
    title               = models.CharField(max_length=200)
    description         = models.TextField(blank=True)
    start_date          = models.DateField(null=True, blank=True)
    due_date            = models.DateField(null=True, blank=True)
    weight              = models.PositiveIntegerField(default=10, help_text='% contribution to final grade')
    order               = models.PositiveIntegerField(default=0)
    is_active           = models.BooleanField(default=True)
    # Split into Report + Presentation sub-components (e.g. milestones 3 & 5)
    has_split           = models.BooleanField(default=False, help_text='Divide this milestone into Report + Presentation grades')
    report_weight       = models.PositiveIntegerField(default=50, help_text='% of this milestone allocated to Report')
    presentation_weight = models.PositiveIntegerField(default=50, help_text='% of this milestone allocated to Presentation')
    created_by          = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                            null=True, blank=True, related_name='created_milestones')
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'due_date']

    def __str__(self): return self.title


class ProjectGrade(models.Model):
    """Grade given to a project for one milestone component (report, presentation, or single)."""
    COMPONENT_CHOICES = [
        ('single',       'Score'),
        ('report',       'Report'),
        ('presentation', 'Presentation'),
    ]
    project   = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                  related_name='milestone_grades')
    milestone = models.ForeignKey(Milestone, on_delete=models.CASCADE,
                                  related_name='project_grades')
    component = models.CharField(max_length=20, choices=COMPONENT_CHOICES, default='single')
    score     = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='given_milestone_grades')
    graded_at = models.DateTimeField(null=True, blank=True)
    notes     = models.TextField(blank=True, default='')

    class Meta:
        unique_together = [('project', 'milestone', 'component')]

    def __str__(self):
        return f'{self.project} — {self.milestone} ({self.component}): {self.score}'
