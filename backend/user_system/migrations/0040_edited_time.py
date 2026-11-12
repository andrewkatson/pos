from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0039_private_accounts'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='edited_time',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='comment',
            name='edited_time',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
