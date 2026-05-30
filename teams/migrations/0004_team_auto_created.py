from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0003_alter_team_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='auto_created',
            field=models.BooleanField(default=False),
        ),
    ]
