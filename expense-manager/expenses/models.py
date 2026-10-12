from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField("نام دسته‌بندی", max_length=60)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_owner_category")
        ]

    def __str__(self):
        return self.name


class Expense(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="دسته‌بندی")
    title = models.CharField("عنوان هزینه", max_length=120)
    amount = models.DecimalField(
        "مبلغ (تومان)",
        max_digits=14,
        decimal_places=0,
        validators=[MinValueValidator(Decimal("1"))],
    )
    spent_on = models.DateField("تاریخ میلادی", default=timezone.localdate)
    note = models.TextField("یادداشت اختیاری", max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-spent_on", "-id"]
        indexes = [models.Index(fields=["owner", "spent_on"], name="expense_owner_date")]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="positive_expense_amount")
        ]

    def clean(self):
        super().clean()
        if self.category_id and self.owner_id and self.category.owner_id != self.owner_id:
            raise ValidationError({"category": "دسته‌بندی متعلق به این کاربر نیست."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
