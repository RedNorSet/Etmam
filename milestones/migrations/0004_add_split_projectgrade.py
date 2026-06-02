from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_splits(apps, schema_editor):
    """Mark milestones 3 and 5 (by display order) as split."""
    Milestone = apps.get_model('milestones', 'Milestone')
    Milestone.objects.filter(order__in=[3, 5]).update(has_split=True)


class Migration(migrations.Migration):

    dependencies = [
        ('milestones', '0003_alter_milestone_created_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0002_project_reviewers'),
    ]

    operations = [
        # ── New Milestone fields ─────────────────────────────────────────────
        migrations.AddField(
            model_name='milestone',
            name='has_split',
            field=models.BooleanField(
                default=False,
                help_text='Divide this milestone into Report + Presentation grades',
            ),
        ),
        migrations.AddField(
            model_name='milestone',
            name='report_weight',
            field=models.PositiveIntegerField(
                default=50,
                help_text='% of this milestone allocated to Report',
            ),
        ),
        migrations.AddField(
            model_name='milestone',
            name='presentation_weight',
            field=models.PositiveIntegerField(
                default=50,
                help_text='% of this milestone allocated to Presentation',
            ),
        ),

        # ── ProjectGrade table ───────────────────────────────────────────────
        migrations.CreateModel(
            name='ProjectGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('component', models.CharField(
                    choices=[('single', 'Score'), ('report', 'Report'),
                             ('presentation', 'Presentation')],
                    default='single', max_length=20,
                )),
                ('score', models.DecimalField(decimal_places=2, max_digits=5,
                                              null=True, blank=True)),
                ('graded_at', models.DateTimeField(null=True, blank=True)),
                ('notes', models.TextField(blank=True, default='')),
                ('graded_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='given_milestone_grades',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('milestone', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='project_grades',
                    to='milestones.milestone',
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='milestone_grades',
                    to='projects.project',
                )),
            ],
            options={
                'unique_together': {('project', 'milestone', 'component')},
            },
        ),

        # ── Seed splits for milestones 3 & 5 ────────────────────────────────
        migrations.RunPython(seed_splits, migrations.RunPython.noop),
    ]
