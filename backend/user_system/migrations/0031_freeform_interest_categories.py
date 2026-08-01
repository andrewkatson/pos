# Widens UserFreeformInterest's single mapped bucket (the `category` FK) into a
# `categories` M2M (issues #446/#35), so a freeform term that maps to several
# buckets ("nature outdoors" -> nature, outdoors) keeps them all and the user's
# interest_categories union rebuilds deterministically from these rows.
#
# The operations are deliberately ordered Add -> copy -> Remove so both columns
# coexist while the data moves; the generated order (Remove first) would drop
# every existing mapping. In practice the table is created by 0028 in the same
# unmerged change, so a deployed database has no rows to lose — but a branch
# checkout that already migrated does, and the migration should be correct in
# isolation regardless.
from django.db import migrations, models


def copy_category_to_categories(apps, schema_editor):
    """Move each row's single mapped bucket into the new M2M."""
    UserFreeformInterest = apps.get_model('user_system', 'UserFreeformInterest')
    for row in UserFreeformInterest.objects.exclude(category__isnull=True).iterator():
        row.categories.add(row.category_id)


def copy_categories_to_category(apps, schema_editor):
    """Reverse: collapse the M2M back to one bucket.

    Inherently lossy (that is what reversing this migration means), so keep the
    lowest-id mapping as the representative — deterministic rather than
    arbitrary.
    """
    UserFreeformInterest = apps.get_model('user_system', 'UserFreeformInterest')
    for row in UserFreeformInterest.objects.iterator():
        first = row.categories.order_by('id').first()
        if first is not None:
            row.category_id = first.id
            row.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0030_merge_20260730_2140'),
    ]

    operations = [
        migrations.AddField(
            model_name='userfreeforminterest',
            name='categories',
            field=models.ManyToManyField(blank=True, related_name='+', to='user_system.interestcategory'),
        ),
        migrations.RunPython(copy_category_to_categories, copy_categories_to_category),
        migrations.RemoveField(
            model_name='userfreeforminterest',
            name='category',
        ),
    ]
