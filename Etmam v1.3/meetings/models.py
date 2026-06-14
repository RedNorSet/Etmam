from datetime import timedelta

from django.conf import settings
from django.db import models

class Meeting(models.Model):
    IMPORTANCE = [
        ('low',    'Low'),
        ('medium', 'Medium'),
        ('high',   'High'),
    ]
    STATUSES = [
        ('pending',      'Pending'),
        ('confirmed',    'Confirmed'),
        ('rescheduling', 'Rescheduling'),
        ('declined',     'Declined'),
        ('cancelled',    'Cancelled'),
        ('completed',    'Completed'),
    ]

    project          = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                         related_name='meetings', null=True, blank=True)
    scheduled_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                         null=True, related_name='scheduled_meetings')
    title            = models.CharField(max_length=200)
    datetime         = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=30)
    location         = models.CharField(max_length=200, blank=True)
    importance       = models.CharField(max_length=20, choices=IMPORTANCE, default='medium')
    status           = models.CharField(max_length=20, choices=STATUSES, default='pending')
    notes            = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['datetime']

    @property
    def end_datetime(self):
        return self.datetime + timedelta(minutes=self.duration_minutes)

    def __str__(self):
        return f"{self.title} — {self.datetime.strftime('%Y-%m-%d %H:%M')}"

class MeetingParticipant(models.Model):
    RESPONSES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('proposed', 'Proposed reschedule'),
    ]
    meeting      = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='participants')
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name='meeting_invitations')
    response     = models.CharField(max_length=20, choices=RESPONSES, default='pending')
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('meeting', 'user')]
        ordering        = ['id']

    def __str__(self):
        return f"{self.user} → {self.meeting} ({self.response})"

class RescheduleProposal(models.Model):
    STATUSES = [
        ('open',     'Open'),
        ('chosen',   'Chosen'),
        ('rejected', 'Rejected'),
    ]
    meeting     = models.ForeignKey(Meeting, on_delete=models.CASCADE,
                                    related_name='reschedule_proposals')
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='meeting_reschedules')
    status      = models.CharField(max_length=20, choices=STATUSES, default='open')
    created_at  = models.DateTimeField(auto_now_add=True)
    decided_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Reschedule for {self.meeting_id} by {self.proposed_by} ({self.status})"

class ProposedSlot(models.Model):
    proposal = models.ForeignKey(RescheduleProposal, on_delete=models.CASCADE, related_name='slots')
    datetime = models.DateTimeField()
    selected = models.BooleanField(default=False)

    class Meta:
        ordering = ['datetime']

    def __str__(self):
        return self.datetime.strftime('%Y-%m-%d %H:%M')
