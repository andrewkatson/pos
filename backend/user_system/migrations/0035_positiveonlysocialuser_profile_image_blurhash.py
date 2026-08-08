from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0034_commentreport_retracted_time_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='profile_image_blurhash',
            field=models.TextField(blank=True, default=None, null=True),
        ),
    ]
