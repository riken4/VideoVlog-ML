from .models import (
    Like,
    Comment,
    WatchHistory,
    Follow
)


def calculate_interaction_score(user, post):
    """
    Calculate a user's interaction score for a specific post.
    """

    score = 0

    # Viewed
    if WatchHistory.objects.filter(
        user=user,
        post=post
    ).exists():
        score += 1

    # Completed
    if WatchHistory.objects.filter(
        user=user,
        post=post,
        completed=True
    ).exists():
        score += 5

    # Liked
    if Like.objects.filter(
        user=user,
        post=post
    ).exists():
        score += 3

    # Commented
    if Comment.objects.filter(
        author=user,
        post=post
    ).exists():
        score += 4

    # Following the creator
    if Follow.objects.filter(
        follower=user,
        following=post.author
    ).exists():
        score += 2

    return score