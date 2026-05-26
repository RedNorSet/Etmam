"""
Migration: make Milestone global.
- Drops per-project columns (project_id, status, type) via RemoveField so state is clean for seeding.
- Drops template_id (not in Django model) via RunSQL.
- Adds order + is_active.
- Seeds 5 default objectives.
Note: start_date already exists in the DB — declared via SeparateDatabaseAndState.
"""
from django.db import migrations, models


DEFAULT_MILESTONES = [
    {
        'order': 1,
        'title': 'Project Proposal',
        'description': (
            'Submit the initial project proposal document, including problem statement, '
            'objectives, methodology, and expected outcomes.'
        ),
    },
    {
        'order': 2,
        'title': 'Literature Review',
        'description': (
            'Deliver a comprehensive literature review covering relevant research, '
            'technologies, and prior work related to the project.'
        ),
    },
    {
        'order': 3,
        'title': 'Design & Architecture',
        'description': (
            'Submit the system design document including architecture diagrams, '
            'data models, and technology stack decisions.'
        ),
    },
    {
        'order': 4,
        'title': 'Prototype / Mid-Review Deliverable',
        'description': (
            'Present a working prototype or mid-review deliverable demonstrating '
            'core functionality. Includes a progress report.'
        ),
    },
    {
        'order': 5,
        'title': 'Final Submission',
        'description': (
            'Submit the completed project including source code, final report, '
            'documentation, and any required presentation materials.'
        ),
    },
]


def seed_defaults(apps, schema_editor):
    Milestone = apps.get_model('milestones', 'Milestone')
    for m in DEFAULT_MILESTONES:
        Milestone.objects.create(
            order=m['order'],
            title=m['title'],
            description=m['description'],
            weight=20,
            is_active=True,
        )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('milestones', '0001_initial'),
        ('projects',   '0001_initial'),
    ]

    operations = [
        # 1. Wipe linked data and milestones safely
        migrations.RunSQL(
            sql='''
                DO $$ BEGIN
                  IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='submissions_submissionfile') THEN
                    DELETE FROM submissions_submissionfile;
                  END IF;
                  IF EXISTS (SELECT FROM pg_tables WHERE schemaname='public' AND tablename='submissions_submission') THEN
                    DELETE FROM submissions_submission;
                  END IF;
                END $$;
                DELETE FROM milestones_milestone;
                ALTER TABLE milestones_milestone DROP COLUMN IF EXISTS template_id;
                ALTER TABLE milestones_milestone DROP COLUMN IF EXISTS project_id;
                ALTER TABLE milestones_milestone DROP COLUMN IF EXISTS status;
                ALTER TABLE milestones_milestone DROP COLUMN IF EXISTS type;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # 2. Sync Django state: remove fields that are now gone from DB
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='milestone', name='project'),
                migrations.RemoveField(model_name='milestone', name='status'),
                migrations.RemoveField(model_name='milestone', name='type'),
            ],
            database_operations=[],
        ),

        # 3. Add new columns (IF NOT EXISTS via raw SQL to be safe)
        migrations.RunSQL(
            sql='''
                ALTER TABLE milestones_milestone ADD COLUMN IF NOT EXISTS start_date date;
                ALTER TABLE milestones_milestone ADD COLUMN IF NOT EXISTS "order" integer NOT NULL DEFAULT 0;
                ALTER TABLE milestones_milestone ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
                ALTER TABLE milestones_milestone ALTER COLUMN due_date DROP NOT NULL;
            ''',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # 4. Sync Django state for new fields
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(model_name='milestone', name='start_date', field=models.DateField(null=True, blank=True)),
                migrations.AddField(model_name='milestone', name='order', field=models.PositiveIntegerField(default=0)),
                migrations.AddField(model_name='milestone', name='is_active', field=models.BooleanField(default=True)),
                migrations.AlterField(model_name='milestone', name='due_date', field=models.DateField(null=True, blank=True)),
            ],
            database_operations=[],
        ),

        # 5. Update ordering meta
        migrations.AlterModelOptions(
            name='milestone',
            options={'ordering': ['order', 'due_date']},
        ),

        # 6. Seed 5 default milestones
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
