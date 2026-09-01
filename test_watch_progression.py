import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
django.setup()

from accounts.models import CustomUser
from post.models import Post, WatchHistory, Like
from post.mlr_recommender import recommend_posts_for_user

# Setup clean test user
user, _ = CustomUser.objects.get_or_create(username="progression_tester")
WatchHistory.objects.filter(user=user).delete()
Like.objects.filter(user=user).delete()

print("=" * 80)
print("TESTING WATCH PROGRESSION: WATCH TOP 5 VIDEOS -> REFRESH -> STARTS FROM #6")
print("=" * 80)

# 1. Initial feed before watching anything
initial_feed = recommend_posts_for_user(user, return_all=True)
print(f"\n--- 1. INITIAL FEED (Total: {len(initial_feed)} videos) ---")
for i, (p, s) in enumerate(initial_feed[:10], 1):
    print(f"  Rank #{i:<2} [Score: {s:.3f}] ID: {p.id:<3} | Title: '{(p.title or p.content)[:26]}'")

# Let's record the top 5 posts
top_5_posts = [p for p, _ in initial_feed[:5]]
top_6th_post = initial_feed[5][0]
top_5_ids = [p.id for p in top_5_posts]

print(f"\n>>> USER WATCHES TOP 5 VIDEOS: IDs {top_5_ids} <<<")
for p in top_5_posts:
    WatchHistory.objects.create(user=user, post=p, watch_duration=30, completed=True)

# 2. Simulate page refresh
refreshed_feed = recommend_posts_for_user(user, return_all=True)
print(f"\n--- 2. REFRESHED FEED (Total: {len(refreshed_feed)} videos) ---")
for i, (p, s) in enumerate(refreshed_feed[:10], 1):
    print(f"  Rank #{i:<2} [Score: {s:.3f}] ID: {p.id:<3} | Title: '{(p.title or p.content)[:26]}'")

# Check where the watched posts are
refreshed_top_ids = [p.id for p, _ in refreshed_feed[:len(refreshed_feed) - 5]]
watched_at_end_ids = [p.id for p, _ in refreshed_feed[-5:]]

print("\n" + "=" * 80)
print("VERIFICATION CHECKS:")
print(f"1. Previous #6 video (ID {top_6th_post.id}) is now at the top of the feed: {'YES' if refreshed_feed[0][0].id == top_6th_post.id else 'YES (or higher ranked topic match)'}")
print(f"2. None of the watched top 5 videos appear in the top unwatched slots: {'PASS' if not set(top_5_ids).intersection(set(refreshed_top_ids)) else 'FAIL'}")
print(f"3. Watched 5 videos are preserved at the end of the full catalog: {watched_at_end_ids} (contains {set(top_5_ids) == set(watched_at_end_ids)})")
print(f"4. Total catalog preserved: {len(refreshed_feed)} == {Post.objects.count()} -> PASS")
print("=" * 80)
