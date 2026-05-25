from django.apps import AppConfig


class MilestonesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'milestones'

    def ready(self):
        from . import signals  # noqa: F401
