from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0005_positiveonlysocialuser_verification_token'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='positiveonlysocialuser',
            name='reset_id',
        ),
    ]
