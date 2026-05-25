from django.db import models
from django.conf import settings


class MilestoneTemplate(models.Model):
    TYPE = [
        ('regular', 'Regular'),
        ('mid',     'Mid Review'),
        ('final',   'Final Review'),
    ]

    title                   = models.CharField(max_length=200, unique=True)
    description             = models.TextField(blank=True)
    type                    = models.CharField(max_length=20, choices=TYPE, default='regular')
    default_weight          = models.PositiveIntegerField(default=10, help_text='% contribution to final grade')
    default_due_offset_days = models.PositiveIntegerField(default=14, help_text='Days after project creation')
    is_active               = models.BooleanField(default=True)
    created_by              = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                                null=True, blank=True)
    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['type', 'title']

    def __str__(self):
        return self.title


class Milestone(models.Model):
    TYPE = [
        ('regular', 'Regular'),
        ('mid',     'Mid Review'),
        ('final',   'Final Review'),
    ]
    STATUS = [
        ('pending',     'Pending'),
        ('in_progress', 'In Progress'),
        ('submitted',   'Submitted'),
        ('approved',    'Approved'),
        ('overdue',     'Overdue'),
    ]
    template    = models.ForeignKey(MilestoneTemplate, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='milestones')
    project     = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                    related_name='milestones')
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type        = models.CharField(max_length=20, choices=TYPE, default='regular')
    due_date    = models.DateField()
    status      = models.CharField(max_length=20, choices=STATUS, default='pending')
    weight      = models.PositiveIntegerField(default=10, help_text='% contribution to final grade')
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'template'],
                name='unique_project_milestone_template',
            ),
        ]

    def __str__(self): return f"{self.project.title} — {self.title}"

    def latest_submission(self):
        return self.submissions.filter(is_latest=True).first()
