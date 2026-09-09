from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Item, Room
from notifications.models import Notification
from notifications.services import (
    check_all_reorder_levels,
    notify_reorder,
    resolve_reorder,
    sync_item_alert,
)

User = get_user_model()


class ReorderAlertTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.manager = User.objects.create_user("m@x.com", "Manager", role="manager")
        self.viewer = User.objects.create_user("v@x.com", "Viewer", role="viewer")
        self.room = Room.objects.create(room_name="Lab 1", room_type="lab")
        self.item = Item.objects.create(
            item_name="HDMI Cable", unit="pcs", quantity=3, min_quantity=10, room=self.room
        )

    def test_alert_raised_for_admins_and_managers_only(self):
        created = notify_reorder(self.item)
        self.assertEqual(len(created), 2)
        recipients = set(Notification.objects.values_list("recipient_id", flat=True))
        self.assertEqual(recipients, {self.admin.pk, self.manager.pk})
        self.assertEqual(Notification.objects.filter(recipient=self.viewer).count(), 0)

    def test_alert_is_deduped_per_open_notification(self):
        notify_reorder(self.item)
        notify_reorder(self.item)  # still low, alert already open
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 2)

    def test_alert_reopens_after_being_read(self):
        notify_reorder(self.item)
        Notification.objects.update(is_read=True)
        again = notify_reorder(self.item)
        self.assertEqual(len(again), 2)

    def test_sync_resolves_alert_when_stock_recovers(self):
        notify_reorder(self.item)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 2)

        self.item.quantity = 50
        self.item.save(update_fields=["quantity"])
        sync_item_alert(self.item)

        self.assertEqual(Notification.objects.filter(is_read=False).count(), 0)

    def test_no_alert_when_above_minimum(self):
        self.item.quantity = 25
        self.item.save(update_fields=["quantity"])
        self.assertEqual(notify_reorder(self.item), [])

    def test_check_all_reorder_levels_scans_every_item(self):
        Item.objects.create(item_name="Toner", unit="box", quantity=0, min_quantity=5)
        raised = check_all_reorder_levels()
        self.assertEqual(raised, 4)  # 2 low items x 2 recipients


class CrossAppNotificationTests(TestCase):
    """Every user-facing action now drops an in-app notification for the person
    who should hear about it - not just reorder alerts for admins."""

    def setUp(self):
        self.admin = User.objects.create_user("adm@x.com", "Admin", role="admin")
        self.viewer = User.objects.create_user("vw@x.com", "Viewer", role="viewer")
        self.staff = User.objects.create_user("st@x.com", "Staff", role="staff")
        self.lab1 = Room.objects.create(room_name="Lab 1", room_type="lab")
        self.lab2 = Room.objects.create(room_name="Lab 2", room_type="lab")
        self.item = Item.objects.create(
            item_name="Projector", unit="pcs", quantity=10, opening_quantity=10, room=self.lab1
        )

    def _notes(self, user, **filters):
        return Notification.objects.filter(recipient=user, **filters)

    def test_item_transfer_notifies_the_actor(self):
        from stock.services import transfer_item

        transfer_item(item=self.item, to_room=self.lab2, quantity=4, user=self.staff)
        note = self._notes(self.staff, category="transfer").first()
        self.assertIsNotNone(note)
        self.assertIn("Projector", note.title)

    def test_bulk_import_notifies_the_uploader(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from stock.services import bulk_import_stock

        f = SimpleUploadedFile("i.csv", b"item_name,quantity\nProjector,3\n", content_type="text/csv")
        bulk_import_stock(file=f, user=self.staff, filename="i.csv")
        self.assertTrue(self._notes(self.staff, category="import").exists())

    def test_pending_stock_decision_notifies_the_requester(self):
        from stock.models import PendingStockTransaction
        from stock.services import approve_pending_stock, reject_pending_stock

        p1 = PendingStockTransaction.objects.create(
            item=self.item, type="IN", quantity=2, requested_by=self.viewer
        )
        approve_pending_stock(pending=p1, approver=self.admin)
        p2 = PendingStockTransaction.objects.create(
            item=self.item, type="OUT", quantity=1, requested_by=self.viewer
        )
        reject_pending_stock(pending=p2, approver=self.admin, reason="not needed")

        levels = set(self._notes(self.viewer, category="general").values_list("level", flat=True))
        self.assertEqual(levels, {"success", "danger"})

    def test_key_borrow_decision_notifies_the_borrower(self):
        from keys.models import KeyBorrow, RoomKey
        from keys.services import approve_borrow, reject_borrow
        from django.utils import timezone
        from datetime import timedelta

        key = RoomKey.objects.create(room_name="Lab 1", key_number="K-1")
        b = KeyBorrow.objects.create(
            key=key, borrower=self.viewer, purpose="class",
            expected_return_at=timezone.now() + timedelta(days=1),
        )
        approve_borrow(borrow=b, approver=self.staff)
        self.assertTrue(self._notes(self.viewer, category="general", level="success").exists())

        key2 = RoomKey.objects.create(room_name="Lab 2", key_number="K-2")
        b2 = KeyBorrow.objects.create(
            key=key2, borrower=self.viewer, purpose="class",
            expected_return_at=timezone.now() + timedelta(days=1),
        )
        reject_borrow(borrow=b2, approver=self.staff, reason="busy")
        self.assertTrue(self._notes(self.viewer, category="general", level="danger").exists())

    def test_requisition_decision_notifies_the_requester(self):
        from requisitions.models import Requisition
        from requisitions.services import approve

        req = Requisition.objects.create(user=self.viewer, purpose="lab work")
        approve(requisition=req, user=self.admin)
        self.assertTrue(self._notes(self.viewer, category="general").exists())

    # ---- new requests land in the staff / approver queue ---------------------

    def test_key_request_notifies_every_key_staff(self):
        from datetime import timedelta

        from django.utils import timezone
        from rest_framework.test import APIClient

        from keys.models import RoomKey

        manager = User.objects.create_user("mg@x.com", "Manager", role="manager")
        key = RoomKey.objects.create(room_name="Lab 1", key_number="K-9")

        client = APIClient()
        client.force_authenticate(self.viewer)
        res = client.post(
            "/api/key-borrows/",
            {"key": key.key_id, "purpose": "class",
             "expected_return_at": (timezone.now() + timedelta(days=1)).isoformat()},
            format="json",
        )
        self.assertEqual(res.status_code, 201)

        # staff + admin + manager each get one, the viewer gets none
        for u in (self.staff, self.admin, manager):
            self.assertEqual(self._notes(u, category="general").filter(title__startswith="Key request").count(), 1)
        self.assertFalse(self._notes(self.viewer).filter(title__startswith="Key request").exists())

    def test_key_return_notifies_staff_and_borrower(self):
        from datetime import timedelta

        from django.utils import timezone

        from keys.models import KeyBorrow, RoomKey
        from keys.services import approve_borrow, confirm_pickup, return_borrow

        key = RoomKey.objects.create(room_name="Lab 1", key_number="K-8")
        b = KeyBorrow.objects.create(
            key=key, borrower=self.viewer, purpose="class",
            expected_return_at=timezone.now() + timedelta(days=1),
        )
        approve_borrow(borrow=b, approver=self.admin)
        confirm_pickup(borrow=b, actor=self.admin)
        Notification.objects.all().delete()  # isolate the return step

        return_borrow(borrow=b, actor=self.viewer, location="Front desk")
        self.assertTrue(self._notes(self.staff, category="general").filter(title__startswith="Key returned").exists())
        self.assertTrue(self._notes(self.viewer, category="general").filter(title__startswith="Key returned").exists())

    def test_pending_stock_request_notifies_approvers(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.staff)
        res = client.post(
            "/api/pending-stock-transactions/",
            {"item": self.item.item_id, "type": "IN", "quantity": 5},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(self._notes(self.admin, category="general").filter(title__startswith="Stock IN request").exists())
        # the requester is excluded
        self.assertFalse(self._notes(self.staff).filter(title__startswith="Stock IN request").exists())

    def test_new_requisition_notifies_admins(self):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.staff)
        res = client.post(
            "/api/requisitions/",
            {"purpose": "workshop", "items": [{"item": self.item.item_id, "quantity": 2}]},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            self._notes(self.admin, category="general").filter(title__contains="requisition").exists()
        )

    def test_a_failing_notification_never_breaks_the_operation(self):
        """safe_notify swallows errors - the transfer still completes."""
        from unittest.mock import patch
        from stock.services import transfer_item

        with patch("notifications.services.push", side_effect=RuntimeError("db down")):
            history = transfer_item(item=self.item, to_room=self.lab2, user=self.admin)
        self.item.refresh_from_db()
        self.assertEqual(self.item.room, self.lab2)
        self.assertEqual(history.transfer_type, "full")


class NotificationApiTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.user = User.objects.create_user("api@x.com", "Api", role="admin")
        self.other = User.objects.create_user("other@x.com", "Other", role="admin")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.mine = Notification.objects.create(
            recipient=self.user, title="Yours", message="hi", level="info", category="general"
        )
        Notification.objects.create(recipient=self.other, title="Theirs", category="general")

    def test_list_returns_only_my_notifications(self):
        res = self.client.get("/api/notifications/?page_size=100")
        self.assertEqual(res.status_code, 200)
        titles = [n["title"] for n in res.data["results"]]
        self.assertEqual(titles, ["Yours"])

    def test_unread_count_and_mark_read(self):
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 1)
        res = self.client.post(f"/api/notifications/{self.mine.notification_id}/mark_read/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_read"])
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 0)

    def test_mark_all_read(self):
        Notification.objects.create(recipient=self.user, title="Another", category="import")
        res = self.client.post("/api/notifications/mark_all_read/")
        self.assertEqual(res.data["updated"], 2)
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["count"], 0)
