from django.contrib import admin
from .models import Sales, Expenses, Orders

admin.site.register([Sales, Expenses, Orders])