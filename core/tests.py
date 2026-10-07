from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounting.models import Account, Payment, acct
from core.models import ERPError
from hr.models import Department, Employee, Payslip
from inventory.models import Category, Product, Warehouse
from purchasing.models import PurchaseOrder, PurchaseOrderLine, Supplier
from sales.models import Customer, SalesOrder, SalesOrderLine


class ERPFlowTests(TestCase):
    def setUp(self):
        self.wh = Warehouse.objects.create(name="Main")
        self.p = Product.objects.create(sku="A1", name="Widget", cost_price=0, sale_price=10)
        self.cust = Customer.objects.create(name="Acme")
        self.sup = Supplier.objects.create(name="Sup")

    def receive(self, qty, cost):
        po = PurchaseOrder.objects.create(supplier=self.sup, warehouse=self.wh)
        PurchaseOrderLine.objects.create(order=po, product=self.p, quantity=qty, unit_cost=cost)
        po.receive()
        return po

    def sell(self, qty):
        so = SalesOrder.objects.create(customer=self.cust, warehouse=self.wh)
        SalesOrderLine.objects.create(order=so, product=self.p, quantity=qty)
        return so

    def test_purchase_adds_stock_and_posts_ledger(self):
        po = self.receive(10, 4)
        self.assertEqual(self.p.stock(), 10)
        self.assertEqual(acct("1200").balance, 40)
        self.assertEqual(acct("2000").balance, 40)
        self.assertEqual(po.number, f"PO-{po.pk:06d}")

    def test_weighted_average_cost(self):
        self.receive(10, 4)
        self.receive(10, 6)
        self.p.refresh_from_db()
        self.assertEqual(self.p.cost_price, Decimal("5.00"))

    def test_sale_flow_and_payment(self):
        self.receive(10, 4)
        so = self.sell(3)
        inv = so.confirm()
        self.assertEqual(self.p.stock(), 7)
        self.assertEqual(inv.total, 30)
        self.assertEqual(acct("4000").balance, 30)
        self.assertEqual(acct("5000").balance, 12)
        Payment.objects.create(direction="received", date=date.today(), amount=30, invoice=inv)
        self.assertEqual(inv.balance_due, 0)
        self.assertEqual(inv.status, "Paid")
        self.assertEqual(acct("1100").balance, 0)

    def test_cannot_oversell(self):
        self.receive(2, 4)
        so = self.sell(5)
        with self.assertRaises(ERPError):
            so.confirm()
        so.refresh_from_db()
        self.assertEqual(so.status, "draft")
        self.assertEqual(self.p.stock(), 2)

    def test_overpayment_rejected(self):
        self.receive(5, 4)
        inv = self.sell(1).confirm()
        with self.assertRaises(ERPError):
            Payment.objects.create(direction="received", date=date.today(), amount=11, invoice=inv)

    def test_ledger_balances(self):
        self.receive(10, 4)
        self.sell(2).confirm()
        d = sum(a.lines.aggregate(t=__import__("django.db.models", fromlist=["Sum"]).Sum("debit"))["t"] or 0
                for a in Account.objects.all())
        c = sum(a.lines.aggregate(t=__import__("django.db.models", fromlist=["Sum"]).Sum("credit"))["t"] or 0
                for a in Account.objects.all())
        self.assertEqual(d, c)

    def test_payroll_posts_once(self):
        emp = Employee.objects.create(first_name="J", last_name="D", email="j@x.com",
                                      hire_date=date.today(), monthly_salary=1000)
        ps = Payslip.objects.create(employee=emp, period=date(2026, 1, 1), basic=1000,
                                    allowances=100, deductions=150)
        ps.post()
        self.assertEqual(acct("6000").balance, 1100)
        self.assertEqual(acct("1000").balance, -950)
        with self.assertRaises(ERPError):
            ps.post()

    def test_dashboard_requires_login_and_renders(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        u = get_user_model().objects.create_superuser("a", "a@x.com", "pw")
        self.client.force_login(u)
        self.assertEqual(self.client.get("/").status_code, 200)


class LoginPageTests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user("bob", password="pw12345!")

    def test_login_page_renders(self):
        r = self.client.get("/login/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Welcome")

    def test_anonymous_redirected_to_login(self):
        self.assertRedirects(self.client.get("/", follow=False), "/login/?next=/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/").status_code, 302)

    def test_bad_password_shows_error(self):
        r = self.client.post("/login/", {"username": "bob", "password": "nope"})
        self.assertContains(r, "Incorrect username or password")

    def test_login_redirects_to_dashboard_and_session_ends_with_browser(self):
        r = self.client.post("/login/", {"username": "bob", "password": "pw12345!"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_remember_me_keeps_session_30_days(self):
        self.client.post("/login/", {"username": "bob", "password": "pw12345!", "remember": "on"})
        self.assertEqual(self.client.session.get_expiry_age(), 60 * 60 * 24 * 30)

    def test_logout(self):
        self.client.force_login(self.u)
        self.assertRedirects(self.client.post("/logout/"), "/login/", fetch_redirect_response=False)
