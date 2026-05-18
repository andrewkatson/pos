from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0003_userblock_positiveonlysocialuser_blocked_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='reset_token',
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='reset_token_expires',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
