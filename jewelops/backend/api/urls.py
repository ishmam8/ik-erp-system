from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views.auth_views import RegisterView, LoginView, LogoutView, ProtectedView
from .accounting_ledger.views import ExpensesGetView, ExpensesView, SalesView, SalesGetView
from django.http import HttpResponse


urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('protected/', ProtectedView.as_view(), name='protected'),

    path('ledger/sales/', SalesView.as_view(), name='sales'),
    path('ledger/sales/all/', SalesGetView.as_view(), name='sales-list'),
    path('ledger/expenses/', ExpensesView.as_view(), name='expenses'),
    path('ledger/expenses/all/', ExpensesGetView.as_view(), name='expenses-list')
]
