from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0004_positiveonlysocialuser_reset_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='verification_token',
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='verification_token_expires',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
