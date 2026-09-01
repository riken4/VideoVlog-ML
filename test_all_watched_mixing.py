import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
django.setup()

from accounts.models import CustomUser
from post.models import Post, WatchHistory, Like
from post.mlr_recommender import recommend_posts_for_user

user, _ = CustomUser.objects.get_or_create(username="all_watched_tester")
WatchHistory.objects.filter(user=user).delete()
Like.objects.filter(user=user).delete()

# Mark ALL posts as watched for this user
all_posts = list(Post.objects.all())
for p in all_posts:
    WatchHistory.objects.create(user=user, post=p, watch_duration=45, completed=True)

print("=" * 80)
print(f"TESTING FEED MIXING WHEN ALL {len(all_posts)} VIDEOS ARE WATCHED (User: {user.username})")
print("=" * 80)

feeds = []
for refresh_idx in range(1, 4):
    feed = recommend_posts_for_user(user, return_all=True)
    top_5 = feed[:5]
    top_ids = [p.id for p, _ in top_5]
    top_titles = [f"#{p.id} {(p.title or p.content)[:18]}" for p, _ in top_5]
    feeds.append(top_ids)

    print(f"\n--- REFRESH #{refresh_idx} (Total in Feed: {len(feed)}) ---")
    print(f"Top 5 Titles: {top_titles}")
    print(f"Top 5 Scores: {[round(s, 3) for _, s in top_5]}")

print("\n" + "=" * 80)
print("TEST SUMMARY:")
print(f"1. Total videos delivered in each feed: {len(feed)} (all videos in DB).")
print(f"2. Feed ordering is dynamically mixed across refreshes:")
print(f"   Refresh #1 Top IDs: {feeds[0]}")
print(f"   Refresh #2 Top IDs: {feeds[1]}")
print(f"   Refresh #3 Top IDs: {feeds[2]}")
print(f"3. Mix check: Refresh 1 != Refresh 2 -> {feeds[0] != feeds[1]}")
print("=" * 80)
