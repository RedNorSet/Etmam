from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('submissions', '0005_add_component_grades')]
    operations = [
        migrations.AddField(
            model_name='submission',
            name='is_late',
            field=models.BooleanField(default=False),
        ),
    ]
