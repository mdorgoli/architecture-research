from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from expenses import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", views.ExpenseLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", views.signup, name="signup"),
    path("", views.dashboard, name="dashboard"),
    path("expenses/new/", views.expense_edit, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("categories/", views.categories, name="categories"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("health/live/", views.live, name="live"),
    path("health/ready/", views.ready, name="ready"),
]
