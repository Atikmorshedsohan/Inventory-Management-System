from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from audit.filters import classify
from audit.models import AuditLog

User = get_user_model()


def _log(user, action, days_ago=0):
    entry = AuditLog.objects.create(user=user, action=action)
    if days_ago:
        AuditLog.objects.filter(pk=entry.pk).update(
            timestamp=timezone.now() - timedelta(days=days_ago)
        )
    return entry


class ActionClassificationTests(TestCase):
    def test_classifies_common_actions(self):
        cases = {
            "Stock IN: Cable x5": "stock",
            "Bulk stock import 'x.csv': 3 ok, 0 failed": "stock",
            "Transferred 2 x Projector from Lab 1 to Lab 2": "transfer",
            "Reconciled 'Camera': ledger adjusted by +7": "reconcile",
            "Approved requisition #4": "approve",
            "Rejected pending item: Chair. Reason: dup": "reject",
            "Issued requisition #4": "issue",
            "Returned requisition #4": "return",
            "Created item directly: Cable": "create",
            "Changed role for Bob (b@x.com): viewer -> manager": "role",
            "Commented on requisition #4": "comment",
            "Password reset completed for a@x.com": "auth",
        }
        for action, expected in cases.items():
            self.assertEqual(classify(action), expected, action)

    def test_unrecognised_action_falls_back_to_other(self):
        self.assertEqual(classify("Something entirely new"), "other")
        self.assertEqual(classify(""), "other")
        self.assertEqual(classify(None), "other")


class AuditLogFilterApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.other = User.objects.create_user("m@x.com", "Manager", role="manager")
        self.viewer = User.objects.create_user("v@x.com", "Viewer", role="viewer")

        _log(self.admin, "Stock IN: Cable x5")
        _log(self.admin, "Approved requisition #1")
        _log(self.other, "Created item directly: Chair")
        _log(self.other, "Stock OUT: Cable x2", days_ago=10)
        _log(self.admin, "Deleted something", days_ago=40)

        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @staticmethod
    def rows(response):
        """Result rows from a paginated or plain list response.

        ``data.get("results") or data`` is wrong: an empty ``results`` list is
        falsy and would fall through to the envelope dict.
        """
        data = response.data
        if isinstance(data, dict) and "results" in data:
            return data["results"]
        return data

    def test_filter_by_user(self):
        res = self.client.get("/api/audit-logs/", {"user": self.other.pk, "page_size": 100})
        self.assertEqual(res.status_code, 200)
        actions = [r["action"] for r in self.rows(res)]
        self.assertEqual(len(actions), 2)
        self.assertTrue(all("Cable x2" in a or "Chair" in a for a in actions))

    def test_filter_by_action_type(self):
        res = self.client.get("/api/audit-logs/", {"action_type": "stock", "page_size": 100})
        self.assertEqual(res.status_code, 200)
        rows = self.rows(res)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["action_type"] == "stock" for r in rows))

    def test_filter_by_date_range(self):
        today = timezone.localdate()
        res = self.client.get("/api/audit-logs/", {
            "date_from": (today - timedelta(days=15)).isoformat(),
            "date_to": today.isoformat(),
            "page_size": 100,
        })
        rows = self.rows(res)
        self.assertEqual(len(rows), 4)  # the 40-day-old row is excluded

    def test_date_from_and_to_are_inclusive(self):
        today = timezone.localdate()
        res = self.client.get("/api/audit-logs/", {
            "date_from": today.isoformat(), "date_to": today.isoformat(), "page_size": 100,
        })
        rows = self.rows(res)
        self.assertEqual(len(rows), 3)

    def test_filters_combine(self):
        res = self.client.get("/api/audit-logs/", {
            "user": self.admin.pk, "action_type": "stock", "page_size": 100,
        })
        rows = self.rows(res)
        self.assertEqual(len(rows), 1)
        self.assertIn("Stock IN", rows[0]["action"])

    def test_search_still_works_alongside_filters(self):
        res = self.client.get("/api/audit-logs/", {"search": "Chair", "page_size": 100})
        rows = self.rows(res)
        self.assertEqual(len(rows), 1)

    def test_serializer_exposes_action_type(self):
        res = self.client.get("/api/audit-logs/", {"page_size": 100})
        rows = self.rows(res)
        self.assertTrue(all("action_type" in r for r in rows))

    def test_action_types_endpoint_reports_counts(self):
        res = self.client.get("/api/audit-logs/action_types/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total"], 5)
        counts = {row["key"]: row["count"] for row in res.data["action_types"]}
        self.assertEqual(counts["stock"], 2)
        self.assertEqual(counts["approve"], 1)
        self.assertEqual(counts["create"], 1)

    def test_action_type_counts_are_disjoint_and_sum_to_total(self):
        # "Approved and created item" matches both the approve and create
        # patterns; classify() calls it an approval, so the filter must too.
        _log(self.admin, "Approved and created item: Desk")

        res = self.client.get("/api/audit-logs/action_types/")
        counts = {row["key"]: row["count"] for row in res.data["action_types"]}
        self.assertEqual(sum(counts.values()), res.data["total"])
        self.assertEqual(counts["approve"], 2)
        self.assertEqual(counts["create"], 1)  # not 2

    def test_filter_results_agree_with_the_displayed_action_type(self):
        _log(self.admin, "Approved and created item: Desk")
        for key in ("stock", "approve", "create", "other"):
            res = self.client.get("/api/audit-logs/", {"action_type": key, "page_size": 100})
            rows = self.rows(res)
            self.assertTrue(
                all(r["action_type"] == key for r in rows),
                f"{key} filter returned rows badged differently",
            )

    def test_action_types_respects_active_filters(self):
        res = self.client.get("/api/audit-logs/action_types/", {"user": self.other.pk})
        counts = {row["key"]: row["count"] for row in res.data["action_types"]}
        self.assertEqual(res.data["total"], 2)
        self.assertEqual(counts["stock"], 1)
        self.assertEqual(counts["approve"], 0)

    def test_export_returns_filtered_csv(self):
        res = self.client.get("/api/audit-logs/export/", {"action_type": "stock"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("attachment;", res["Content-Disposition"])

        body = res.content.decode("utf-8")
        self.assertIn("Stock IN: Cable x5", body)
        self.assertIn("Stock OUT: Cable x2", body)
        self.assertNotIn("Approved requisition", body)

    def test_viewers_are_denied(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/api/audit-logs/").status_code, 403)
        self.assertEqual(self.client.get("/api/audit-logs/action_types/").status_code, 403)
        self.assertEqual(self.client.get("/api/audit-logs/export/").status_code, 403)
