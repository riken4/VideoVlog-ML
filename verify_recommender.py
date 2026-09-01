import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
django.setup()

from accounts.models import CustomUser
from post.models import Post
from post.mlr_recommender import recommend_posts_for_user
from post.recommender import recommend

print("=" * 60)
print("VERIFYING MLR RECOMMENDATION ENGINE PIPELINE")
print("=" * 60)

users = list(CustomUser.objects.all()[:3])

for u in users:
    print(f"\n--- Recommendations for User: {u.username} (ID: {u.id}) ---")
    recs = recommend_posts_for_user(u, top_n=5)
    for rank, (post, score) in enumerate(recs, start=1):
        print(f"  #{rank} [Score: {score:.4f}] ID: {post.id} | Author: {post.author.username} | Title: '{post.title or post.content[:25]}'")

print("\n--- Cold Start / Anonymous Recommendations ---")
anon_recs = recommend_posts_for_user(None, top_n=5)
for rank, (post, score) in enumerate(anon_recs, start=1):
    print(f"  #{rank} [Score: {score:.4f}] ID: {post.id} | Author: {post.author.username} | Title: '{post.title or post.content[:25]}'")

print("\n--- Content-Based Query Recommendation (Title/Topic Search) ---")
test_post = Post.objects.first()
if test_post:
    content_recs = recommend(test_post.id, top_n=3)
    print(f"Similar to Post #{test_post.id} ('{test_post.title}'):")
    for p in content_recs:
        print(f"  -> ID: {p.id} | Title: '{p.title or p.content[:25]}'")

print("\n" + "=" * 60)
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
print("=" * 60)
