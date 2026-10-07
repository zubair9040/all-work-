from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum

from core.models import TimeStamped, NumberedMixin, ERPError


class Account(models.Model):
    ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE = "asset", "liability", "equity", "revenue", "expense"
    TYPES = [(ASSET, "Asset"), (LIABILITY, "Liability"), (EQUITY, "Equity"),
             (REVENUE, "Revenue"), (EXPENSE, "Expense")]
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPES)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def balance(self):
        t = self.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        d, c = t["d"] or Decimal(0), t["c"] or Decimal(0)
        # Debit-normal accounts: assets & expenses
        return d - c if self.type in (self.ASSET, self.EXPENSE) else c - d


# Default chart of accounts used by auto-posting
CASH, AR, INVENTORY, AP = "1000", "1100", "1200", "2000"
SALES, COGS = "4000", "5000"
DEFAULT_ACCOUNTS = [
    (CASH, "Cash & Bank", Account.ASSET),
    (AR, "Accounts Receivable", Account.ASSET),
    (INVENTORY, "Inventory", Account.ASSET),
    (AP, "Accounts Payable", Account.LIABILITY),
    ("2100", "Payroll Liabilities", Account.LIABILITY),
    ("3000", "Owner's Equity", Account.EQUITY),
    (SALES, "Sales Revenue", Account.REVENUE),
    (COGS, "Cost of Goods Sold", Account.EXPENSE),
    ("6000", "Salaries & Wages", Account.EXPENSE),
    ("6100", "General Expenses", Account.EXPENSE),
]


def acct(code):
    obj, _ = Account.objects.get_or_create(
        code=code,
        defaults={"name": dict((c, n) for c, n, _t in DEFAULT_ACCOUNTS).get(code, code),
                  "type": dict((c, t) for c, _n, t in DEFAULT_ACCOUNTS).get(code, Account.EXPENSE)},
    )
    return obj


class JournalEntry(TimeStamped, NumberedMixin):
    number_prefix = "JE"
    date = models.DateField()
    memo = models.CharField(max_length=200, blank=True)
    reference = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name_plural = "journal entries"
        ordering = ["-date", "-id"]

    @property
    def total(self):
        return self.lines.aggregate(t=Sum("debit"))["t"] or Decimal(0)

    @property
    def is_balanced(self):
        t = self.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        return (t["d"] or 0) == (t["c"] or 0)


class JournalLine(models.Model):
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)


@transaction.atomic
def post_journal(date, memo, reference, lines):
    """lines: iterable of (account_code, debit, credit). Must balance."""
    lines = [(c, Decimal(d), Decimal(cr)) for c, d, cr in lines if d or cr]
    if sum(l[1] for l in lines) != sum(l[2] for l in lines):
        raise ERPError("Journal entry is not balanced")
    entry = JournalEntry.objects.create(date=date, memo=memo, reference=reference)
    for code, d, c in lines:
        JournalLine.objects.create(entry=entry, account=acct(code), debit=d, credit=c)
    return entry


class Payment(TimeStamped, NumberedMixin):
    number_prefix = "PAY"
    RECEIVED, MADE = "received", "made"
    DIRECTIONS = [(RECEIVED, "Received from customer"), (MADE, "Paid to supplier")]
    direction = models.CharField(max_length=10, choices=DIRECTIONS)
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    invoice = models.ForeignKey("sales.Invoice", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="payments")
    purchase_order = models.ForeignKey("purchasing.PurchaseOrder", null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="payments")
    note = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        new = self.pk is None
        with transaction.atomic():
            if new:
                if self.direction == self.RECEIVED and not self.invoice:
                    raise ERPError("A received payment must reference an invoice")
                if self.direction == self.MADE and not self.purchase_order:
                    raise ERPError("A supplier payment must reference a purchase order")
                if self.amount <= 0:
                    raise ERPError("Payment amount must be positive")
                target = self.invoice if self.direction == self.RECEIVED else self.purchase_order
                if self.amount > target.balance_due:
                    raise ERPError(f"Payment exceeds balance due ({target.balance_due})")
            super().save(*args, **kwargs)
            if new:
                if self.direction == self.RECEIVED:
                    post_journal(self.date, f"Payment {self.number}", self.number,
                                 [(CASH, self.amount, 0), (AR, 0, self.amount)])
                else:
                    post_journal(self.date, f"Payment {self.number}", self.number,
                                 [(AP, self.amount, 0), (CASH, 0, self.amount)])
