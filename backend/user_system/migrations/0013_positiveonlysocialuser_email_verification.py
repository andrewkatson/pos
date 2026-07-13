from django.db import migrations, models


def mark_existing_users_verified(apps, schema_editor):
    """Accounts created before email verification existed are grandfathered in;
    only accounts registered after this deploy must verify their address.

    The column default below is already True, so existing rows are verified when
    the field is added; this makes the grandfathering explicit and independent of
    that default. Filtering to False rows keeps it a no-op in practice instead
    of rewriting the whole table during deploy."""
    user_model = apps.get_model('user_system', 'PositiveOnlySocialUser')
    user_model.objects.filter(email_verified=False).update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0012_appeal_unique_appeal_per_post_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='email_verified',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='email_verification_token',
            field=models.TextField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='positiveonlysocialuser',
            name='email_verification_token_expires',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        migrations.RunPython(mark_existing_users_verified, migrations.RunPython.noop),
    ]
