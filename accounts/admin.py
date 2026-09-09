from django.contrib import admin

from .models import LoginEvent, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("user_id", "name", "email", "role", "is_staff", "created_at")
    search_fields = ("name", "email")
    list_filter = ("role", "is_staff")


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "email", "event", "successful", "ip_address", "client", "timestamp")
    list_filter = ("event", "successful", "timestamp")
    search_fields = ("email", "ip_address", "user__name")
    readonly_fields = tuple(f.name for f in LoginEvent._meta.fields)
    ordering = ("-timestamp",)
