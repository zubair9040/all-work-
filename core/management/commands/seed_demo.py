from datetime import date

from django.core.management.base import BaseCommand

from accounting.models import DEFAULT_ACCOUNTS, Account
from hr.models import Department, Employee
from inventory.models import Category, Product, Warehouse
from purchasing.models import PurchaseOrder, PurchaseOrderLine, Supplier
from sales.models import Customer


class Command(BaseCommand):
    help = "Load the chart of accounts and a small demo data set"

    def handle(self, *args, **opts):
        for code, name, typ in DEFAULT_ACCOUNTS:
            Account.objects.get_or_create(code=code, defaults={"name": name, "type": typ})
        wh, _ = Warehouse.objects.get_or_create(name="Main Warehouse")
        cat, _ = Category.objects.get_or_create(name="General")
        for sku, name, cost, price in [("A100", "Widget", 5, 9), ("B200", "Gadget", 12, 20)]:
            Product.objects.get_or_create(sku=sku, defaults=dict(
                name=name, category=cat, cost_price=cost, sale_price=price, reorder_level=10))
        Customer.objects.get_or_create(name="Acme Ltd")
        sup, _ = Supplier.objects.get_or_create(name="Global Supplies")
        dep, _ = Department.objects.get_or_create(name="Operations")
        Employee.objects.get_or_create(email="jane@example.com", defaults=dict(
            first_name="Jane", last_name="Doe", department=dep, hire_date=date.today(), monthly_salary=2500))
        if not PurchaseOrder.objects.exists():
            po = PurchaseOrder.objects.create(supplier=sup, warehouse=wh)
            for p in Product.objects.all():
                PurchaseOrderLine.objects.create(order=po, product=p, quantity=50)
            po.receive()
        self.stdout.write(self.style.SUCCESS("Demo data loaded"))
