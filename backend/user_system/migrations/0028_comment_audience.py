from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0027_post_image_blurhash'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='audience',
            field=models.CharField(
                choices=[('public', 'Public'), ('following', 'People I follow'), ('friends', 'Friends'), ('family', 'Family')],
                default='public',
                max_length=16,
            ),
        ),
    ]
