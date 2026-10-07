from django.contrib import admin

from core.admin_actions import run_action
from .models import Customer, SalesOrder, SalesOrderLine, Invoice


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone"]
    search_fields = ["name", "email"]


class LineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "customer", "date", "status", "total"]
    list_filter = ["status"]
    search_fields = ["number", "customer__name"]
    inlines = [LineInline]
    actions = ["confirm_orders", "cancel_orders"]

    @admin.action(description="Confirm (issue stock, invoice, post to ledger)")
    def confirm_orders(self, request, qs):
        run_action(self, request, qs, "confirm", "Confirmed")

    @admin.action(description="Cancel draft orders")
    def cancel_orders(self, request, qs):
        run_action(self, request, qs, "cancel", "Cancelled")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "order", "date", "due_date", "total", "paid", "status"]
    search_fields = ["number", "order__customer__name"]
