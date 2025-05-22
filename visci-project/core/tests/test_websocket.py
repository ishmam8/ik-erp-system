# test_websocket.py
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://127.0.0.1:8000/ws/balance/2/"  # Use a valid user ID
    async with websockets.connect(uri) as websocket:
        print("✅ Connected. Waiting for balance updates...\n")
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print("💰 Received balance update:", data)

asyncio.run(test_websocket())