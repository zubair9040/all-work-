from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import TimeStamped, NumberedMixin, ERPError
from inventory.models import Product, Warehouse, StockMovement, move_stock


class Supplier(TimeStamped):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PurchaseOrder(TimeStamped, NumberedMixin):
    number_prefix = "PO"
    DRAFT, RECEIVED, CANCELLED = "draft", "received", "cancelled"
    STATUSES = [(DRAFT, "Draft"), (RECEIVED, "Received"), (CANCELLED, "Cancelled")]

    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT)

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def total(self):
        return sum((l.subtotal for l in self.lines.all()), Decimal(0))

    @property
    def paid(self):
        return self.payments.aggregate(t=Sum("amount"))["t"] or Decimal(0)

    @property
    def balance_due(self):
        return self.total - self.paid if self.status == self.RECEIVED else Decimal(0)

    @transaction.atomic
    def receive(self):
        """Receive goods: add stock, update cost price, book inventory vs payables."""
        from accounting.models import post_journal, INVENTORY, AP

        if self.status != self.DRAFT:
            raise ERPError("Only draft purchase orders can be received")
        lines = list(self.lines.select_related("product"))
        if not lines:
            raise ERPError("Order has no lines")
        for l in lines:
            move_stock(l.product, self.warehouse, l.quantity, StockMovement.IN, self.number)
            # Weighted-average cost (stock already includes this receipt)
            p = l.product
            before = p.stock() - l.quantity
            if before > 0:
                p.cost_price = ((p.cost_price * before) + (l.unit_cost * l.quantity)) / (before + l.quantity)
            else:
                p.cost_price = l.unit_cost
            p.cost_price = p.cost_price.quantize(Decimal("0.01"))
            p.save(update_fields=["cost_price", "updated_at"])
        self.status = self.RECEIVED
        self.save(update_fields=["status", "updated_at"])
        post_journal(self.date, f"Purchase {self.number}", self.number,
                     [(INVENTORY, self.total, 0), (AP, 0, self.total)])

    def cancel(self):
        if self.status != self.DRAFT:
            raise ERPError("Only draft purchase orders can be cancelled")
        self.status = self.CANCELLED
        self.save(update_fields=["status", "updated_at"])


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True)

    def save(self, *args, **kwargs):
        if self.unit_cost is None:
            self.unit_cost = self.product.cost_price
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.unit_cost or 0) * self.quantity
