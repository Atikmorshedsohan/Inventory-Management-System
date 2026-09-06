from rest_framework.permissions import BasePermission, SAFE_METHODS

class RolePermission(BasePermission):
    """Permission class enforcing access by user role.
    - admin: full access
    - manager: cannot delete items, but can create/update items, purchases, requisitions
    - viewer: read-only
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role = getattr(user, 'role', 'viewer')
        method = request.method

        if role == 'admin':
            return True

        if role == 'viewer':
            return method in SAFE_METHODS

        if role == 'manager':
            # Managers can read and modify most resources, but we restrict deletes in view-level
            if method in SAFE_METHODS:
                return True
            # Allow POST, PUT, PATCH
            return method in ('POST', 'PUT', 'PATCH')

        # legacy 'staff' behaves like manager
        if role == 'staff':
            if method in SAFE_METHODS:
                return True
            return method in ('POST', 'PUT', 'PATCH')

        return False

class NoDeletePermission(BasePermission):
    """Block DELETE for non-admin roles."""
    def has_permission(self, request, view):
        user = request.user
        if request.method != 'DELETE':
            return True
        return getattr(user, 'role', 'viewer') == 'admin'

class NotViewerPermission(BasePermission):
    """Block access for viewer role - used for requisitions and audit logs."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        role = getattr(user, 'role', 'viewer')
        # Block viewers from accessing this resource entirely
        if role == 'viewer':
            return False
        # Allow admin, manager, staff
        return True
