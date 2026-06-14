from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('milestones', '0006_add_guide_file')]
    operations = [
        migrations.AddField(
            model_name='milestone',
            name='allow_late_submissions',
            field=models.BooleanField(default=False),
        ),
    ]
