"""Project-wide list pagination.

The stock, audit, users and roomwise pages all ask for large result sets via a
``?page_size=`` or ``?limit=`` query param (dropdowns and history tables need the
whole set, not one 10-row page). Plain :class:`PageNumberPagination` ignores both
and hard-caps every list at ``PAGE_SIZE``, which is why those screens looked
"broken" - only the first 10 items/rooms/rows ever showed up.

This class keeps the ``{count, next, previous, results}`` envelope (so existing
``data.results || data`` callers are unaffected) but lets a caller widen the page
with ``?page_size=`` or the ``?limit=`` alias, up to ``max_page_size``.
"""

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 5000

    def get_page_size(self, request):
        raw = request.query_params.get(self.page_size_query_param) or request.query_params.get("limit")
        if raw is not None:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return self.page_size
            if value > 0:
                return min(value, self.max_page_size)
        return self.page_size
