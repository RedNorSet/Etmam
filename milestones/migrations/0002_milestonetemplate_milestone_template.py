# Generated manually for universal milestone templates.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('milestones', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MilestoneTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('type', models.CharField(choices=[('regular', 'Regular'), ('mid', 'Mid Review'), ('final', 'Final Review')], default='regular', max_length=20)),
                ('default_weight', models.PositiveIntegerField(default=10, help_text='% contribution to final grade')),
                ('default_due_offset_days', models.PositiveIntegerField(default=14, help_text='Days after project creation')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['type', 'title'],
            },
        ),
        migrations.AddField(
            model_name='milestone',
            name='template',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='milestones', to='milestones.milestonetemplate'),
        ),
        migrations.AddConstraint(
            model_name='milestone',
            constraint=models.UniqueConstraint(fields=('project', 'template'), name='unique_project_milestone_template'),
        ),
    ]
