from django.db import models
from django.conf import settings


class Submission(models.Model):
    STATUS = [
        ('pending',  'Pending'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('revision', 'Revision Needed'),
    ]
    milestone    = models.ForeignKey('milestones.Milestone', on_delete=models.CASCADE,
                                     related_name='submissions')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, related_name='submissions')
    version      = models.PositiveIntegerField(default=1)
    notes        = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status       = models.CharField(max_length=20, choices=STATUS, default='pending')
    is_latest    = models.BooleanField(default=True)

    class Meta:
        ordering = ['-version']

    def __str__(self): return f"{self.milestone.title} — v{self.version}"

    def save(self, *args, **kwargs):
        if self.pk is None:
            Submission.objects.filter(milestone=self.milestone).update(is_latest=False)
            last = Submission.objects.filter(
                milestone=self.milestone
            ).order_by('-version').first()
            self.version = (last.version + 1) if last else 1
        super().save(*args, **kwargs)


class SubmissionFile(models.Model):
    submission  = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='files')
    file        = models.FileField(upload_to='submissions/%Y/%m/')
    file_name   = models.CharField(max_length=255, blank=True)
    file_type   = models.CharField(max_length=100, blank=True)
    file_size   = models.PositiveIntegerField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return self.file_name or str(self.file)

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)
