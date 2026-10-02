# ERP System

A Django-based ERP for a trading/retail business.

## Modules
- **Inventory** – products, categories, warehouses, append-only stock ledger, reorder alerts
- **Sales** – customers, sales orders (confirm → stock issue + invoice + ledger posting), invoices
- **Purchasing** – suppliers, purchase orders (receive → stock in, weighted-average cost, ledger posting)
- **Accounting** – chart of accounts, double-entry journal (always balanced), payments against invoices/POs
- **HR** – departments, employees, leave requests, payslips posted to the ledger
- **Dashboard** at `/` – sales, receivables, payables, profit, low stock, overdue invoices

Day-to-day work is done in the Django admin (`/admin/`) using the order/payslip actions.

## Run
```
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo        # chart of accounts + sample data
python manage.py createsuperuser
python manage.py runserver
```
Tests: `python manage.py test`
