from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('projects', '0009_phase2_start_date')]
    operations = [
        migrations.AddField(
            model_name='systemconfig',
            name='pending_phase2_switch',
            field=models.BooleanField(default=False),
        ),
    ]
