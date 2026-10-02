from django.contrib import admin

from core.admin_actions import run_action
from .models import Department, Employee, LeaveRequest, Payslip


admin.site.register(Department)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["__str__", "department", "job_title", "monthly_salary", "is_active"]
    list_filter = ["department", "is_active"]
    search_fields = ["first_name", "last_name", "email"]


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["employee", "start_date", "end_date", "days", "status"]
    list_filter = ["status"]
    actions = ["approve", "reject"]

    @admin.action(description="Approve")
    def approve(self, request, qs):
        qs.update(status=LeaveRequest.APPROVED)

    @admin.action(description="Reject")
    def reject(self, request, qs):
        qs.update(status=LeaveRequest.REJECTED)


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ["number", "employee", "period", "basic", "allowances", "deductions", "net", "posted"]
    list_filter = ["posted"]
    actions = ["post_payslips"]

    @admin.action(description="Post to ledger")
    def post_payslips(self, request, qs):
        run_action(self, request, qs, "post", "Posted")
