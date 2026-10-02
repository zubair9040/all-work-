from django.contrib import admin

from core.admin_actions import run_action
from .models import Supplier, PurchaseOrder, PurchaseOrderLine


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone"]
    search_fields = ["name", "email"]


class LineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "supplier", "date", "status", "total", "balance_due"]
    list_filter = ["status"]
    search_fields = ["number", "supplier__name"]
    inlines = [LineInline]
    actions = ["receive_orders", "cancel_orders"]

    @admin.action(description="Receive goods (add stock, post to ledger)")
    def receive_orders(self, request, qs):
        run_action(self, request, qs, "receive", "Received")

    @admin.action(description="Cancel draft orders")
    def cancel_orders(self, request, qs):
        run_action(self, request, qs, "cancel", "Cancelled")
