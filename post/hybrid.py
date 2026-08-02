from collections import defaultdict

from django.db.models import Case, When

from post.models import (
    Post,
    Like,
    WatchHistory
)

from post.recommender import recommend
from post.collaborative import collaborative_recommend

from accounts.models import Follow


def hybrid_recommend(user, current_post_id, top_n=20):

    scores = defaultdict(float)

    # ----------------------------
    # Content-Based Recommendation
    # ----------------------------
    content_posts = recommend(
        current_post_id,
        top_n=20
    )

    for rank, post in enumerate(content_posts):
        score = 0.40 * (
            1 - rank / 20
        )
        scores[post.id] += score

    # ----------------------------
    # Collaborative Recommendation
    # ----------------------------
    collaborative_posts = collaborative_recommend(
        user.id,
        top_n=20
    )

    for rank, post in enumerate(collaborative_posts):
        score = 0.35 * (
            1 - rank / 20
        )
        scores[post.id] += score

    # ----------------------------
    # Watch Completion Score
    # ----------------------------
    for post_id in list(scores.keys()):

        completed_count = WatchHistory.objects.filter(
            post_id=post_id,
            completed=True
        ).count()

        scores[post_id] += completed_count * 0.10

    # ----------------------------
    # Like Score
    # ----------------------------
    for post_id in list(scores.keys()):

        like_count = Like.objects.filter(
            post_id=post_id
        ).count()

        scores[post_id] += like_count * 0.05

    # ----------------------------
    # Follow Author Bonus
    # ----------------------------
    for post_id in list(scores.keys()):

        post = Post.objects.get(id=post_id)

        if Follow.objects.filter(
            follower=user,
            following=post.author
        ).exists():

            scores[post_id] += 0.05

    # ----------------------------
    # Trending Score
    # ----------------------------
    for post_id in list(scores.keys()):

        likes = Like.objects.filter(
            post_id=post_id
        ).count()

        completed = WatchHistory.objects.filter(
            post_id=post_id,
            completed=True
        ).count()

        trending_score = likes + completed

        scores[post_id] += trending_score * 0.05


    # ----------------------------
    # Sort by Score
    # ----------------------------
    sorted_posts = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    recommended_ids = [
        post_id
        for post_id, score in sorted_posts[:top_n]
    ]

    preserved_order = Case(
        *[
            When(id=pk, then=position)
            for position, pk in enumerate(recommended_ids)
        ]
    )

    return (
        Post.objects
        .filter(id__in=recommended_ids)
        .order_by(preserved_order)
    )