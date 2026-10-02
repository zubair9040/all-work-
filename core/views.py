from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from accounting.models import Account
from hr.models import Employee, LeaveRequest
from inventory.models import Product
from purchasing.models import PurchaseOrder
from sales.models import Invoice, SalesOrder


@login_required
def dashboard(request):
    today = timezone.localdate()
    invoices = list(Invoice.objects.select_related("order"))
    receivable = sum((i.balance_due for i in invoices), Decimal(0))
    overdue = [i for i in invoices if i.status == "Overdue"]
    payable = sum((p.balance_due for p in PurchaseOrder.objects.filter(status="received")), Decimal(0))
    month_sales = sum((o.total for o in SalesOrder.objects.filter(
        status="confirmed", date__year=today.year, date__month=today.month)), Decimal(0))
    revenue = Account.objects.filter(type="revenue")
    expense = Account.objects.filter(type="expense")
    profit = sum((a.balance for a in revenue), Decimal(0)) - sum((a.balance for a in expense), Decimal(0))
    ctx = {
        "receivable": receivable,
        "payable": payable,
        "month_sales": month_sales,
        "profit": profit,
        "overdue": overdue,
        "low_stock": [p for p in Product.objects.filter(is_active=True) if p.needs_reorder],
        "draft_sales": SalesOrder.objects.filter(status="draft").count(),
        "draft_purchases": PurchaseOrder.objects.filter(status="draft").count(),
        "employees": Employee.objects.filter(is_active=True).count(),
        "pending_leave": LeaveRequest.objects.filter(status="pending").count(),
    }
    return render(request, "dashboard.html", ctx)
