from django.urls import re_path
from . import consumers


websocket_urlpatterns = [

    # Post WebSocket
    re_path(
        r"ws/post/(?P<post_id>\d+)/$",
        consumers.PostConsumer.as_asgi()
    ),

    # Notification WebSocket
    re_path(
        r"ws/notifications/$",
        consumers.NotificationConsumer.as_asgi()
    ),

]