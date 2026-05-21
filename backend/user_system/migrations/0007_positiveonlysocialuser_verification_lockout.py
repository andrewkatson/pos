from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0006_remove_positiveonlysocialuser_reset_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='verification_failed_attempts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='verification_lockout_until',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
