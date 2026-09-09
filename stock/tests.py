from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Item, Room
from common.exceptions import DomainError
from reports.selectors import reconciliation_report
from stock.models import PendingStockTransaction, RoomItemHistory, StockTransaction
from stock.services import bulk_import_stock, transfer_item

User = get_user_model()


def _csv(text):
    return SimpleUploadedFile("import.csv", text.encode("utf-8"), content_type="text/csv")


class BulkImportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.lab = Room.objects.create(room_name="Lab 1", room_type="lab")
        self.cable = Item.objects.create(
            item_name="HDMI Cable", unit="pcs", quantity=5, opening_quantity=5, room=self.lab
        )
        self.mouse = Item.objects.create(
            item_name="Mouse", unit="pcs", quantity=2, opening_quantity=2
        )

    def test_imports_valid_rows_and_reports_bad_ones(self):
        csv_text = (
            "item_name,quantity,room,notes\n"
            "HDMI Cable,10,Lab 1,restock\n"
            "Mouse,3,,\n"
            "Nonexistent,4,,\n"
            "HDMI Cable,-2,Lab 1,bad qty\n"
        )
        batch = bulk_import_stock(file=_csv(csv_text), user=self.user, filename="import.csv")

        self.assertEqual(batch.total_rows, 4)
        self.assertEqual(batch.success_count, 2)
        self.assertEqual(batch.error_count, 2)

        self.cable.refresh_from_db()
        self.mouse.refresh_from_db()
        self.assertEqual(self.cable.quantity, 15)
        self.assertEqual(self.mouse.quantity, 5)

        self.assertEqual(StockTransaction.objects.filter(type="IN").count(), 2)
        statuses = {r["row"]: r["status"] for r in batch.report}
        self.assertEqual(statuses, {2: "ok", 3: "ok", 4: "error", 5: "error"})

    def test_import_keeps_ledger_balanced(self):
        bulk_import_stock(
            file=_csv("item_name,quantity\nHDMI Cable,7\n"), user=self.user
        )
        rows = {r["item_name"]: r for r in reconciliation_report()["rows"]}
        self.assertEqual(rows["HDMI Cable"]["discrepancy"], 0)

    def test_empty_file_is_rejected(self):
        with self.assertRaises(DomainError):
            bulk_import_stock(file=_csv(""), user=self.user)

    def test_ambiguous_item_name_without_room_is_an_error(self):
        Item.objects.create(item_name="HDMI Cable", unit="pcs", quantity=1)  # 2nd match
        batch = bulk_import_stock(
            file=_csv("item_name,quantity\nHDMI Cable,5\n"), user=self.user
        )
        self.assertEqual(batch.success_count, 0)
        self.assertIn("several", batch.report[0]["message"])


class PendingStatusIntegrityTests(TestCase):
    """A requester must not be able to self-approve by editing ``status``."""

    def setUp(self):
        from rest_framework.test import APIClient

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


class ItemTransferTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.lab1 = Room.objects.create(room_name="Lab 1", room_type="lab")
        self.lab2 = Room.objects.create(room_name="Lab 2", room_type="lab")
        self.item = Item.objects.create(
            item_name="Projector", unit="pcs", quantity=10, opening_quantity=10, room=self.lab1
        )

    def test_full_move_reassigns_room_without_ledger_entry(self):
        history = transfer_item(item=self.item, to_room=self.lab2, user=self.user)

        self.item.refresh_from_db()
        self.assertEqual(self.item.room, self.lab2)
        self.assertEqual(self.item.quantity, 10)
        self.assertEqual(StockTransaction.objects.count(), 0)
        self.assertEqual(history.transfer_type, "full")
        self.assertEqual(history.source_qty_before, 10)
        self.assertEqual(history.source_qty_after, 0)
        self.assertEqual(history.dest_qty_after, 10)

    def test_partial_move_splits_item_and_keeps_both_balanced(self):
        history = transfer_item(
            item=self.item, to_room=self.lab2, quantity=4, user=self.user, remarks="loan"
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 6)
        self.assertEqual(self.item.room, self.lab1)

        dest = Item.objects.get(item_name="Projector", room=self.lab2)
        self.assertEqual(dest.quantity, 4)
        self.assertEqual(dest.opening_quantity, 0)

        self.assertEqual(history.transfer_type, "partial")
        self.assertEqual(history.source_qty_before, 10)
        self.assertEqual(history.source_qty_after, 6)
        self.assertEqual(history.dest_qty_before, 0)
        self.assertEqual(history.dest_qty_after, 4)
        self.assertEqual(history.dest_item, dest)

        self.assertEqual(
            StockTransaction.objects.filter(item=self.item, type="OUT").count(), 1
        )
        self.assertEqual(
            StockTransaction.objects.filter(item=dest, type="IN").count(), 1
        )

        rows = {r["item_id"]: r for r in reconciliation_report()["rows"]}
        self.assertEqual(rows[self.item.item_id]["discrepancy"], 0)
        self.assertEqual(rows[dest.item_id]["discrepancy"], 0)

    def test_partial_move_merges_into_existing_sibling(self):
        existing = Item.objects.create(
            item_name="Projector", unit="pcs", quantity=3, opening_quantity=3, room=self.lab2
        )
        transfer_item(item=self.item, to_room=self.lab2, quantity=5, user=self.user)

        existing.refresh_from_db()
        self.assertEqual(existing.quantity, 8)
        self.assertEqual(Item.objects.filter(item_name="Projector", room=self.lab2).count(), 1)

    def test_cannot_transfer_more_than_in_stock(self):
        with self.assertRaises(DomainError):
            transfer_item(item=self.item, to_room=self.lab2, quantity=99, user=self.user)

    def test_cannot_transfer_to_same_room(self):
        with self.assertRaises(DomainError):
            transfer_item(item=self.item, to_room=self.lab1, quantity=1, user=self.user)

    def test_transfer_logs_room_move_history(self):
        transfer_item(item=self.item, to_room=self.lab2, quantity=2, user=self.user)
        self.assertEqual(
            RoomItemHistory.objects.filter(
                from_room=self.lab1, to_room=self.lab2, transfer_type="partial"
            ).count(),
            1,
        )


class StockEndpointTests(TestCase):
    """The HTTP layer the Stock page actually calls: move-item, bulk-import,
    and list pagination wide enough to fill the dropdowns."""

    def setUp(self):
        self.admin = User.objects.create_user("e@x.com", "Admin", role="admin")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.lab1 = Room.objects.create(room_name="Lab 1", room_type="lab")
        self.lab2 = Room.objects.create(room_name="Lab 2", room_type="lab")
        self.item = Item.objects.create(
            item_name="Projector", unit="pcs", quantity=10, opening_quantity=10, room=self.lab1
        )

    # ---- Move Item over HTTP --------------------------------------------------

    def test_move_item_full_relocation_via_endpoint(self):
        res = self.client.post(
            "/api/stock/transfer/",
            {"item": self.item.item_id, "to_room": self.lab2.room_id},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["transfer_type"], "full")
        self.item.refresh_from_db()
        self.assertEqual(self.item.room_id, self.lab2.room_id)
        self.assertEqual(self.item.quantity, 10)

    def test_move_item_partial_split_via_endpoint(self):
        res = self.client.post(
            "/api/stock/transfer/",
            {"item": self.item.item_id, "to_room": self.lab2.room_id, "quantity": 4},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["transfer_type"], "partial")
        self.assertEqual(res.data["source_qty_after"], 6)
        self.assertEqual(res.data["dest_qty_after"], 4)

    def test_move_item_rejects_bad_input_with_400(self):
        res = self.client.post(
            "/api/stock/transfer/",
            {"item": self.item.item_id, "to_room": self.lab1.room_id},  # same room
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    # ---- Bulk import over HTTP ---------------------------------------------------

    def _upload(self, text):
        f = SimpleUploadedFile("import.csv", text.encode("utf-8"), content_type="text/csv")
        return self.client.post("/api/stock/bulk-import/", {"file": f}, format="multipart")

    def test_bulk_import_partial_success_returns_201_with_report(self):
        res = self._upload(
            "item_name,quantity,room,notes\nProjector,5,Lab 1,restock\nGhost,3,,\n"
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["success_count"], 1)
        self.assertEqual(res.data["error_count"], 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 15)

    def test_bulk_import_all_rows_failing_returns_400_with_report(self):
        res = self._upload("item_name,quantity\nGhost,3\n")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["success_count"], 0)
        self.assertIn("report", res.data)

    def test_bulk_import_missing_file_is_400(self):
        res = self.client.post("/api/stock/bulk-import/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_bulk_import_template_download(self):
        res = self.client.get("/api/stock/bulk-import/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("item_name", res.content.decode())

    # ---- Pagination: dropdowns must be able to load every item/room ------------

    def test_item_list_can_be_widened_past_the_default_page(self):
        for i in range(60):
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
