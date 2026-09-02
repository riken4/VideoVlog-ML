"""
============================================================
Recommendation System Diagnostic & Inspection Tool
============================================================
Run this script to inspect how videos are scored and ranked
for any specific user in your database.

Usage:
    python diagnose_recommendation.py
    python diagnose_recommendation.py <username>
============================================================
"""

import os
import sys
import django
import pandas as pd

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
django.setup()

from accounts.models import CustomUser
from post.models import Post
from post.mlr_recommender import recommend_posts_for_user, load_mlr_artifacts
from post.mlr_features import build_features_for_user, FEATURE_NAMES


def inspect_user_recommendations(username=None):
    if username:
        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            print(f"Error: User '{username}' does not exist.")
            return
    else:
        user = CustomUser.objects.first()

    print("=" * 80)
    print(f"RECOMMENDATION DIAGNOSTIC FOR USER: {user.username if user else 'Anonymous/Cold-Start'} (ID: {user.id if user else 'None'})")
    print("=" * 80)

    # 1. Get Top Recommendations
    recs = recommend_posts_for_user(user, top_n=10)
    if not recs:
        print("No recommendations returned. Please check if posts exist in the database.")
        return

    candidate_posts = [p for p, _ in recs]
    model, vectorizer = load_mlr_artifacts()
    features_df = build_features_for_user(user, candidate_posts, vectorizer=vectorizer)

    print("\n--- TOP RANKED POSTS WITH FEATURE BREAKDOWN ---")
    rows = []
    for i, (post, score) in enumerate(recs, start=1):
        f_row = features_df.iloc[i - 1]
        rows.append({
            "Rank": f"#{i}",
            "ID": post.id,
            "Title": (post.title or post.content)[:22],
            "Author": post.author.username,
            "Predicted Score": f"{score:.4f}",
            "Content (TF-IDF)": f"{f_row['content_score']:.3f}",
            "Liked?": int(f_row['user_liked']),
            "Commented?": int(f_row['user_commented']),
            "Follows Author?": int(f_row['following_author']),
            "Post Views": f"{f_row['post_views']:.2f}",
        })

    table_df = pd.DataFrame(rows)
    print(table_df.to_string(index=False))

    print("\n--- HOW TO VERIFY THIS IS ACCURATE ---")
    print("1. Content Score: Posts matching the user's past watched/liked topics have higher 'Content (TF-IDF)'.")
    print("2. Engagement Signals: Posts where Liked/Commented/Follows Author is 1 receive large positive boosts.")
    print("3. Final Score: The Predicted Score combines these weights and dictates the exact feed order.")
    print("=" * 80)


if __name__ == "__main__":
    target_user = sys.argv[1] if len(sys.argv) > 1 else None
    inspect_user_recommendations(target_user)
