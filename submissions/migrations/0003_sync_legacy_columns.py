"""
Migration: sync Django model state with legacy DB columns that already exist.
- supervisor_feedback and reviewer_feedback are NOT NULL with no default →
  first set DB default to '' so Django INSERTs don't fail.
- All other extra columns are nullable → just declare them in state.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0002_add_project_grade'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS supervisor_grade numeric(5,2);
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS supervisor_feedback text NOT NULL DEFAULT '';
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS supervisor_graded_by_id integer REFERENCES accounts_user(id) ON DELETE SET NULL;
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS supervisor_graded_at timestamp with time zone;
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS reviewer_grade numeric(5,2);
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS reviewer_feedback text NOT NULL DEFAULT '';
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS reviewer_graded_by_id integer REFERENCES accounts_user(id) ON DELETE SET NULL;
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS reviewer_graded_at timestamp with time zone;
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS review_score numeric(5,2);
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS reviewed_by_id integer REFERENCES accounts_user(id) ON DELETE SET NULL;
                ALTER TABLE submissions_submission ADD COLUMN IF NOT EXISTS reviewed_at timestamp with time zone;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(model_name='submission', name='supervisor_grade', field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                migrations.AddField(model_name='submission', name='supervisor_feedback', field=models.TextField(blank=True, default='')),
                migrations.AddField(model_name='submission', name='supervisor_graded_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='supervisor_graded_submissions', to=settings.AUTH_USER_MODEL)),
                migrations.AddField(model_name='submission', name='supervisor_graded_at', field=models.DateTimeField(blank=True, null=True)),
                migrations.AddField(model_name='submission', name='reviewer_grade', field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                migrations.AddField(model_name='submission', name='reviewer_feedback', field=models.TextField(blank=True, default='')),
                migrations.AddField(model_name='submission', name='reviewer_graded_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewer_graded_submissions', to=settings.AUTH_USER_MODEL)),
                migrations.AddField(model_name='submission', name='reviewer_graded_at', field=models.DateTimeField(blank=True, null=True)),
                migrations.AddField(model_name='submission', name='review_score', field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                migrations.AddField(model_name='submission', name='reviewed_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_submissions', to=settings.AUTH_USER_MODEL)),
                migrations.AddField(model_name='submission', name='reviewed_at', field=models.DateTimeField(blank=True, null=True)),
            ],
            database_operations=[],
        ),
    ]
