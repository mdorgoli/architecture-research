from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .forms import CategoryForm, ExpenseForm, LoginForm, SignupForm
from .models import Category, Expense


class ExpenseLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm

    def post(self, request, *args, **kwargs):
        request.POST = request.POST.copy()
        request.POST["username"] = request.POST.get("username", "").strip().lower()
        return super().post(request, *args, **kwargs)


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                Category.objects.bulk_create(
                    [
                        Category(owner=user, name=name)
                        for name in ["خوراک", "رفت‌وآمد", "خانه", "سلامت", "سایر"]
                    ]
                )
        except IntegrityError:
            form.add_error("username", "این نام کاربری قبلاً ثبت شده است.")
        else:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@login_required
@never_cache
@require_GET
def dashboard(request):
    month = request.GET.get("month", timezone.localdate().strftime("%Y-%m"))
    try:
        start = date.fromisoformat(month + "-01")
        end = (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
    except ValueError, OverflowError:
        start = timezone.localdate().replace(day=1)
        end = (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
        month = start.strftime("%Y-%m")
        messages.warning(request, "ماه نامعتبر بود؛ ماه جاری نمایش داده شد.")
    expenses = Expense.objects.filter(owner=request.user, spent_on__gte=start, spent_on__lt=end)
    category = request.GET.get("category", "")
    if category:
        selected = get_object_or_404(
            Category,
            pk=category if category.isdecimal() and len(category) < 19 else 0,
            owner=request.user,
        )
        expenses = expenses.filter(category=selected)
    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    groups = list(
        expenses.order_by()
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    for group in groups:
        group["percent"] = round(group["total"] / total * 100) if total else 0
    return render(
        request,
        "expenses/dashboard.html",
        {
            "month": month,
            "total": total,
            "count": expenses.count(),
            "groups": groups,
            "page_obj": Paginator(expenses.select_related("category"), 20).get_page(
                request.GET.get("page")
            ),
            "categories": Category.objects.filter(owner=request.user),
            "selected_category": category,
        },
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def expense_edit(request, pk=None):
    expense = get_object_or_404(Expense, pk=pk, owner=request.user) if pk else None
    form = ExpenseForm(
        request.POST if request.method == "POST" else None, instance=expense, user=request.user
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "هزینه ذخیره شد.")
        return redirect("dashboard")
    return render(request, "expenses/form.html", {"form": form, "editing": expense is not None})


@login_required
@require_POST
def expense_delete(request, pk):
    get_object_or_404(Expense, pk=pk, owner=request.user).delete()
    messages.success(request, "هزینه حذف شد.")
    return redirect("dashboard")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def categories(request):
    form = CategoryForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error("name", "این دسته‌بندی وجود دارد.")
        else:
            messages.success(request, "دسته‌بندی اضافه شد.")
            return redirect("categories")
    return render(
        request,
        "expenses/categories.html",
        {"form": form, "categories": Category.objects.filter(owner=request.user)},
    )


@login_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, owner=request.user)
    try:
        category.delete()
    except ProtectedError:
        messages.error(request, "این دسته‌بندی هزینه دارد؛ ابتدا هزینه‌ها را جابه‌جا یا حذف کنید.")
    else:
        messages.success(request, "دسته‌بندی حذف شد.")
    return redirect("categories")


@require_GET
def live(request):
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
