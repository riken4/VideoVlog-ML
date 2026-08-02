from django.http import JsonResponse
from .recommender import recommend
from .models import Post
import json
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from .models import Post, WatchHistory
from django.contrib.auth.decorators import login_required

def get_recommendations(request):
    title = request.GET.get("title")

    if not title:
        return JsonResponse(
            {"error": "Video title is required"},
            status=400
        )

    recommendations = recommend(title)

    return JsonResponse(recommendations, safe=False)


def recommend_posts(request, post_id):
    try:
        Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return JsonResponse(
            {"error": "Post not found"},
            status=404
        )

    recommended_posts = recommend(post_id)

    data = []

    for post in recommended_posts:
        data.append({
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "author": post.author.username,
            "likes": post.total_likes,
            "comments": post.total_comments,
            "image": post.image.url if post.image else None,
            "video": post.video.url if post.video else None,
        })

    return JsonResponse(data, safe=False)

@require_POST
@login_required
def watch_start(request):

    data = json.loads(request.body)

    post_id = data.get("post_id")

    post = get_object_or_404(Post, id=post_id)

    watch, created = WatchHistory.objects.get_or_create(
        user=request.user,
        post=post,
        defaults={
            "watch_duration": 0,
            "completed": False,
        }
    )

    return JsonResponse({
        "success": True,
        "created": created,
        "watch_id": watch.id
    })
    
@require_POST
@login_required
def watch_update(request):

    data = json.loads(request.body)

    post_id = data.get("post_id")
    duration = data.get("duration")

    post = get_object_or_404(Post, id=post_id)

    try:

        watch = WatchHistory.objects.get(
            user=request.user,
            post=post
        )

        watch.watch_duration = duration
        watch.save()

        return JsonResponse({
            "success": True
        })

    except WatchHistory.DoesNotExist:

        return JsonResponse({
            "success": False
        }, status=404)
        
@require_POST
@login_required
def watch_complete(request):

    data = json.loads(request.body)

    post_id = data.get("post_id")

    post = get_object_or_404(Post, id=post_id)

    try:
        watch = WatchHistory.objects.get(
            user=request.user,
            post=post
        )

        watch.completed = True
        watch.completed = True

        watch.save()

        return JsonResponse({
            "success": True
        })

    except WatchHistory.DoesNotExist:

        return JsonResponse({
            "success": False
        }, status=404)