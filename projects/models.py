from django.db import models
from django.conf import settings
from django.utils import timezone


class SystemConfig(models.Model):
    phase              = models.PositiveSmallIntegerField(default=1)  # 1 or 2
    phase_switched_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'System Configuration'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f'Phase {self.phase}'


class Project(models.Model):
    STATUS = [
        ('draft',     'Draft'),
        ('submitted', 'Submitted'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
        ('active',    'Active'),
        ('completed', 'Completed'),
    ]
    team             = models.OneToOneField('teams.Team', on_delete=models.CASCADE,
                                            related_name='project')
    supervisor       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='supervised_projects')
    reviewers        = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                              blank=True, related_name='reviewed_projects')
    title            = models.CharField(max_length=200)
    description      = models.TextField()
    objectives       = models.TextField(blank=True)
    status           = models.CharField(max_length=20, choices=STATUS, default='draft')
    submitted_at     = models.DateTimeField(null=True, blank=True)
    approved_at      = models.DateTimeField(null=True, blank=True)
    approved_by      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name='approved_projects')
    rejection_reason  = models.TextField(blank=True)
    hide_from_archive         = models.BooleanField(default=False)
    auto_assigned_supervisor  = models.BooleanField(default=False)
    created_at                = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.title

    def completion_percent(self):
        milestones = self.milestones.all()
        if not milestones.exists():
            return 0
        done = milestones.filter(status='approved').count()
        return int((done / milestones.count()) * 100)

    def is_at_risk(self):
        return self.milestones.filter(
            due_date__lt=timezone.now().date(),
            status__in=['pending', 'in_progress']
        ).exists()


class SupervisionRequest(models.Model):
    STATUS = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    team       = models.ForeignKey('teams.Team', on_delete=models.CASCADE,
                                   related_name='supervision_requests')
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='supervision_requests')
    title      = models.CharField(max_length=200)
    pitch      = models.TextField()
    status     = models.CharField(max_length=20, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'supervisor')
        ordering        = ['-created_at']

    def __str__(self): return f"{self.team} → {self.supervisor} ({self.status})"
