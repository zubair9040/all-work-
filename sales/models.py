from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import TimeStamped, NumberedMixin, ERPError
from inventory.models import Product, Warehouse, StockMovement, move_stock


class Customer(TimeStamped):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SalesOrder(TimeStamped, NumberedMixin):
    number_prefix = "SO"
    DRAFT, CONFIRMED, CANCELLED = "draft", "confirmed", "cancelled"
    STATUSES = [(DRAFT, "Draft"), (CONFIRMED, "Confirmed"), (CANCELLED, "Cancelled")]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT)
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT)

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def total(self):
        return sum((l.subtotal for l in self.lines.all()), Decimal(0))

    @transaction.atomic
    def confirm(self):
        """Issue stock, create invoice, and post revenue + COGS to the ledger."""
        from accounting.models import post_journal, AR, SALES, COGS, INVENTORY

        if self.status != self.DRAFT:
            raise ERPError("Only draft orders can be confirmed")
        lines = list(self.lines.select_related("product"))
        if not lines:
            raise ERPError("Order has no lines")
        cogs = Decimal(0)
        for l in lines:
            move_stock(l.product, self.warehouse, -l.quantity, StockMovement.OUT, self.number)
            cogs += l.product.cost_price * l.quantity
        self.status = self.CONFIRMED
        self.save(update_fields=["status", "updated_at"])
        invoice = Invoice.objects.create(order=self, date=self.date,
                                         due_date=self.date + timezone.timedelta(days=30))
        post_journal(self.date, f"Sale {self.number}", invoice.number, [
            (AR, self.total, 0), (SALES, 0, self.total),
            (COGS, cogs, 0), (INVENTORY, 0, cogs),
        ])
        return invoice

    @transaction.atomic
    def cancel(self):
        """Cancel a draft only; confirmed orders need a return process."""
        if self.status != self.DRAFT:
            raise ERPError("Only draft orders can be cancelled")
        self.status = self.CANCELLED
        self.save(update_fields=["status", "updated_at"])


class SalesOrderLine(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True)

    def save(self, *args, **kwargs):
        if self.unit_price is None:
            self.unit_price = self.product.sale_price
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return (self.unit_price or 0) * self.quantity


class Invoice(TimeStamped, NumberedMixin):
    number_prefix = "INV"
    order = models.OneToOneField(SalesOrder, on_delete=models.PROTECT, related_name="invoice")
    date = models.DateField()
    due_date = models.DateField()

    class Meta:
        ordering = ["-date", "-id"]

    @property
    def total(self):
        return self.order.total

    @property
    def paid(self):
        return self.payments.aggregate(t=Sum("amount"))["t"] or Decimal(0)

    @property
    def balance_due(self):
        return self.total - self.paid

    @property
    def status(self):
        if self.balance_due <= 0:
            return "Paid"
        return "Overdue" if self.due_date < timezone.localdate() else "Unpaid"
