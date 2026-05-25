from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Milestone


@receiver(post_save, sender=Milestone)
def create_submission_shell_for_milestone(sender, instance, created, **kwargs):
    if created:
        from submissions.models import ensure_submission_shell

        ensure_submission_shell(instance)
