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

    dependencies = [
        ('milestones', '0001_initial'),
        ('projects',   '0001_initial'),
    ]

    operations = [
        # 1. Wipe all per-project milestone rows first
        migrations.RunSQL(
            sql='DELETE FROM milestones_milestone;',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # 2. Drop template_id (not tracked by Django state — raw SQL only)
        migrations.RunSQL(
            sql='ALTER TABLE milestones_milestone DROP COLUMN IF EXISTS template_id;',
            reverse_sql=migrations.RunSQL.noop,
        ),

        # 3. Remove per-project fields via RemoveField (updates migration state)
        migrations.RemoveField(model_name='milestone', name='project'),
        migrations.RemoveField(model_name='milestone', name='status'),
        migrations.RemoveField(model_name='milestone', name='type'),

        # 4. Declare start_date in Django state only (column already in DB from old schema)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='milestone',
                    name='start_date',
                    field=models.DateField(null=True, blank=True),
                ),
            ],
            database_operations=[],   # column already exists — don't re-create it
        ),

        # 5. Add missing columns
        migrations.AddField(
            model_name='milestone',
            name='order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='milestone',
            name='is_active',
            field=models.BooleanField(default=True),
        ),

        # 6. Make due_date optional
        migrations.AlterField(
            model_name='milestone',
            name='due_date',
            field=models.DateField(null=True, blank=True),
        ),

        # 7. Update ordering meta
        migrations.AlterModelOptions(
            name='milestone',
            options={'ordering': ['order', 'due_date']},
        ),

        # 8. Seed 5 default objectives (state is now clean — no type/status/project)
        migrations.RunPython(seed_defaults, migrations.RunPython.noop),
    ]
