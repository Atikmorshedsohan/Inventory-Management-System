from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Item
from common.exceptions import DomainError
from requisitions.models import Requisition, RequisitionEvent, RequisitionItem
from requisitions.services import add_comment, approve, issue, mark_returned, reject
from stock.models import StockTransaction

User = get_user_model()


class RequisitionWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.requester = User.objects.create_user("r@x.com", "Req", role="staff")
        self.widget = Item.objects.create(item_name="Widget", unit="pcs", quantity=10, opening_quantity=10)
        self.gadget = Item.objects.create(item_name="Gadget", unit="pcs", quantity=2, opening_quantity=2)

    def _req(self, lines, status="approved"):
        req = Requisition.objects.create(user=self.requester, purpose="test", status=status)
        for item, qty in lines:
            RequisitionItem.objects.create(requisition=req, item=item, quantity=qty)
        return req

    # ---- partial issue -----------------------------------------------------

    def test_partial_issue_gives_what_is_in_stock_and_marks_partial(self):
        req = self._req([(self.widget, 5), (self.gadget, 6)])  # gadget only has 2

        result = issue(requisition=req, user=self.admin)

        req.refresh_from_db()
        self.assertEqual(req.status, "partially_issued")
        self.assertFalse(result["fully_issued"])

        widget_line = req.items.get(item=self.widget)
        gadget_line = req.items.get(item=self.gadget)
        self.assertEqual(widget_line.issued_quantity, 5)
        self.assertEqual(gadget_line.issued_quantity, 2)
        self.assertEqual(gadget_line.outstanding_quantity, 4)

        self.widget.refresh_from_db()
        self.gadget.refresh_from_db()
        self.assertEqual(self.widget.quantity, 5)
        self.assertEqual(self.gadget.quantity, 0)
        self.assertEqual(StockTransaction.objects.filter(type="OUT").count(), 2)

    def test_second_issue_completes_a_partial_requisition(self):
        req = self._req([(self.gadget, 6)])
        issue(requisition=req, user=self.admin)  # issues 2, partial

        self.gadget.quantity = 10
        self.gadget.save(update_fields=["quantity"])

        result = issue(requisition=req, user=self.admin)  # issues remaining 4
        req.refresh_from_db()
        self.assertEqual(req.status, "issued")
        self.assertTrue(result["fully_issued"])
        self.assertEqual(req.items.get(item=self.gadget).issued_quantity, 6)

    def test_issue_with_allow_partial_false_skips_partly_fillable_lines(self):
        req = self._req([(self.widget, 5), (self.gadget, 6)])
        result = issue(requisition=req, user=self.admin, allow_partial=False)

        self.assertEqual(req.items.get(item=self.widget).issued_quantity, 5)
        self.assertEqual(req.items.get(item=self.gadget).issued_quantity, 0)
        self.assertTrue(any(s["item"] == "Gadget" for s in result["shortfalls"]))

    def test_issue_can_target_specific_lines(self):
        req = self._req([(self.widget, 3), (self.gadget, 2)])
        widget_line = req.items.get(item=self.widget)

        issue(requisition=req, user=self.admin, req_item_ids=[widget_line.req_item_id])

        req.refresh_from_db()
        self.assertEqual(req.status, "partially_issued")
        self.assertEqual(req.items.get(item=self.widget).issued_quantity, 3)
        self.assertEqual(req.items.get(item=self.gadget).issued_quantity, 0)

    def test_issue_raises_when_nothing_available(self):
        self.gadget.quantity = 0
        self.gadget.save(update_fields=["quantity"])
        req = self._req([(self.gadget, 4)])
        with self.assertRaises(DomainError):
            issue(requisition=req, user=self.admin)

    def test_partially_issued_requisition_can_be_returned(self):
        req = self._req([(self.gadget, 6)])
        issue(requisition=req, user=self.admin)
        mark_returned(requisition=req, user=self.admin)
        req.refresh_from_db()
        self.assertEqual(req.status, "returned")
        self.assertIsNotNone(req.returned_at)

    # ---- comments & timeline --------------------------------------------------

    def test_reject_stores_reason_as_timeline_event(self):
        req = self._req([(self.widget, 1)], status="pending")
        reject(requisition=req, user=self.admin, reason="Not this quarter")

        event = req.events.get(event_type="rejected")
        self.assertEqual(event.note, "Not this quarter")
        self.assertEqual(event.from_status, "pending")
        self.assertEqual(event.to_status, "rejected")
        self.assertEqual(event.actor, self.admin)

    def test_add_comment_creates_comment_event(self):
        req = self._req([(self.widget, 1)], status="pending")
        add_comment(requisition=req, user=self.requester, note="Please expedite")

        event = req.events.get(event_type="comment")
        self.assertEqual(event.note, "Please expedite")
        self.assertEqual(event.actor, self.requester)

    def test_empty_comment_is_rejected(self):
        req = self._req([(self.widget, 1)])
        with self.assertRaises(DomainError):
            add_comment(requisition=req, user=self.requester, note="   ")

    def test_full_lifecycle_builds_ordered_timeline(self):
        req = self._req([(self.widget, 2)], status="pending")
        approve(requisition=req, user=self.admin)
        issue(requisition=req, user=self.admin)
        mark_returned(requisition=req, user=self.admin)

        types = list(req.events.order_by("created_at", "event_id").values_list("event_type", flat=True))
        self.assertEqual(types, ["approved", "issued", "returned"])

    def test_approve_only_from_pending(self):
        req = self._req([(self.widget, 1)], status="approved")
        with self.assertRaises(DomainError):
            approve(requisition=req, user=self.admin)


class RequisitionApiTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.admin = User.objects.create_user("a2@x.com", "Admin", role="admin")
        self.requester = User.objects.create_user("r2@x.com", "Req", role="staff")
        self.item = Item.objects.create(item_name="Cable", unit="pcs", quantity=1, opening_quantity=1)
        self.client = APIClient()

    def _make_req(self):
        req = Requisition.objects.create(user=self.requester, purpose="p", status="approved")
        RequisitionItem.objects.create(requisition=req, item=self.item, quantity=5)
        return req

    def test_issue_endpoint_returns_partial_summary(self):
        req = self._make_req()
        self.client.force_authenticate(self.admin)
        res = self.client.post(f"/api/requisitions/{req.req_id}/issue/", {}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "partially_issued")
        self.assertFalse(res.data["fully_issued"])
        self.assertEqual(res.data["issued"][0]["issued"], 1)

    def test_comment_endpoint_blocks_other_requesters(self):
        req = self._make_req()
        stranger = User.objects.create_user("s@x.com", "Stranger", role="viewer")
        self.client.force_authenticate(stranger)
        res = self.client.post(
            f"/api/requisitions/{req.req_id}/comment/", {"note": "hi"}, format="json"
        )
        # viewer is blocked from the requisitions viewset entirely
        self.assertIn(res.status_code, (403,))

    def test_second_issue_via_api_completes_requisition(self):
        """Guards against the viewset's prefetch cache masking a full issue."""
        req = self._make_req()  # wants 5, only 1 in stock
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/requisitions/{req.req_id}/issue/", {}, format="json")

        self.item.quantity = 20
        self.item.save(update_fields=["quantity"])
        res = self.client.post(f"/api/requisitions/{req.req_id}/issue/", {}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["fully_issued"])
        self.assertEqual(res.data["status"], "issued")
        req.refresh_from_db()
        self.assertEqual(req.status, "issued")

    def test_timeline_endpoint_lists_events(self):
        req = self._make_req()
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/requisitions/{req.req_id}/reject/", {"note": "no"}, format="json")
        res = self.client.get(f"/api/requisitions/{req.req_id}/timeline/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(e["event_type"] == "rejected" and e["note"] == "no" for e in res.data))
