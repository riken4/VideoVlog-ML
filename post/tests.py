from unittest.mock import patch

import pandas as pd
from django.test import TestCase

from accounts.models import CustomUser
from post.mlr_features import FEATURE_NAMES
from post.models import Like, Post
from post.mlr_recommender import recommend_posts_for_user


class RecommendationExclusionTests(TestCase):
    def test_liked_post_is_not_returned_as_its_own_recommendation(self):
        user = CustomUser.objects.create_user(username="viewer", password="password")
        author = CustomUser.objects.create_user(username="creator", password="password")
        liked_post = Post.objects.create(author=author, title="Python basics", content="")
        related_post = Post.objects.create(author=author, title="Python functions", content="")
        Like.objects.create(user=user, post=liked_post)

        feature_rows = pd.DataFrame(
            [{feature: 0.0 for feature in FEATURE_NAMES}], columns=FEATURE_NAMES
        )
        with (
            patch("post.mlr_recommender.load_mlr_artifacts", return_value=(None, object())),
            patch("post.mlr_recommender.build_features_for_user", return_value=feature_rows),
        ):
            recommendations = recommend_posts_for_user(user, return_all=True)

        recommended_ids = [post.id for post, _score in recommendations]
        self.assertNotIn(liked_post.id, recommended_ids)
        self.assertIn(related_post.id, recommended_ids)
