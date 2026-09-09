from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from catalog.models import Item, Room
from catalog.services import roomwise_inventory


class RoomwiseInventoryOrderingTests(TestCase):
    def setUp(self):
        self.a = Room.objects.create(room_name="Alpha Lab", room_type="lab")
        self.b = Room.objects.create(room_name="Beta Lab", room_type="lab")
        self.c = Room.objects.create(room_name="Gamma Lab", room_type="lab")
        self.ia = Item.objects.create(item_name="a", unit="pcs", quantity=1, room=self.a)
        self.ib = Item.objects.create(item_name="b", unit="pcs", quantity=1, room=self.b)
        self.ic = Item.objects.create(item_name="c", unit="pcs", quantity=1, room=self.c)
        self.unassigned = Item.objects.create(item_name="loose", unit="pcs", quantity=4)
        # Pin explicit, well-separated update times: Alpha < Beta < Gamma < General.
        self._stamp(self.ia, 40)
        self._stamp(self.ib, 30)
        self._stamp(self.ic, 20)
        self._stamp(self.unassigned, 10)

    def _stamp(self, item, minutes_ago):
        Item.objects.filter(pk=item.pk).update(
            updated_at=timezone.now() - timedelta(minutes=minutes_ago)
        )

    def _names(self):
        return [r["room_name"] for r in roomwise_inventory()]

    def test_baseline_order_is_newest_activity_first(self):
        self.assertEqual(
            self._names(), ["General Storage", "Gamma Lab", "Beta Lab", "Alpha Lab"]
        )

    def test_a_partial_save_bumps_updated_at_and_reorders(self):
        # Django < 5 ignores auto_now on update_fields; Item.save() compensates.
        self.ia.quantity = 9
        self.ia.save(update_fields=["quantity"])
        self.assertEqual(self._names()[0], "Alpha Lab")

    def test_a_stock_in_pulls_general_storage_to_the_top(self):
        self.unassigned.quantity = 20
        self.unassigned.save(update_fields=["quantity"])
        self.assertEqual(self._names()[0], "General Storage")

    def test_general_storage_bucket_holds_unassigned_items(self):
        rooms = {r["room_name"]: r for r in roomwise_inventory()}
        self.assertIn("General Storage", rooms)
        self.assertIsNone(rooms["General Storage"]["room_id"])
        self.assertEqual(rooms["General Storage"]["total_quantity"], 4)

    def test_no_general_storage_bucket_when_everything_is_assigned(self):
        self.unassigned.room = self.a
        self.unassigned.save(update_fields=["room"])
        self.assertNotIn("General Storage", self._names())

    def test_each_room_and_item_carries_a_last_update_timestamp(self):
        alpha = {r["room_name"]: r for r in roomwise_inventory()}["Alpha Lab"]
        self.assertIsNotNone(alpha["last_updated"])
        self.assertIsNotNone(alpha["items"][0]["updated_at"])

    def test_general_storage_loses_ties_to_real_rooms(self):
        stamp = timezone.now()
        Item.objects.filter(pk__in=[self.ic.pk, self.unassigned.pk]).update(updated_at=stamp)
        names = self._names()
        self.assertLess(names.index("Gamma Lab"), names.index("General Storage"))
