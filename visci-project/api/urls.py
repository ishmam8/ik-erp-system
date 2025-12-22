from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views.auth_views import RegisterView, VerifyOTPView, LoginView, GoogleLoginView, LogoutView, ProtectedView
from .views.trade_views import get_currency_view, switch_currency_view

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    #TODO: Implement token refresh logic
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('protected/', ProtectedView.as_view(), name='protected'),

    #TODO: build the frontend for get-currency
    path('get-currency/', get_currency_view, name='get_currency'),
    path('switch-currency/', switch_currency_view, name='switch_currency'),
]