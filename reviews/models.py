from django.db import models
from django.conf import settings


class Grade(models.Model):
    TYPE = [
        ('mid',   'Mid Review'),
        ('final', 'Final Review'),
    ]
    project          = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                         related_name='grades')
    type             = models.CharField(max_length=10, choices=TYPE)
    supervisor_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reviewer_score   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    final_score      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    letter_grade     = models.CharField(max_length=5, blank=True)
    comments         = models.TextField(blank=True)
    graded_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('project', 'type')

    def __str__(self): return f"{self.project} — {self.get_type_display()} — {self.letter_grade}"


class Feedback(models.Model):
    project    = models.ForeignKey('projects.Project', on_delete=models.CASCADE,
                                   related_name='feedback')
    given_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name='feedback_given')
    submission = models.ForeignKey('submissions.Submission', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='feedback')
    comment    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"Feedback on {self.project} by {self.given_by}"
