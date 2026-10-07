from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from accounting.models import Account
from hr.models import Employee, LeaveRequest
from inventory.models import Product
from purchasing.models import PurchaseOrder
from sales.models import Invoice, SalesOrder, SalesOrderLine

CHART_MONTHS = 6
CHART_HEIGHT = 125


def _month_start(d, back=0):
    """First day of the month `back` months before d."""
    idx = d.year * 12 + d.month - 1 - back
    return d.replace(year=idx // 12, month=idx % 12 + 1, day=1)


def _monthly_sales(today):
    start = _month_start(today, CHART_MONTHS - 1)
    rows = (
        SalesOrderLine.objects
        .filter(order__status=SalesOrder.CONFIRMED, order__date__gte=start)
        .annotate(m=TruncMonth("order__date"))
        .values("m")
        .annotate(t=Sum(ExpressionWrapper(F("quantity") * F("unit_price"),
                                          output_field=DecimalField(max_digits=16, decimal_places=2))))
    )
    totals = {r["m"]: r["t"] or Decimal(0) for r in rows}
    months = []
    for back in range(CHART_MONTHS - 1, -1, -1):
        m = _month_start(today, back)
        months.append({"label": m.strftime("%b"), "total": totals.get(m, Decimal(0))})
    peak = max((m["total"] for m in months), default=Decimal(0)) or Decimal(1)
    for i, m in enumerate(months):
        m["x"] = 52 + 80 * i
        m["cx"] = m["x"] + 21
        m["height"] = int(m["total"] / peak * CHART_HEIGHT)
        m["y"] = CHART_HEIGHT - m["height"] + 20
    return months


@login_required
def dashboard(request):
    today = timezone.localdate()
    invoices = list(Invoice.objects.select_related("order__customer"))
    receivable = sum((i.balance_due for i in invoices), Decimal(0))
    overdue = [i for i in invoices if i.status == "Overdue"]
    unpaid_pos = [p for p in PurchaseOrder.objects.filter(status=PurchaseOrder.RECEIVED) if p.balance_due > 0]
    payable = sum((p.balance_due for p in unpaid_pos), Decimal(0))

    chart = _monthly_sales(today)
    this_month, last_month = chart[-1]["total"], chart[-2]["total"]
    change = None
    if last_month:
        change = ((this_month - last_month) / last_month * 100).quantize(Decimal("0.1"))

    revenue = sum((a.balance for a in Account.objects.filter(type="revenue")), Decimal(0))
    expense = sum((a.balance for a in Account.objects.filter(type="expense")), Decimal(0))
    profit = revenue - expense
    margin = (profit / revenue * 100).quantize(Decimal("0.1")) if revenue else None

    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    user = request.user
    ctx = {
        "greeting": greeting,
        "display_name": user.get_short_name() or user.get_username(),
        "month_sales": this_month,
        "sales_change": change,
        "receivable": receivable,
        "overdue": overdue[:5],
        "overdue_count": len(overdue),
        "payable": payable,
        "unpaid_po_count": len(unpaid_pos),
        "profit": profit,
        "margin": margin,
        "chart": chart,
        "chart_peak_label": max(m["total"] for m in chart),
        "low_stock": [p for p in Product.objects.filter(is_active=True) if p.needs_reorder][:5],
        "draft_sales": SalesOrder.objects.filter(status="draft").count(),
        "draft_purchases": PurchaseOrder.objects.filter(status="draft").count(),
        "employees": Employee.objects.filter(is_active=True).count(),
        "pending_leave": LeaveRequest.objects.filter(status="pending").count(),
    }
    return render(request, "dashboard.html", ctx)
