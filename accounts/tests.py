from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.access_matrix import build_matrix
from accounts.models import LoginEvent
from accounts.services import change_user_role
from accounts.utils import describe_client
from audit.models import AuditLog
from common.exceptions import DomainError

User = get_user_model()


class ChangeUserRoleServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.other_admin = User.objects.create_user("a2@x.com", "Admin Two", role="admin")
        self.member = User.objects.create_user("m@x.com", "Member", role="viewer")

    def test_promotes_and_recomputes_django_staff_flag(self):
        self.assertFalse(self.member.is_staff)

        change_user_role(target=self.member, actor=self.admin, new_role="manager")

        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "manager")
        self.assertTrue(self.member.is_staff)  # User.save() derives this

    def test_demotion_clears_the_staff_flag(self):
        staff = User.objects.create_user("s@x.com", "Staff", role="staff")
        self.assertTrue(staff.is_staff)

        change_user_role(target=staff, actor=self.admin, new_role="viewer")

        staff.refresh_from_db()
        self.assertEqual(staff.role, "viewer")
        self.assertFalse(staff.is_staff)

    def test_change_is_audited_with_both_roles(self):
        change_user_role(target=self.member, actor=self.admin, new_role="manager")
        log = AuditLog.objects.filter(action__icontains="Changed role").latest("timestamp")
        self.assertEqual(log.user, self.admin)
        self.assertIn("Member", log.action)
        self.assertIn("viewer -> manager", log.action)

    def test_rejects_an_unknown_role(self):
        with self.assertRaises(DomainError) as ctx:
            change_user_role(target=self.member, actor=self.admin, new_role="superuser")
        self.assertIn("not a valid role", str(ctx.exception.detail))

    def test_rejects_a_no_op_change(self):
        with self.assertRaises(DomainError) as ctx:
            change_user_role(target=self.member, actor=self.admin, new_role="viewer")
        self.assertIn("already has", str(ctx.exception.detail))

    def test_cannot_change_your_own_role(self):
        with self.assertRaises(DomainError) as ctx:
            change_user_role(target=self.admin, actor=self.admin, new_role="viewer")
        self.assertIn("your own role", str(ctx.exception.detail))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")

    def test_an_admin_can_be_demoted_while_another_admin_remains(self):
        change_user_role(target=self.other_admin, actor=self.admin, new_role="manager")
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.role, "manager")

    def test_cannot_demote_the_last_active_admin(self):
        # Only ``other_admin`` is still an active admin.
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        with self.assertRaises(DomainError) as ctx:
            change_user_role(target=self.other_admin, actor=self.admin, new_role="viewer")
        self.assertIn("last active admin", str(ctx.exception.detail))

        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.role, "admin")

    def test_role_is_normalised(self):
        change_user_role(target=self.member, actor=self.admin, new_role="  MANAGER  ")
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "manager")


class RoleManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.manager = User.objects.create_user("m@x.com", "Manager", role="manager")
        self.staff = User.objects.create_user("s@x.com", "Staff", role="staff")
        self.viewer = User.objects.create_user("v@x.com", "Viewer", role="viewer")
        self.client = APIClient()

    def _set_role(self, target, role):
        return self.client.post(
            f"/api/users/{target.pk}/set_role/", {"role": role}, format="json"
        )

    def test_admin_can_change_a_role(self):
        self.client.force_authenticate(self.admin)
        res = self._set_role(self.viewer, "manager")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["role"], "manager")
        self.assertEqual(res.data["role_display"], "Manager")
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.role, "manager")

    def test_manager_and_staff_cannot_change_roles(self):
        for actor in (self.manager, self.staff, self.viewer):
            self.client.force_authenticate(actor)
            res = self._set_role(self.viewer, "admin")
            self.assertEqual(res.status_code, 403, actor.role)
            self.viewer.refresh_from_db()
            self.assertEqual(self.viewer.role, "viewer")

    def test_invalid_role_returns_a_helpful_400(self):
        self.client.force_authenticate(self.admin)
        res = self._set_role(self.viewer, "wizard")
        self.assertEqual(res.status_code, 400)
        self.assertIn("not a valid role", res.data["detail"])

    def test_self_role_change_is_refused(self):
        self.client.force_authenticate(self.admin)
        res = self._set_role(self.admin, "viewer")
        self.assertEqual(res.status_code, 400)
        self.assertIn("your own role", res.data["detail"])

    def test_role_cannot_be_set_through_a_plain_patch(self):
        self.client.force_authenticate(self.admin)
        res = self.client.patch(
            f"/api/users/{self.viewer.pk}/", {"role": "admin"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.role, "viewer")  # silently ignored, not applied

    def test_role_cannot_be_escalated_through_the_profile_endpoint(self):
        self.client.force_authenticate(self.viewer)
        res = self.client.patch("/api/auth/me/", {"role": "admin"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.role, "viewer")

    def test_non_admins_cannot_edit_other_users(self):
        self.client.force_authenticate(self.manager)
        res = self.client.patch(
            f"/api/users/{self.viewer.pk}/", {"name": "Renamed"}, format="json"
        )
        self.assertEqual(res.status_code, 403)
        self.viewer.refresh_from_db()
        self.assertEqual(self.viewer.name, "Viewer")

    def test_everyone_signed_in_can_still_read_the_directory(self):
        for actor in (self.admin, self.manager, self.staff, self.viewer):
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get("/api/users/").status_code, 200, actor.role)

    def test_roles_endpoint_lists_the_vocabulary(self):
        self.client.force_authenticate(self.admin)
        res = self.client.get("/api/users/roles/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            {r["value"] for r in res.data}, {"admin", "manager", "viewer", "staff"}
        )


class UserActivityApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "Admin", role="admin")
        self.manager = User.objects.create_user("m@x.com", "Manager", role="manager")
        self.viewer = User.objects.create_user("v@x.com", "Viewer", role="viewer")
        self.other = User.objects.create_user("o@x.com", "Other", role="viewer")

        for i in range(3):
            AuditLog.objects.create(user=self.viewer, action=f"Stock IN: Cable x{i}")
        AuditLog.objects.create(user=self.admin, action="Approved requisition #1")
        self.client = APIClient()

    def _activity(self, target, **params):
        return self.client.get(f"/api/users/{target.pk}/activity/", params)

    def test_returns_only_that_users_entries_newest_first(self):
        self.client.force_authenticate(self.admin)
        res = self._activity(self.viewer)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total"], 3)
        self.assertEqual(res.data["user_name"], "Viewer")
        actions = [r["action"] for r in res.data["results"]]
        self.assertEqual(actions, ["Stock IN: Cable x2", "Stock IN: Cable x1", "Stock IN: Cable x0"])

    def test_entries_carry_the_action_type_badge(self):
        self.client.force_authenticate(self.admin)
        res = self._activity(self.viewer)
        self.assertTrue(all(r["action_type"] == "stock" for r in res.data["results"]))

    def test_a_user_can_see_their_own_activity(self):
        self.client.force_authenticate(self.viewer)
        res = self._activity(self.viewer)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total"], 3)

    def test_a_viewer_cannot_see_someone_elses_activity(self):
        self.client.force_authenticate(self.viewer)
        res = self._activity(self.admin)
        self.assertEqual(res.status_code, 403)

    def test_managers_can_see_anyones_activity(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self._activity(self.viewer).status_code, 200)

    def test_limit_is_honoured_and_clamped(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self._activity(self.viewer, limit=2).data["results"]), 2)
        self.assertEqual(len(self._activity(self.viewer, limit=0).data["results"]), 1)
        self.assertEqual(self._activity(self.viewer, limit="abc").data["total"], 3)

    def test_user_with_no_activity_returns_an_empty_list(self):
        self.client.force_authenticate(self.admin)
        res = self._activity(self.other)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["total"], 0)
        self.assertEqual(res.data["results"], [])

    def test_a_role_change_shows_up_in_the_actors_activity(self):
        self.client.force_authenticate(self.admin)
        self.client.post(
            f"/api/users/{self.other.pk}/set_role/", {"role": "manager"}, format="json"
        )
        res = self._activity(self.admin)
        entry = next(
            (r for r in res.data["results"] if "Changed role for Other" in r["action"]),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry["action_type"], "role")


class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("pm-a@x.com", "Admin", role="admin")
        self.manager = User.objects.create_user("pm-m@x.com", "Manager", role="manager")
        self.viewer = User.objects.create_user("pm-v@x.com", "Viewer", role="viewer")
        self.client = APIClient()

    def test_matrix_is_admin_only(self):
        for actor in (self.manager, self.viewer):
            self.client.force_authenticate(actor)
            self.assertEqual(
                self.client.get("/api/access/matrix/").status_code, 403, actor.role
            )
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/access/matrix/").status_code, 200)

    def test_matrix_lists_every_role_and_resource(self):
        matrix = build_matrix()
        self.assertEqual(
            [r["key"] for r in matrix["roles"]], ["admin", "manager", "staff", "viewer"]
        )
        keys = {r["key"] for r in matrix["resources"]}
        for expected in ("items", "users", "audit-logs", "login-events"):
            self.assertIn(expected, keys)

    def test_matrix_reflects_the_real_permission_classes(self):
        users = {r["key"]: r for r in build_matrix()["resources"]}["users"]

        self.assertIn("AdminWritePermission", users["enforced_by"])
        # Only admins write to the user directory; everyone signed in can read.
        self.assertTrue(users["roles"]["admin"]["PATCH"])
        self.assertFalse(users["roles"]["manager"]["PATCH"])
        self.assertFalse(users["roles"]["staff"]["PATCH"])
        self.assertTrue(users["roles"]["viewer"]["GET"])

    def test_matrix_shows_viewers_are_read_only_on_items(self):
        items = {r["key"]: r for r in build_matrix()["resources"]}["items"]
        self.assertTrue(items["roles"]["viewer"]["GET"])
        self.assertFalse(items["roles"]["viewer"]["POST"])
        self.assertFalse(items["roles"]["viewer"]["DELETE"])

    def test_matrix_shows_only_admins_delete(self):
        items = {r["key"]: r for r in build_matrix()["resources"]}["items"]
        self.assertTrue(items["roles"]["admin"]["DELETE"])
        self.assertFalse(items["roles"]["manager"]["DELETE"])

    def test_matrix_blocks_viewers_from_the_audit_log(self):
        audit = {r["key"]: r for r in build_matrix()["resources"]}["audit-logs"]
        self.assertFalse(audit["roles"]["viewer"]["GET"])
        self.assertTrue(audit["roles"]["manager"]["GET"])

    def test_matrix_tracks_a_permission_class_change(self):
        """The whole point: change the code, and the page follows."""
        from catalog.views import ItemViewSet
        from common.permissions import AdminOnlyPermission

        before = {r["key"]: r for r in build_matrix()["resources"]}["items"]
        self.assertTrue(before["roles"]["manager"]["POST"])

        original = ItemViewSet.permission_classes
        try:
            ItemViewSet.permission_classes = [AdminOnlyPermission]
            after = {r["key"]: r for r in build_matrix()["resources"]}["items"]
            self.assertFalse(after["roles"]["manager"]["POST"])
            self.assertEqual(after["enforced_by"], ["AdminOnlyPermission"])
        finally:
            ItemViewSet.permission_classes = original

    def test_action_rules_come_from_the_real_constants(self):
        actions = {a["label"]: a for a in build_matrix()["actions"]}
        approve = actions["Approve / reject a pending item"]
        self.assertEqual(approve["allowed"], ["admin", "manager"])
        self.assertTrue(approve["roles"]["admin"])
        self.assertFalse(approve["roles"]["viewer"])
        self.assertIn("catalog.views._ITEM_APPROVERS", approve["source"])

    def test_every_action_cites_where_the_rule_lives(self):
        for entry in build_matrix()["actions"]:
            self.assertTrue(entry["source"], entry["label"])
            self.assertTrue(entry["endpoint"], entry["label"])


class LoginActivityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            "la-a@x.com", "Admin", role="admin", password="secret-pass-1"
        )
        self.viewer = User.objects.create_user(
            "la-v@x.com", "Viewer", role="viewer", password="secret-pass-2"
        )
        self.client = APIClient()

    def _login(self, email, password, **extra):
        return self.client.post(
            "/api/auth/token/", {"email": email, "password": password}, format="json", **extra
        )

    def test_successful_login_is_recorded_with_ip_and_client(self):
        res = self._login(
            "la-a@x.com", "secret-pass-1",
            REMOTE_ADDR="203.0.113.9",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        )
        self.assertEqual(res.status_code, 200)

        event = LoginEvent.objects.get()
        self.assertEqual(event.event, "login")
        self.assertTrue(event.successful)
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.ip_address, "203.0.113.9")
        self.assertEqual(event.client, "Chrome on Windows")

    def test_failed_login_is_recorded_with_the_attempted_email(self):
        res = self._login("la-a@x.com", "wrong-password", REMOTE_ADDR="198.51.100.4")
        self.assertEqual(res.status_code, 401)

        event = LoginEvent.objects.get()
        self.assertEqual(event.event, "failed")
        self.assertFalse(event.successful)
        self.assertEqual(event.email, "la-a@x.com")
        self.assertEqual(event.ip_address, "198.51.100.4")
        self.assertTrue(event.reason)

    def test_failed_login_for_an_unknown_address_has_no_user(self):
        self._login("nobody@x.com", "whatever")
        event = LoginEvent.objects.get()
        self.assertIsNone(event.user)
        self.assertEqual(event.email, "nobody@x.com")

    def test_logout_is_recorded(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 200)

        event = LoginEvent.objects.get()
        self.assertEqual(event.event, "logout")
        self.assertEqual(event.user, self.viewer)

    def test_forwarded_header_is_preferred_over_remote_addr(self):
        self._login(
            "la-a@x.com", "secret-pass-1",
            HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.1",
            REMOTE_ADDR="10.0.0.1",
        )
        self.assertEqual(LoginEvent.objects.get().ip_address, "203.0.113.7")

    def test_a_junk_forwarded_header_does_not_break_login(self):
        res = self._login(
            "la-a@x.com", "secret-pass-1",
            HTTP_X_FORWARDED_FOR="not-an-ip",
            REMOTE_ADDR="192.0.2.5",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(LoginEvent.objects.get().ip_address, "192.0.2.5")

    def test_login_events_are_admin_only(self):
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/api/login-events/").status_code, 403)
        self.assertEqual(self.client.get("/api/login-events/summary/").status_code, 403)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/login-events/").status_code, 200)

    def test_events_can_be_filtered(self):
        self._login("la-a@x.com", "secret-pass-1", REMOTE_ADDR="203.0.113.9")
        self._login("la-a@x.com", "nope", REMOTE_ADDR="203.0.113.9")
        self._login("la-v@x.com", "secret-pass-2", REMOTE_ADDR="198.51.100.1")

        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.get("/api/login-events/", {"successful": "false"}).data["count"], 1
        )
        self.assertEqual(
            self.client.get("/api/login-events/", {"user": self.viewer.pk}).data["count"], 1
        )
        self.assertEqual(
            self.client.get("/api/login-events/", {"ip_address": "203.0.113"}).data["count"], 2
        )

    def test_summary_counts_and_last_seen(self):
        self._login("la-a@x.com", "secret-pass-1", REMOTE_ADDR="203.0.113.9")
        self._login("la-a@x.com", "nope", REMOTE_ADDR="203.0.113.9")

        self.client.force_authenticate(self.admin)
        data = self.client.get("/api/login-events/summary/").data

        self.assertEqual(data["successful_logins"], 1)
        self.assertEqual(data["failed_logins"], 1)
        self.assertEqual(data["distinct_ips"], 1)
        me = next(u for u in data["users"] if u["user_id"] == self.admin.pk)
        self.assertEqual(me["logins"], 1)
        self.assertEqual(me["last_ip"], "203.0.113.9")
        self.assertIsNotNone(me["last_login"])


class ClientDescriptionTests(TestCase):
    def test_recognises_common_clients(self):
        cases = {
            "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0 Safari/537.36": "Chrome on Windows",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) Firefox/121.0": "Firefox on macOS",
            "Mozilla/5.0 (Windows NT 10.0) Chrome/120 Safari/537.36 Edg/120": "Edge on Windows",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1": "Safari on iOS",
            "curl/8.4.0": "curl",
        }
        for agent, expected in cases.items():
            self.assertEqual(describe_client(agent), expected, agent)

    def test_unknown_agent_is_handled(self):
        self.assertEqual(describe_client(""), "Unknown client")
        self.assertEqual(describe_client(None), "Unknown client")
