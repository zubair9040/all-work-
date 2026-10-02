from django.contrib import admin

from .models import Category, Warehouse, Product, StockMovement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["name", "location"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["sku", "name", "category", "cost_price", "sale_price", "on_hand", "needs_reorder", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["sku", "name"]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["created_at", "product", "warehouse", "quantity", "kind", "reference"]
    list_filter = ["kind", "warehouse"]
    search_fields = ["product__sku", "reference"]
    # The ledger is append-only: no edits or deletes after the fact.
    def has_change_permission(self, request, obj=None):
        return obj is None
    def has_delete_permission(self, request, obj=None):
        return False
