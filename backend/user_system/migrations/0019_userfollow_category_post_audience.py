from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0018_alter_twofactorchallenge_expires_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userfollow',
            name='category',
            field=models.CharField(
                choices=[('following', 'Following'), ('friend', 'Friend'), ('family', 'Family')],
                default='following',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='post',
            name='audience',
            field=models.CharField(
                choices=[('public', 'Public'), ('following', 'People I follow'), ('friends', 'Friends'), ('family', 'Family')],
                default='public',
                max_length=16,
            ),
        ),
    ]
