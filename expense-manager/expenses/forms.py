from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import Category, Expense


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username"]

    def clean_username(self):
        username = self.cleaned_data["username"].strip().lower()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("این نام کاربری قبلاً ثبت شده است.")
        return username


class LoginForm(AuthenticationForm):
    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["title", "amount", "category", "spent_on", "note"]
        widgets = {
            "spent_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = user
        self.fields["category"].queryset = Category.objects.filter(owner=user)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.owner = user

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Category.objects.filter(owner=self.instance.owner, name=name).exists():
            raise forms.ValidationError("این دسته‌بندی وجود دارد.")
        return name
