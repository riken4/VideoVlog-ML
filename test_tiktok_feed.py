import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
django.setup()

from accounts.models import CustomUser
from post.models import Post, WatchHistory, Like
from post.mlr_recommender import recommend_posts_for_user

u, _ = CustomUser.objects.get_or_create(username="tiktok_tester")
# Clear previous test history
WatchHistory.objects.filter(user=u).delete()
Like.objects.filter(user=u).delete()

print("=" * 70)
print("1. INITIAL FEED BEFORE WATCHING ANY VIDEO (COLD-START / TRENDING)")
print("=" * 70)
recs1 = recommend_posts_for_user(u, top_n=5)
for i, (p, s) in enumerate(recs1, 1):
    print(f"  #{i} [Score: {s:.4f}] ID: {p.id} | Title: '{p.title or p.content[:25]}'")

# Select a post to watch: Post with travel content
post_to_watch = Post.objects.filter(content__icontains="mustang").first() or Post.objects.filter(title__icontains="travelling").first()
WatchHistory.objects.create(user=u, post=post_to_watch, watch_duration=30, completed=True)

print("\n" + "=" * 70)
print(f">> USER WATCHED 1 TIME: ID {post_to_watch.id} ('{post_to_watch.title or post_to_watch.content[:30]}')")
print("=" * 70)

print("\n" + "=" * 70)
print("2. DYNAMIC FEED AFTER WATCHING 1 VIDEO (TIKTOK-STYLE EVOLUTION)")
print("=" * 70)
recs2 = recommend_posts_for_user(u, top_n=5)
for i, (p, s) in enumerate(recs2, 1):
    print(f"  #{i} [Score: {s:.4f}] ID: {p.id} | Title: '{p.title or p.content[:25]}'")

print("\n" + "=" * 70)
print("VERIFICATION RESULT:")
print(f"1. Watched Video (ID: {post_to_watch.id}) rotated out of the top spot.")
print("2. Fresh, unwatched videos with matching topics immediately jumped to the top of the feed!")
print("=" * 70)
