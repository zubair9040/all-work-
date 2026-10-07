from decimal import Decimal

from django.db import models, transaction

from core.models import TimeStamped, NumberedMixin, ERPError


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Employee(TimeStamped):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    job_title = models.CharField(max_length=100, blank=True)
    hire_date = models.DateField()
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class LeaveRequest(TimeStamped):
    PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"
    STATUSES = [(PENDING, "Pending"), (APPROVED, "Approved"), (REJECTED, "Rejected")]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leaves")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date")

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


class Payslip(TimeStamped, NumberedMixin):
    number_prefix = "PS"
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payslips")
    period = models.DateField(help_text="First day of the pay month")
    basic = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    posted = models.BooleanField(default=False, editable=False)

    class Meta:
        unique_together = [("employee", "period")]
        ordering = ["-period", "employee"]

    @property
    def net(self):
        return self.basic + self.allowances - self.deductions

    @transaction.atomic
    def post(self):
        """Book salary expense against cash."""
        from accounting.models import post_journal, CASH
        if self.posted:
            raise ERPError("Payslip already posted")
        post_journal(self.period, f"Payroll {self.number}", self.number,
                     [("6000", self.basic + self.allowances, 0),
                      (CASH, 0, self.net), ("2100", 0, self.deductions)])
        self.posted = True
        self.save(update_fields=["posted", "updated_at"])
