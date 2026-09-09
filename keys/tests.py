from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from common.exceptions import DomainError
from keys.models import KeyAuditLog, KeyBorrow, RoomKey
from keys.services import (
    approve_borrow,
    confirm_pickup,
    reject_borrow,
    return_borrow,
)

User = get_user_model()


def _later(days=2):
    return timezone.now() + timedelta(days=days)


class KeyHandoverTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("s@x.com", "Staff", role="staff")
        self.borrower = User.objects.create_user("v@x.com", "Viewer", role="viewer")
        self.other = User.objects.create_user("v2@x.com", "Other", role="viewer")
        self.key = RoomKey.objects.create(room_name="Lab 1", key_number="K-101")

    def _request(self, borrower=None):
        return KeyBorrow.objects.create(
            key=self.key,
            borrower=borrower or self.borrower,
            purpose="class",
            expected_return_at=_later(),
        )

    # ---- approval no longer hands the key over -----------------------------

    def test_approve_parks_request_awaiting_pickup(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)

        borrow.refresh_from_db()
        self.key.refresh_from_db()

        self.assertEqual(borrow.status, "approved")
        self.assertTrue(borrow.awaiting_pickup)
        self.assertIsNotNone(borrow.approved_at)
        self.assertIsNone(borrow.borrowed_at)
        self.assertIsNone(borrow.handed_over_by)
        # The key is untouched until the handover is confirmed.
        self.assertEqual(self.key.status, "available")
        self.assertIsNone(self.key.assigned_to)

    def test_approve_logs_an_approved_audit_entry(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        log = KeyAuditLog.objects.get(key=self.key, action="approved")
        self.assertIn("Awaiting pickup", log.notes)
        self.assertEqual(log.performed_by, self.staff)

    # ---- the new confirm-pickup step ---------------------------------------

    def test_confirm_pickup_records_the_physical_handover(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)

        confirm_pickup(borrow=borrow, actor=self.staff, notes="ID checked at office")

        borrow.refresh_from_db()
        self.key.refresh_from_db()

        self.assertEqual(borrow.status, "borrowed")
        self.assertFalse(borrow.awaiting_pickup)
        self.assertIsNotNone(borrow.borrowed_at)
        self.assertEqual(borrow.handed_over_by, self.staff)
        self.assertEqual(borrow.handover_notes, "ID checked at office")
        self.assertEqual(self.key.status, "in_use")
        self.assertEqual(self.key.assigned_to, self.borrower)
        self.assertIsNotNone(self.key.assigned_date)

    def test_borrowed_at_is_stamped_at_pickup_not_at_approval(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        borrow.refresh_from_db()
        approved_at = borrow.approved_at

        # The whole point: approval leaves the handover timestamp empty.
        self.assertIsNotNone(approved_at)
        self.assertIsNone(borrow.borrowed_at)

        confirm_pickup(borrow=borrow, actor=self.staff)

        borrow.refresh_from_db()
        self.assertIsNotNone(borrow.borrowed_at)
        self.assertGreaterEqual(borrow.borrowed_at, approved_at)
        self.assertEqual(borrow.approved_at, approved_at)  # unchanged by pickup

    def test_confirm_pickup_logs_who_handed_it_over(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        confirm_pickup(borrow=borrow, actor=self.staff)

        log = KeyAuditLog.objects.get(key=self.key, action="picked_up")
        self.assertIn("Handover confirmed", log.notes)
        self.assertIn("Viewer", log.notes)
        self.assertIn("Staff", log.notes)

    def test_cannot_pick_up_a_request_that_was_never_approved(self):
        borrow = self._request()
        with self.assertRaises(DomainError):
            confirm_pickup(borrow=borrow, actor=self.staff)

    def test_cannot_pick_up_twice(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        confirm_pickup(borrow=borrow, actor=self.staff)
        with self.assertRaises(DomainError):
            confirm_pickup(borrow=borrow, actor=self.staff)

    def test_cannot_pick_up_a_lost_key(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        self.key.status = "lost"
        self.key.save(update_fields=["status"])
        with self.assertRaises(DomainError):
            confirm_pickup(borrow=borrow, actor=self.staff)

    def test_pickup_cancels_competing_requests(self):
        mine = self._request()
        theirs = self._request(borrower=self.other)
        approve_borrow(borrow=mine, approver=self.staff)
        confirm_pickup(borrow=mine, actor=self.staff)

        theirs.refresh_from_db()
        self.assertEqual(theirs.status, "rejected")

    # ---- guards around the new approved state ------------------------------

    def test_cannot_approve_a_second_request_while_one_awaits_pickup(self):
        first = self._request()
        second = self._request(borrower=self.other)
        approve_borrow(borrow=first, approver=self.staff)

        with self.assertRaises(DomainError) as ctx:
            approve_borrow(borrow=second, approver=self.staff)
        self.assertIn("awaiting pickup", str(ctx.exception.detail))

    def test_cannot_approve_while_key_is_already_handed_over(self):
        first = self._request()
        approve_borrow(borrow=first, approver=self.staff)
        confirm_pickup(borrow=first, actor=self.staff)

        second = self._request(borrower=self.other)
        with self.assertRaises(DomainError) as ctx:
            approve_borrow(borrow=second, approver=self.staff)
        self.assertIn("already handed over", str(ctx.exception.detail))

    def test_approved_request_can_be_cancelled_before_pickup(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        reject_borrow(borrow=borrow, approver=self.staff, reason="No longer needed")

        borrow.refresh_from_db()
        self.key.refresh_from_db()
        self.assertEqual(borrow.status, "rejected")
        self.assertEqual(self.key.status, "available")
        # Key is free again, so a fresh request can be approved.
        approve_borrow(borrow=self._request(borrower=self.other), approver=self.staff)

    def test_cannot_return_a_key_that_was_never_picked_up(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        with self.assertRaises(DomainError):
            return_borrow(borrow=borrow, actor=self.staff, location="Office")

    def test_full_lifecycle_releases_the_key(self):
        borrow = self._request()
        approve_borrow(borrow=borrow, approver=self.staff)
        confirm_pickup(borrow=borrow, actor=self.staff)
        return_borrow(borrow=borrow, actor=self.staff, location="Front desk")

        borrow.refresh_from_db()
        self.key.refresh_from_db()
        self.assertEqual(borrow.status, "returned")
        self.assertEqual(self.key.status, "available")
        self.assertIsNone(self.key.assigned_to)
        self.assertEqual(self.key.last_location, "Front desk")
        # The handover record survives the return.
        self.assertEqual(borrow.handed_over_by, self.staff)


class KeyHandoverApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("s2@x.com", "Staff", role="staff")
        self.borrower = User.objects.create_user("v3@x.com", "Viewer", role="viewer")
        self.stranger = User.objects.create_user("v4@x.com", "Stranger", role="viewer")
        self.key = RoomKey.objects.create(room_name="Lab 2", key_number="K-202")
        self.borrow = KeyBorrow.objects.create(
            key=self.key, borrower=self.borrower, purpose="lab",
            expected_return_at=_later(),
        )
        self.client = APIClient()

    def test_approve_endpoint_returns_approved_not_borrowed(self):
        self.client.force_authenticate(self.staff)
        res = self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/approve/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "approved")
        self.assertTrue(res.data["awaiting_pickup"])
        self.assertIsNone(res.data["borrowed_at"])

    def test_confirm_pickup_endpoint_completes_the_handover(self):
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/approve/")
        res = self.client.post(
            f"/api/key-borrows/{self.borrow.borrow_id}/confirm-pickup/",
            {"handover_notes": "Collected in person"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "borrowed")
        self.assertFalse(res.data["awaiting_pickup"])
        self.assertIsNotNone(res.data["borrowed_at"])
        self.assertEqual(res.data["handed_over_by_name"], "Staff")
        self.assertEqual(res.data["handover_notes"], "Collected in person")

    def test_borrower_can_confirm_their_own_pickup(self):
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/approve/")

        self.client.force_authenticate(self.borrower)
        res = self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/pickup/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["handed_over_by_name"], "Viewer")

    def test_stranger_cannot_confirm_someone_elses_pickup(self):
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/approve/")

        self.client.force_authenticate(self.stranger)
        res = self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/pickup/")
        # Viewers are scoped to their own borrows, so the row is simply not
        # visible to them - 404 rather than 403, which leaks nothing.
        self.assertEqual(res.status_code, 404)

        self.borrow.refresh_from_db()
        self.assertEqual(self.borrow.status, "approved")
        self.assertIsNone(self.borrow.borrowed_at)

    def test_awaiting_pickup_queue_lists_approved_requests(self):
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/approve/")

        res = self.client.get("/api/key-borrows/awaiting_pickup/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["borrow_id"], self.borrow.borrow_id)

        # Once collected it drops off the queue.
        self.client.post(f"/api/key-borrows/{self.borrow.borrow_id}/pickup/")
        res = self.client.get("/api/key-borrows/awaiting_pickup/")
        self.assertEqual(len(res.data), 0)


class KeyReservationTests(TestCase):
    """A borrow *request* immediately takes the key off the shelf."""

    def setUp(self):
        self.staff = User.objects.create_user("s5@x.com", "Staff", role="staff")
        self.first = User.objects.create_user("v5@x.com", "First", role="viewer")
        self.second = User.objects.create_user("v6@x.com", "Second", role="viewer")
        self.key = RoomKey.objects.create(room_name="Lab 3", key_number="K-303")
        self.client = APIClient()

    def _request_as(self, user):
        self.client.force_authenticate(user)
        return self.client.post(
            "/api/key-borrows/",
            {"key": self.key.key_id, "purpose": "class", "expected_return_at": _later().isoformat()},
            format="json",
        )

    def test_request_reserves_the_key(self):
        res = self._request_as(self.first)
        self.assertEqual(res.status_code, 201)
        self.key.refresh_from_db()
        self.assertEqual(self.key.status, "reserved")

    def test_second_viewer_cannot_request_a_reserved_key(self):
        self.assertEqual(self._request_as(self.first).status_code, 201)

        res = self._request_as(self.second)
        self.assertEqual(res.status_code, 400)
        self.assertIn("unavailable", res.data["detail"].lower())
        self.assertEqual(KeyBorrow.objects.filter(borrower=self.second).count(), 0)

    def test_rejecting_the_only_request_puts_the_key_back(self):
        self._request_as(self.first)
        borrow = KeyBorrow.objects.get(borrower=self.first)

        self.client.force_authenticate(self.staff)
        res = self.client.post(
            f"/api/key-borrows/{borrow.borrow_id}/reject/",
            {"rejection_reason": "no longer needed"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.key.refresh_from_db()
        self.assertEqual(self.key.status, "available")

        # The next person can now request it.
        self.assertEqual(self._request_as(self.second).status_code, 201)

    def test_key_stays_reserved_through_approval_until_pickup(self):
        self._request_as(self.first)
        borrow = KeyBorrow.objects.get(borrower=self.first)

        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/key-borrows/{borrow.borrow_id}/approve/")
        self.key.refresh_from_db()
        self.assertEqual(self.key.status, "reserved")

        self.client.post(f"/api/key-borrows/{borrow.borrow_id}/confirm-pickup/")
        self.key.refresh_from_db()
        self.assertEqual(self.key.status, "in_use")

    def test_full_cycle_returns_the_key_to_available(self):
        self._request_as(self.first)
        borrow = KeyBorrow.objects.get(borrower=self.first)
        self.client.force_authenticate(self.staff)
        self.client.post(f"/api/key-borrows/{borrow.borrow_id}/approve/")
        self.client.post(f"/api/key-borrows/{borrow.borrow_id}/confirm-pickup/")
        self.client.post(
            f"/api/key-borrows/{borrow.borrow_id}/return_key/",
            {"location": "Front desk"}, format="json",
        )
        self.key.refresh_from_db()
        self.assertEqual(self.key.status, "available")

    def test_same_viewer_can_replace_their_own_pending_request(self):
        self.assertEqual(self._request_as(self.first).status_code, 201)
        # A fresh request from the same viewer supersedes the stale one.
        self.assertEqual(self._request_as(self.first).status_code, 201)
        self.key.refresh_from_db()
        self.assertEqual(self.key.status, "reserved")
        self.assertEqual(
            KeyBorrow.objects.filter(key=self.key, status="pending").count(), 1
        )
