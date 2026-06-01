from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_project_hide_from_archive'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phase', models.PositiveSmallIntegerField(default=1)),
                ('phase_switched_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'System Configuration',
            },
        ),
        migrations.AddField(
            model_name='project',
            name='auto_assigned_supervisor',
            field=models.BooleanField(default=False),
        ),
    ]
