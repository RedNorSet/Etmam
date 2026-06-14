from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_project_reviewers'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='hide_from_archive',
            field=models.BooleanField(default=False),
        ),
    ]
