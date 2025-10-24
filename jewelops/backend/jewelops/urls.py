from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include

urlpatterns = [ 
    path("", lambda r: HttpResponse("OK"), name="root"),  
    path('api/', include('api.urls')),
    path('ledger/', include('accounting_ledger.urls')),
]