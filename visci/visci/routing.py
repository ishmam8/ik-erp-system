from django.urls import path
from . import consumers

websocket_urlpatterns = [
    #update user balance
    path("ws/balance/<int:user_id>/", consumers.BalanceConsumer.as_asgi()),
]