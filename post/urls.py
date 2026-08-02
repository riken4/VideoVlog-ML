from django.urls import path
from accounts.views import home_view
from .views import watch_start
from .views import get_recommendations, recommend_posts, watch_update, watch_complete

urlpatterns = [
    path("", home_view, name="home"),
    path("recommend/", get_recommendations, name="recommend"),
    path(
        "recommend/<int:post_id>/",
        recommend_posts,
        name="recommend_posts",
    ),
    path(
    "watch/start/",
    watch_start,
    name="watch_start",
),
    path(
    "watch/update/",
    watch_update,
    name="watch_update",
),
    path(
    "watch/complete/",
    watch_complete,
    name="watch_complete",
),
]
