from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from core.models import ERPError
from .models import Account, JournalEntry, JournalLine, Payment


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "type", "balance"]
    list_filter = ["type"]


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ["number", "date", "memo", "reference", "total", "is_balanced"]
    inlines = [JournalLineInline]
    search_fields = ["number", "memo", "reference"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["number", "date", "direction", "amount", "invoice", "purchase_order"]
    list_filter = ["direction"]

    def has_change_permission(self, request, obj=None):
        return obj is None  # payments are immutable once posted

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except ERPError as e:
            raise ValidationError(str(e))
