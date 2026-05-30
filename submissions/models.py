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
    project      = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                     related_name='submissions', null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, related_name='submissions')
    grade        = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    version      = models.PositiveIntegerField(default=1)
    notes        = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status       = models.CharField(max_length=20, choices=STATUS, default='pending')
    is_latest    = models.BooleanField(default=True)

    # ── Supervisor grading (legacy columns — kept for DB compatibility) ──
    supervisor_grade      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    supervisor_feedback   = models.TextField(blank=True, default='')
    supervisor_graded_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name='supervisor_graded_submissions')
    supervisor_graded_at  = models.DateTimeField(null=True, blank=True)

    # ── Supervisor per-component grades (used when milestone has_split=True) ──
    supervisor_report_grade       = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    supervisor_presentation_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # ── Reviewer grading (legacy columns — kept for DB compatibility) ──
    reviewer_grade        = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reviewer_feedback     = models.TextField(blank=True, default='')
    reviewer_graded_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name='reviewer_graded_submissions')
    reviewer_graded_at    = models.DateTimeField(null=True, blank=True)

    # ── Generic review ──
    review_score  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reviewed_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='reviewed_submissions')
    reviewed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-version']

    def __str__(self): return f"{self.milestone.title} — v{self.version}"

    def save(self, *args, **kwargs):
        if self.pk is None:
            Submission.objects.filter(
                milestone=self.milestone, project=self.project
            ).update(is_latest=False)
            last = Submission.objects.filter(
                milestone=self.milestone, project=self.project
            ).order_by('-version').first()
            self.version = (last.version + 1) if last else 1
        super().save(*args, **kwargs)


class ReviewerGrade(models.Model):
    """One grade+feedback per reviewer per submission per component."""
    COMPONENT = [
        ('single',       'Single'),
        ('report',       'Report'),
        ('presentation', 'Presentation'),
    ]
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name='reviewer_grades')
    reviewer   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='given_reviewer_grades')
    component  = models.CharField(max_length=20, choices=COMPONENT, default='single')
    grade      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback   = models.TextField(blank=True, default='')
    graded_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('submission', 'reviewer', 'component')

    def __str__(self): return f'{self.reviewer} → {self.submission}: {self.grade}'


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
