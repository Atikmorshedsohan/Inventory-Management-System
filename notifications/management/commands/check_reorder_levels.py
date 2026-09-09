"""Scan every item and raise / clear reorder alerts.

Run manually or from a scheduler (cron, Task Scheduler)::

    python manage.py check_reorder_levels
"""

from django.core.management.base import BaseCommand

from notifications.services import check_all_reorder_levels


class Command(BaseCommand):
    help = "Raise reorder alerts for items at or below their minimum quantity."

    def handle(self, *args, **options):
        raised = check_all_reorder_levels()
        self.stdout.write(
            self.style.SUCCESS(f"Reorder scan complete. {raised} new alert(s) raised.")
        )
