from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessAttempt
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from auditlog.models import AuditEvent
from auditlog.services import AuditCommand, record_domain_event

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)

    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "email_verified",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "role",
        "email_verified",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        (
            "Personal information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "role",
                    "email_verified",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "last_login",
        "date_joined",
        "updated_at",
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "role",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<path:object_id>/block/", self.admin_site.admin_view(self.block_view), name="accounts_user_block"),
            path("<path:object_id>/unblock/", self.admin_site.admin_view(self.unblock_view), name="accounts_user_unblock"),
            path("<path:object_id>/unlock-login/", self.admin_site.admin_view(self.unlock_login_view), name="accounts_user_unlock_login"),
        ]
        return custom + urls

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        user = self.get_object(request, object_id)
        extra_context["account_status"] = "Active" if user and user.is_active else "Blocked"
        extra_context["can_block_account"] = bool(user and user.is_active and user.pk != request.user.pk and not user.is_superuser)
        extra_context["can_unblock_account"] = bool(user and not user.is_active)
        extra_context["can_unlock_login"] = bool(user)
        return super().change_view(request, object_id, form_url, extra_context)

    def _target(self, request, object_id):
        target = self.get_object(request, object_id)
        if target is None:
            raise PermissionDenied
        if target.pk == request.user.pk:
            messages.error(request, "You cannot change your own account status.")
            return None
        return target

    def block_view(self, request, object_id):
        if request.method != "POST":
            raise PermissionDenied
        target = self._target(request, object_id)
        if target is None or target.is_superuser or not target.is_active:
            if target is not None and target.is_superuser:
                messages.error(request, "Superuser accounts cannot be blocked here.")
            return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
        target.is_active = False
        target.save(update_fields=("is_active", "updated_at"))
        record_domain_event(AuditCommand(category=AuditEvent.Category.ADMINISTRATION, event_type="account.blocked", outcome=AuditEvent.Outcome.SUCCESS, severity=AuditEvent.Severity.MEDIUM, resource_type="accounts.User", resource_id=None, actor=request.user, metadata={"request_kind": "admin_user_status"}))
        self.message_user(request, f"Account {target.email} was blocked.", messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))

    def unblock_view(self, request, object_id):
        if request.method != "POST":
            raise PermissionDenied
        target = self._target(request, object_id)
        if target is None:
            return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
        target.is_active = True
        target.save(update_fields=("is_active", "updated_at"))
        AxesProxyHandler.reset_attempts(username=target.email)
        record_domain_event(AuditCommand(category=AuditEvent.Category.ADMINISTRATION, event_type="account.unblocked", outcome=AuditEvent.Outcome.SUCCESS, severity=AuditEvent.Severity.INFO, resource_type="accounts.User", resource_id=None, actor=request.user, metadata={"request_kind": "admin_user_status"}))
        self.message_user(request, f"Account {target.email} was unblocked and temporary login lockouts were cleared.", messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))

    def unlock_login_view(self, request, object_id):
        if request.method != "POST":
            raise PermissionDenied
        target = self._target(request, object_id)
        if target is None:
            return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
        ip_address = request.META.get("REMOTE_ADDR") or None
        username_exists = AccessAttempt.objects.filter(username__iexact=target.email).exists()
        shared_ip_exists = bool(ip_address and AccessAttempt.objects.filter(username__isnull=True, ip_address=ip_address, failures_since_start__gte=5).exists())
        if shared_ip_exists and request.POST.get("confirm_shared") != "yes":
            messages.warning(request, "A shared IP lockout is active. Unlocking it may affect other accounts from this address. Confirm the action to continue.")
            return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
        if username_exists:
            AxesProxyHandler.reset_attempts(username=target.email)
        if shared_ip_exists:
            AxesProxyHandler.reset_attempts(ip_address=ip_address)
        if not username_exists and not shared_ip_exists:
            messages.info(request, "No matching Axes login lockout was found for this account.")
            return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
        record_domain_event(AuditCommand(category=AuditEvent.Category.SECURITY, event_type="account.login_attempts_unlocked", outcome=AuditEvent.Outcome.SUCCESS, severity=AuditEvent.Severity.INFO, resource_type="accounts.User", resource_id=None, actor=request.user, metadata={"request_kind": "shared_ip" if shared_ip_exists else "username"}))
        self.message_user(request, f"Login attempts unlocked for {target.email}.", messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:accounts_user_change", args=[object_id]))
