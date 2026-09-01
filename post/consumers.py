import json

from channels.generic.websocket import AsyncWebsocketConsumer


class PostConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.post_id = self.scope["url_route"]["kwargs"]["post_id"]
        self.room_group_name = f"post_{self.post_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)

        message = data.get("message")

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "send_update",
                "message": message
            }
        )

    async def send_update(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "message",
                "message": event["message"]
            })
        )

    # -------------------------
    # LIKE
    # -------------------------

    async def like_update(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "like_update",
                "likes": event["likes"],
                "liked": event["liked"]
            })
        )

    # -------------------------
    # NEW COMMENT
    # -------------------------

    async def comment_update(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "comment_update",
                "comment_id": event["comment_id"],
                "author_id": event["author_id"],
                "username": event["username"],
                "profile_picture": event.get("profile_picture"),
                "comment": event["comment"],
                "time": event["time"]
            })
        )

    # -------------------------
    # EDIT COMMENT
    # -------------------------

    async def comment_edited(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "comment_edited",
                "comment_id": event["comment_id"],
                "comment": event["comment"]
            })
        )

    # -------------------------
    # DELETE COMMENT
    # -------------------------

    async def comment_deleted(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "comment_deleted",
                "comment_id": event["comment_id"]
            })
        )


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope["user"]

        if user.is_anonymous:
            await self.close()
            return

        self.user = user
        self.group_name = f"notifications_{user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def notification_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification",
            "notification_id": event.get("notification_id"),
        }))

        