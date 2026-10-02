from decimal import Decimal

from django.db import models
from django.db.models import Sum

from core.models import TimeStamped, ERPError


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Warehouse(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TimeStamped):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    unit = models.CharField(max_length=20, default="pcs")
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def stock(self, warehouse=None):
        qs = self.movements.all()
        if warehouse:
            qs = qs.filter(warehouse=warehouse)
        return qs.aggregate(t=Sum("quantity"))["t"] or 0

    @property
    def on_hand(self):
        return self.stock()

    @property
    def needs_reorder(self):
        return self.on_hand <= self.reorder_level


class StockMovement(TimeStamped):
    """Signed ledger of stock changes. Stock level = sum of quantities."""

    IN, OUT, ADJUST = "in", "out", "adjust"
    KINDS = [(IN, "Receipt"), (OUT, "Issue"), (ADJUST, "Adjustment")]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    quantity = models.IntegerField(help_text="Positive adds stock, negative removes it")
    kind = models.CharField(max_length=10, choices=KINDS, default=ADJUST)
    reference = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.product.sku} {self.quantity:+d} @ {self.warehouse}"


def move_stock(product, warehouse, quantity, kind, reference="", note=""):
    if kind == StockMovement.OUT and product.stock(warehouse) < abs(quantity):
        raise ERPError(
            f"Insufficient stock for {product.sku} in {warehouse}: "
            f"have {product.stock(warehouse)}, need {abs(quantity)}"
        )
    return StockMovement.objects.create(
        product=product, warehouse=warehouse, quantity=quantity,
        kind=kind, reference=reference, note=note,
    )
