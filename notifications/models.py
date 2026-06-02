from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPES = [
        ('deadline', 'Deadline'),
        ('feedback', 'Feedback'),
        ('meeting',  'Meeting'),
        ('approval', 'Approval'),
        ('risk',     'Risk Alert'),
        ('invite',   'Team Invite'),
        ('general',  'General'),
    ]
    recipient  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='notifications')
    type       = models.CharField(max_length=20, choices=TYPES, default='general')
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    is_read    = models.BooleanField(default=False)
    link       = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self): return f"{self.recipient} — {self.title}"
