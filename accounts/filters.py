import django_filters

from .models import LoginEvent


class LoginEventFilter(django_filters.FilterSet):
    """?user=3&event=failed&successful=false&date_from=2026-09-01"""

    user = django_filters.NumberFilter(field_name="user__user_id")
    date_from = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="timestamp", lookup_expr="date__lte")
    ip_address = django_filters.CharFilter(field_name="ip_address", lookup_expr="icontains")

    class Meta:
        model = LoginEvent
        fields = ["user", "event", "successful", "date_from", "date_to", "ip_address"]
