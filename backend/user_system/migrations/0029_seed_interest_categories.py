# Seeds the curated InterestCategory vocabulary (issues #446/#35) from
# constants.INTEREST_CATEGORY_CHOICES, the single source of truth. Idempotent
# (get_or_create keyed on slug), so re-running is harmless and adding a bucket
# later is just a new one-line seed migration. The name is kept in sync with the
# constant on every run so a relabel of an existing slug lands too.
from django.db import migrations

from user_system.constants import INTEREST_CATEGORY_CHOICES


def seed_interest_categories(apps, schema_editor):
    InterestCategory = apps.get_model('user_system', 'InterestCategory')
    for slug, name in INTEREST_CATEGORY_CHOICES:
        obj, created = InterestCategory.objects.get_or_create(
            slug=slug, defaults={'name': name})
        if not created and obj.name != name:
            obj.name = name
            obj.save(update_fields=['name'])


def unseed_interest_categories(apps, schema_editor):
    InterestCategory = apps.get_model('user_system', 'InterestCategory')
    InterestCategory.objects.filter(
        slug__in=[slug for slug, _ in INTEREST_CATEGORY_CHOICES]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user_system', '0028_interest_categories'),
    ]

    operations = [
        migrations.RunPython(seed_interest_categories, unseed_interest_categories),
    ]
