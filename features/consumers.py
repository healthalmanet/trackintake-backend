import json
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

class ReminderConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.group_name = None

        if self.user and self.user.is_authenticated:
            try:
                self.group_name = f"user_{self.user.id}"
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                await self.accept()
                logger.info(f"✅ Reminder WebSocket connected: user_{self.user.id}")
            except Exception as e:
                logger.error(f"❌ Error during Reminder connect: {e}")
                await self.close()
        else:
            logger.warning("❌ Reminder connection rejected: Unauthenticated")
            await self.close()

    async def disconnect(self, close_code):
        if self.group_name:
            try:
                # Use a timeout for group_discard to prevent hanging on shutdown
                await asyncio.wait_for(
                    self.channel_layer.group_discard(self.group_name, self.channel_name),
                    timeout=5.0
                )
                logger.info(f"🔌 Reminder disconnected: {self.group_name} (Code: {close_code})")
            except Exception as e:
                logger.error(f"❌ Error during Reminder disconnect: {e}")

    async def receive(self, text_data):
        # Handle incoming messages if needed, or just log
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except Exception as e:
            logger.error(f"❌ Error in Reminder receive: {e}")

    async def send_reminder(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type":        "reminder",
                "message":     event.get("message"),
                "reminder_id": event.get("reminder_id"),
                "title":       event.get("title"),
            }))
        except Exception as e:
            logger.error(f"❌ Error sending reminder: {e}")

    async def send_suggestion(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type":           "food_suggestion",
                "message":        event.get("message", ""),
                "top_suggestion": event.get("top_suggestion", ""),
                "reason":         event.get("reason", ""),
                "calories_left":  event.get("calories_left", 0),
            }))
        except Exception as e:
            logger.error(f"❌ Error sending suggestion: {e}")

    async def send_message(self, event):
        """No-op to prevent crash if message event is sent to shared group."""
        pass


class MessageConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        self.group_name = None

        if self.user and self.user.is_authenticated:
            try:
                self.group_name = f"user_{self.user.id}"
                await self.channel_layer.group_add(self.group_name, self.channel_name)
                await self.accept()
                logger.info(f"✅ Message WebSocket connected: user_{self.user.id}")
            except Exception as e:
                logger.error(f"❌ Error during Message connect: {e}")
                await self.close()
        else:
            logger.warning("❌ Message connection rejected: Unauthenticated")
            await self.close()

    async def disconnect(self, close_code):
        if self.group_name:
            try:
                await asyncio.wait_for(
                    self.channel_layer.group_discard(self.group_name, self.channel_name),
                    timeout=5.0
                )
                logger.info(f"🔌 Message disconnected: {self.group_name} (Code: {close_code})")
            except Exception as e:
                logger.error(f"❌ Error during Message disconnect: {e}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
        except Exception as e:
            logger.error(f"❌ Error in Message receive: {e}")

    async def send_message(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type":    "message",
                "message": event.get("message"),
                "sender": {
                    "id":    event.get("sender_id"),
                    "name":  event.get("sender_name"),
                    "email": event.get("sender_email"),
                },
                "receiver": {
                    "id":    event.get("receiver_id"),
                    "name":  event.get("receiver_name"),
                    "email": event.get("receiver_email"),
                },
            }))
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")

    async def send_suggestion(self, event):
        """No-op to prevent crash if suggestion event is sent to shared group."""
        pass

    async def send_reminder(self, event):
        """No-op to prevent crash if reminder event is sent to shared group."""
        pass