import json
from channels.generic.websocket import AsyncWebsocketConsumer


class BalanceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.group_name = f"user_balance_{self.user_id}"

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # Client doesn't need to send anything

    async def send_balance_update(self, event):
        await self.send(text_data=json.dumps(event["data"]))