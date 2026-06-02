from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Remove the old FK reviewer field
        migrations.RemoveField(
            model_name='project',
            name='reviewer',
        ),
        # Add the new M2M reviewers field (max 2 enforced at application level)
        migrations.AddField(
            model_name='project',
            name='reviewers',
            field=models.ManyToManyField(
                blank=True,
                related_name='reviewed_projects',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
