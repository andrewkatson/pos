from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0038_post_comments_disabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='is_private',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='FollowRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('following', 'Following'), ('friend', 'Friend'), ('family', 'Family')], default='following', max_length=16)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user_from', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follow_requests_sent', to=settings.AUTH_USER_MODEL)),
                ('user_to', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follow_requests_received', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['user_to', '-id'], name='follow_request_owner_idx')],
                'constraints': [models.UniqueConstraint(fields=('user_from', 'user_to'), name='unique_follow_requests')],
            },
        ),
    ]
