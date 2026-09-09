from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Item
from stock.models import PendingStockTransaction

User = get_user_model()


class PendingStatusIntegrityTests(TestCase):
    """A requester must not be able to self-approve by editing ``status``."""

    def setUp(self):
        self.staff = User.objects.create_user("ps@x.com", "Staff", role="staff")
        self.item = Item.objects.create(item_name="Cable", unit="pcs", quantity=5)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_status_defaults_to_pending_on_create(self):
        res = self.client.post(
            "/api/pending-stock-transactions/",
            {"item": self.item.item_id, "type": "IN", "quantity": 2, "status": "approved"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")

    def test_requester_cannot_patch_their_row_to_approved(self):
        created = self.client.post(
            "/api/pending-stock-transactions/",
            {"item": self.item.item_id, "type": "IN", "quantity": 2},
            format="json",
        )
        pending_id = created.data["pending_id"]

        res = self.client.patch(
            f"/api/pending-stock-transactions/{pending_id}/",
            {"status": "approved"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "pending")

        pending = PendingStockTransaction.objects.get(pk=pending_id)
        self.assertEqual(pending.status, "pending")

    def test_approving_through_the_service_still_works(self):
        admin = User.objects.create_user("ps-a@x.com", "Admin", role="admin")
        created = self.client.post(
            "/api/pending-stock-transactions/",
            {"item": self.item.item_id, "type": "IN", "quantity": 2},
            format="json",
        )
        self.client.force_authenticate(admin)
        res = self.client.post(
            f"/api/pending-stock-transactions/{created.data['pending_id']}/approve/"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "approved")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 7)


class ItemListPaginationTests(TestCase):
    """The dropdowns on the Stock page must be able to load every item/room."""

    def setUp(self):
        self.admin = User.objects.create_user("e@x.com", "Admin", role="admin")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_item_list_can_be_widened_past_the_default_page(self):
        for i in range(61):
            Item.objects.create(item_name=f"Bulk {i:03d}", unit="pcs", quantity=1)

        default_page = self.client.get("/api/items/")
        self.assertEqual(len(default_page.data["results"]), 50)  # DefaultPagination.page_size

        wide = self.client.get("/api/items/?page_size=1000")
        self.assertEqual(wide.data["count"], len(wide.data["results"]))
        self.assertGreaterEqual(len(wide.data["results"]), 61)

    def test_limit_alias_is_honoured(self):
        for i in range(15):
            Item.objects.create(item_name=f"L {i:03d}", unit="pcs", quantity=1)
        res = self.client.get("/api/items/?limit=3")
        self.assertEqual(len(res.data["results"]), 3)
