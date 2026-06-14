from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0001_initial'),
        ('projects',    '0001_initial'),
        ('milestones',  '0002_global_milestone'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='project',
            field=models.ForeignKey(
                'projects.Project',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='submissions',
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name='submission',
            name='grade',
            field=models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True),
        ),
    ]
