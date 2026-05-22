from django.db import models
from django.conf import settings


class Meeting(models.Model):
    TYPES = [
        ('regular', 'Regular'),
        ('review',  'Review'),
        ('final',   'Final Defense'),
    ]
    project      = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                     related_name='meetings')
    scheduled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, related_name='scheduled_meetings')
    title        = models.CharField(max_length=200)
    datetime     = models.DateTimeField()
    location     = models.CharField(max_length=200, blank=True)
    type         = models.CharField(max_length=20, choices=TYPES, default='regular')
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['datetime']

    def __str__(self): return f"{self.title} — {self.datetime.strftime('%Y-%m-%d %H:%M')}"
