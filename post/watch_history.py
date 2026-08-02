from .models import WatchHistory


def record_watch(user, post):
    """
    Record that a user started watching a post.
    Avoid creating duplicate entries if one already exists.
    """

    WatchHistory.objects.get_or_create(
        user=user,
        post=post,
        defaults={
            "watch_duration": 0,
            "completed": False,
        }
    )