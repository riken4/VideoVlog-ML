from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.utils.timesince import timesince
from django.utils import timezone
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import random

from .models import CustomUser, Follow, BlockedUser
from post.models import Notification, Post, Like, Comment
from post.serializers import NotificationSerializer
from post.train_mlr import train
from post.mlr_recommender import recommend_posts_for_user, recommend_following_posts_for_user
from moderation.comment_predict import predict_comment


def create_and_broadcast_notification(*, recipient, sender, notification_type, post=None, comment=None):
    """Persist a notification and immediately notify the recipient's open tabs."""
    notification = Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        post=post,
        comment=comment,
    )

    async_to_sync(get_channel_layer().group_send)(
        f"notifications_{recipient.id}",
        {
            "type": "notification_update",
            "notification_id": notification.id,
        },
    )
    return notification


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        bio = request.POST.get("bio")
        location = request.POST.get("location")
        profile_picture = request.FILES.get("profile_picture")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")

        if password != password2:
            messages.error(request, "Passwords don't match")
            return redirect('signup')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect('signup')

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect('signup')

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            bio=bio,
            location=location,
        )
        if profile_picture:
            user.profile_picture = profile_picture
            user.save()
        login(request, user)
        messages.success(request, 'User created successfully')
        return redirect('home')
    return render(request, 'pages/signup.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect("admin_users")
            messages.success(request, f"Welcome back, {user.username}")
            return redirect("home")
        else:
            if CustomUser.objects.filter(username=username, is_blocked=True).exists():
                messages.error(request, "This account has been blocked by an administrator.")
                return redirect("login")
            messages.error(request, "Invalid username and password")
            return redirect("login")

    return render(request, "pages/login.html")


def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully")
    return redirect("login")


def profile_view(request, username):
    username = (username or "").strip()
    if not username:
        if request.user.is_authenticated:
            return redirect("myprofile")
        return redirect("login")

    try:
        profile_user = CustomUser.objects.get(username=username)
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("home")

    posts = Post.objects.filter(author=profile_user).order_by("-created_at")
    is_following = False
    if request.user.is_authenticated and Follow.objects.filter(follower=request.user, following=profile_user).exists():
        is_following = True

    context = {
        "profile_user": profile_user,
        "posts": posts,
        "is_following": is_following,
        "following_count": profile_user.get_following_count(),
        "followers_count": profile_user.get_followers_count(),
    }
    return render(request, "pages/profile.html", context)


@login_required
def edit_profile_view(request):
    if request.method == "POST":
        user = request.user
        bio = request.POST.get("bio")
        location = request.POST.get("location")
        profile_picture = request.FILES.get("profile_picture")

        if not user.username:
            messages.error(request, "Your profile is missing a username.")
            return redirect("home")

        user.bio = bio
        user.location = location
        if profile_picture:
            user.profile_picture = profile_picture
        user.save()
        messages.success(request, "Updated successfully")
        return redirect("profile", username=user.username)
    return render(request, "pages/edit_profile.html")


@login_required
def my_profile_view(request):
    user = request.user
    if not user.username:
        messages.error(request, "Your profile is missing a username.")
        return redirect("home")

    myprofile = CustomUser.objects.get(username=user.username)
    posts = myprofile.post.all()
    context = {
        "profile_user": myprofile,
        "posts": posts,
        "is_following": False,
        "following_count": myprofile.get_following_count(),
        "followers_count": myprofile.get_followers_count(),
    }
    return render(request, "pages/profile.html", context)


def search_users(request):
    query = request.GET.get("q", "").strip()
    tab = request.GET.get("tab", "all").lower()
    if tab not in ["all", "videos", "users"]:
        tab = "all"

    users = CustomUser.objects.none()
    videos = []

    if query:
        # 1. Search users by username and bio
        users = CustomUser.objects.filter(
            Q(username__icontains=query) | Q(bio__icontains=query)
        ).order_by("username")

        # 2. Search videos/posts by title and description (content)
        keyword_posts = list(
            Post.objects.filter(
                Q(title__icontains=query) | Q(content__icontains=query)
            ).select_related("author").distinct()
        )
        keyword_ids = {p.id for p in keyword_posts}

        # Augment with TF-IDF content similarity search for semantic matches
        try:
            from post.recommender import recommend as tfidf_search
            tfidf_results = tfidf_search(query, top_n=20)
            tfidf_posts = [p for p, _ in tfidf_results if p.id not in keyword_ids]
        except Exception:
            tfidf_posts = []

        videos = keyword_posts + tfidf_posts

    user_likes = set()
    if request.user.is_authenticated:
        user_likes = set(
            Like.objects.filter(user=request.user).values_list("post_id", flat=True)
        )

    context = {
        "query": query,
        "tab": tab,
        "users": users,
        "videos": videos,
        "users_count": users.count() if query else 0,
        "videos_count": len(videos),
        "user_likes": user_likes,
    }
    return render(request, "pages/search_user.html", context)


@login_required
def follow_toggle(request, username):
    username = (username or "").strip()
    if not username:
        return redirect("home")

    if request.method == "POST":
        try:
            user_to_follow = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("home")

        if request.user == user_to_follow:
            messages.error(request, "You cannot follow yourself")
            return redirect("profile", username=username)

        follow_instance = Follow.objects.filter(follower=request.user, following=user_to_follow).first()
        if follow_instance:
            follow_instance.delete()
        else:
            Follow.objects.create(follower=request.user, following=user_to_follow)
            messages.success(request, f"You follow {username}")
            create_and_broadcast_notification(
                recipient=user_to_follow,
                sender=request.user,
                notification_type='follow'
            )
        return redirect("profile", username=username)
    return redirect("home")


@login_required
def home_view(request):
    # Retrieve personalized feed: unwatched recommendations first (starting from next unwatched),
    # followed by all remaining catalog videos
    recommended = recommend_posts_for_user(
        user=request.user,
        top_n=20,
        return_all=True
    )

    posts = [
        post
        for post, _score in recommended
    ]

    user_likes = list(
        Like.objects.filter(
            user=request.user
        ).values_list(
            "post_id",
            flat=True
        )
    )

    context = {
        "posts": posts,
        "user_likes": user_likes,
    }

    return render(
        request,
        "pages/home.html",
        context
    )


@login_required
def following_feed_view(request):
    """
    Following Feed: Exclusively displays videos from creators the logged-in user follows,
    ranked and personalized using the Multiple Linear Regression (MLR) algorithm.
    """
    recommended = recommend_following_posts_for_user(
        user=request.user,
        top_n=20,
        return_all=True
    )

    posts = [post for post, _score in recommended]

    user_likes = list(
        Like.objects.filter(
            user=request.user
        ).values_list(
            "post_id",
            flat=True
        )
    )

    following_count = request.user.following.count()
    suggested_creators = []
    if not posts or following_count == 0:
        followed_ids = set(request.user.following.values_list("following_id", flat=True))
        suggested_creators = CustomUser.objects.exclude(
            id__in=followed_ids | {request.user.id}
        ).order_by("-followers")[:8]

    context = {
        "posts": posts,
        "user_likes": user_likes,
        "is_following_feed": True,
        "following_count": following_count,
        "suggested_creators": suggested_creators,
    }

    return render(
        request,
        "pages/following.html",
        context
    )


@login_required
def create_post(request):
    if request.method == "POST":
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        video = request.FILES.get('video')

        if not content:
            messages.error(request, "Description / Content cannot be empty.")
            return render(request, "pages/create_post.html", {
                "form_title": title,
                "form_content": content,
            })

        if not video:
            messages.error(request, "Please select a video file. Only video posts are supported.")
            return render(request, "pages/create_post.html", {
                "form_title": title,
                "form_content": content,
            })

        # Validate video file extension
        allowed_extensions = ('.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v')
        if not video.name.lower().endswith(allowed_extensions):
            messages.error(request, "Invalid file format. Please upload a valid video file (MP4, WebM, MOV, MKV).")
            return render(request, "pages/create_post.html", {
                "form_title": title,
                "form_content": content,
            })

        # Check title toxicity with ML moderation model
        if title:
            title_prediction = predict_comment(title)
            if title_prediction == 1:
                messages.error(
                    request,
                    "Your post title contains inappropriate or abusive content and cannot be published."
                )
                return render(request, "pages/create_post.html", {
                    "form_title": title,
                    "form_content": content,
                })

        # Check content/description toxicity with ML moderation model
        content_prediction = predict_comment(content)
        if content_prediction == 1:
            messages.error(
                request,
                "Your post description contains inappropriate or abusive content and cannot be published."
            )
            return render(request, "pages/create_post.html", {
                "form_title": title,
                "form_content": content,
            })

        post = Post.objects.create(
            title=title,
            content=content,
            video=video,
            author=request.user
        )

        # Retrain recommendation model
        try:
            train()
        except Exception as e:
            print(f"Recommender retrain failed: {e}")

        messages.success(request, "Video post published successfully!")
        return redirect("home")

    return render(request, "pages/create_post.html")


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        content = request.POST.get("content")

        # Check the edited title
        if title:
            title_prediction = predict_comment(title)
            if title_prediction == 1:
                messages.error(
                    request,
                    "Your post title contains inappropriate content and cannot be updated."
                )
                return redirect("edit_post", post_id=post.id)

        # Check the edited content/description
        content_prediction = predict_comment(content)
        if content_prediction == 1:
            messages.error(
                request,
                "Your post description contains inappropriate content and cannot be updated."
            )
            return redirect("edit_post", post_id=post.id)

        # Update post if content is safe
        post.title = title
        post.content = content
        post.is_edited = True
        post.save()

        messages.success(request, "Post edited successfully.")
        return redirect("home")

    return render(request, "pages/edit_post.html", {"post": post})


@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    messages.success(request, "Post deleted successfully")
    return redirect("home")


@login_required
def like_post(request, post_id):
    if request.method == "POST":
        post = get_object_or_404(Post, id=post_id)

        like_instance = Like.objects.filter(
            user=request.user,
            post=post
        )

        if like_instance.exists():
            like_instance.delete()
            liked = False
        else:
            Like.objects.create(
                user=request.user,
                post=post
            )
            liked = True

            if post.author != request.user:
                create_and_broadcast_notification(
                    recipient=post.author,
                    sender=request.user,
                    notification_type='like',
                    post=post
                )

        total_likes = Like.objects.filter(post=post).count()

        # Send WebSocket update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"post_{post.id}",
            {
                "type": "like_update",
                "likes": total_likes,
                "liked": liked
            }
        )

        return JsonResponse({
            "success": True,
            "likes": total_likes,
            "liked": liked
        })

    return JsonResponse({"success": False})


@login_required
def comment_post(request, post_id):
    if request.method == "POST":
        post = get_object_or_404(Post, id=post_id)

        content = request.POST.get("content", "").strip()
        if not content:
            return JsonResponse({
                "success": False,
                "message": "Comment cannot be empty."
            })

        prediction = predict_comment(content)
        if prediction == 1:
            return JsonResponse({
                "success": False,
                "message": "Your comment violates our community guidelines."
            })

        comment = Comment.objects.create(
            post=post,
            content=content,
            author=request.user
        )

        if post.author != request.user:
            create_and_broadcast_notification(
                recipient=post.author,
                sender=request.user,
                notification_type="comment",
                post=post,
                comment=comment
            )

        profile_picture_url = request.user.profile_picture.url if request.user.profile_picture else None
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"post_{post.id}",
            {
                "type": "comment_update",
                "comment_id": comment.id,
                "author_id": request.user.id,
                "username": request.user.username,
                "profile_picture": profile_picture_url,
                "comment": comment.content,
                "time": f"{timesince(comment.created_at)} ago"
            }
        )

        return JsonResponse({
            "success": True,
            "comment_id": comment.id,
            "author_username": request.user.username,
            "author_profile_picture": request.user.profile_picture.url if request.user.profile_picture else None,
            "content": comment.content
        })

    return JsonResponse({"success": False})


@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author != request.user:
        return JsonResponse({
            "success": False,
            "message": "You are not authorized to edit this comment."
        }, status=403)

    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Invalid request method."
        }, status=405)

    content = request.POST.get("content", "").strip()
    if not content:
        return JsonResponse({
            "success": False,
            "message": "Comment cannot be empty."
        }, status=400)

    prediction = predict_comment(content)
    if prediction == 1:
        return JsonResponse({
            "success": False,
            "message": "Your comment violates our community guidelines."
        }, status=400)

    comment.content = content
    comment.save()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"post_{comment.post.id}",
        {
            "type": "comment_edited",
            "comment_id": comment.id,
            "comment": comment.content
        }
    )

    return JsonResponse({
        "success": True,
        "comment_id": comment.id,
        "content": comment.content
    })


@login_required
def delete_comment(request, comment_id):
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Invalid request."
        }, status=405)

    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author != request.user:
        return JsonResponse({
            "success": False,
            "message": "You cannot delete this comment."
        }, status=403)

    post_id = comment.post.id
    comment.delete()

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"post_{post_id}",
        {
            "type": "comment_deleted",
            "comment_id": comment_id
        }
    )

    return JsonResponse({
        "success": True,
        "comment_id": comment_id
    })


class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notification = Notification.objects.filter(recipient=request.user).order_by('-created_at')
        serializer = NotificationSerializer(notification, many=True)
        unread_count = notification.filter(is_read=False).count()
        return Response({'notifications': serializer.data, 'unread_count': unread_count})


class MarkNotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return Response({'status': "Success"})


class MarkAllNotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({'status': "Success"})


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')

        if CustomUser.objects.filter(email=email).exists():
            otp = random.randint(100000, 999999)

            send_mail(
                subject="Your OTP Code",
                message=f"Your OTP is {otp}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            response = redirect('verify_otp')
            response.set_cookie('reset_email', email, max_age=300)
            response.set_cookie('reset_otp', otp, max_age=300)

            messages.success(request, "OTP has been sent to your email.")
            return response
        else:
            messages.error(request, "Email not found.")
            return redirect('forgot_password')
    return render(request, 'pages/forgot_password.html')


def verify_otp(request):
    if request.method == "POST":
        otp = request.POST.get('otp')
        saved_otp = request.COOKIES.get('reset_otp')
        if otp == saved_otp:
            messages.success(request, 'OTP verified successfully')
            return redirect('set_password')
        else:
            messages.error(request, 'Invalid OTP')
            return redirect('verify_otp')
    return render(request, 'pages/verify_otp.html')


def set_password(request):
    email = request.COOKIES.get('reset_email')
    if not email:
        messages.error(request, 'Session expired')
        return redirect('forgot_password')
    if request.method == "POST":
        confirm_password = request.POST.get('confirm_password')
        password = request.POST.get('password')
        if password == confirm_password:
            user = CustomUser.objects.get(email=email)
            user.password = make_password(password)
            user.save()
            messages.success(request, 'Password set successfully')
            response = redirect('login')
            response.delete_cookie('reset_email')
            response.delete_cookie('reset_otp')
            return response
        else:
            messages.error(request, 'Passwords do not match')
            return redirect('set_password')
    return render(request, 'pages/set_password.html')


# @staff_member_required
# def admin_users(request):
#     users = CustomUser.objects.all().order_by("-created_at")
#     context = {"users": users}
#     return render(request, "admin/users.html", context)


# @staff_member_required
# def admin_user_detail(request, user_id):
#     user = get_object_or_404(CustomUser, id=user_id)
#     posts = Post.objects.filter(author=user).order_by("-created_at")
#     followers = Follow.objects.filter(following=user).select_related("follower")
#     following = Follow.objects.filter(follower=user).select_related("following")
#     likes_count = Like.objects.filter(user=user).count()
#     comments_count = Comment.objects.filter(author=user).count()

#     context = {
#         "user": user,
#         "posts": posts,
#         "followers": followers,
#         "following": following,
#         "likes_count": likes_count,
#         "comments_count": comments_count,
#     }
#     return render(request, "admin/user_detail.html", context)


# Admin Views for User Blocking Management

@staff_member_required
def admin_dashboard(request):
    """Admin dashboard showing block management overview"""
    total_users = CustomUser.objects.count()
    blocked_users = CustomUser.objects.filter(is_blocked=True).count()
    active_blocks = BlockedUser.objects.filter(is_active=True).count()
    
    context = {
        "total_users": total_users,
        "blocked_users": blocked_users,
        "active_blocks": active_blocks,
    }
    return render(request, "admin/dashboard.html", context)


@staff_member_required
def admin_users(request):
    """Admin view to list all users with block status"""
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', 'all')
    
    users = CustomUser.objects.all().order_by('-created_at')
    
    # Apply search filter
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter == 'blocked':
        users = users.filter(is_blocked=True)
    elif status_filter == 'active':
        users = users.filter(is_blocked=False)
    
    # Paginate results
    from django.core.paginator import Paginator
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        "page_obj": page_obj,
        "users": page_obj.object_list,
        "search_query": search_query,
        "status_filter": status_filter,
        "total_users": CustomUser.objects.count(),
        "blocked_count": CustomUser.objects.filter(is_blocked=True).count(),
    }
    return render(request, "admin/users.html", context)


@staff_member_required
def admin_block_user(request, user_id):
    """Block a user"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == "POST":
        reason = request.POST.get('reason', '').strip()
        
        if not user.is_blocked:
            user.is_blocked = True
            user.blocked_reason = reason
            user.blocked_date = timezone.now()
            user.save()
            
            # Create a block record
            BlockedUser.objects.create(
                user=user,
                blocked_by=request.user,
                reason=reason
            )
            
            messages.success(request, f"User '{user.username}' has been blocked successfully.")
        else:
            messages.warning(request, f"User '{user.username}' is already blocked.")
        
        return redirect('admin_users')
    
    context = {"user": user}
    return render(request, "admin/block_user.html", context)


@staff_member_required
def admin_unblock_user(request, user_id):
    """Unblock a user"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == "POST":
        if user.is_blocked:
            user.is_blocked = False
            user.blocked_reason = ""
            user.blocked_date = None
            user.save()
            
            # Mark all active block records as inactive
            BlockedUser.objects.filter(user=user, is_active=True).update(
                is_active=False,
                unblocked_at=timezone.now()
            )
            
            messages.success(request, f"User '{user.username}' has been unblocked successfully.")
        else:
            messages.warning(request, f"User '{user.username}' is not blocked.")
        
        return redirect('admin_users')
    
    context = {"user": user}
    return render(request, "admin/unblock_user.html", context)


@staff_member_required
def admin_user_detail(request, user_id):
    """View detailed information about a user"""
    user = get_object_or_404(CustomUser, id=user_id)
    posts = Post.objects.filter(author=user).order_by('-created_at')
    followers = Follow.objects.filter(following=user).select_related('follower')
    following = Follow.objects.filter(follower=user).select_related('following')
    likes_count = Like.objects.filter(user=user).count()
    comments_count = Comment.objects.filter(author=user).count()
    
    # Get block history
    block_history = BlockedUser.objects.filter(user=user).order_by('-blocked_at')
    
    context = {
        "user": user,
        "posts": posts,
        "followers": followers,
        "following": following,
        "likes_count": likes_count,
        "comments_count": comments_count,
        "block_history": block_history,
    }
    return render(request, "admin/user_detail_admin.html", context)


@staff_member_required
def admin_blocked_users(request):
    """View all blocked users"""
    search_query = request.GET.get('search', '').strip()
    
    blocked_users = CustomUser.objects.filter(is_blocked=True).order_by('-blocked_date')
    
    if search_query:
        blocked_users = blocked_users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    # Get latest block records for each blocked user
    from django.core.paginator import Paginator
    paginator = Paginator(blocked_users, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        "page_obj": page_obj,
        "blocked_users": page_obj.object_list,
        "search_query": search_query,
        "total_blocked": CustomUser.objects.filter(is_blocked=True).count(),
    }
    return render(request, "admin/blocked_users.html", context)


@staff_member_required  
def admin_block_history(request):
    """View block/unblock history"""
    search_query = request.GET.get('search', '').strip()
    
    block_records = BlockedUser.objects.all().order_by('-blocked_at')
    
    if search_query:
        block_records = block_records.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(blocked_by__username__icontains=search_query)
        )
    
    from django.core.paginator import Paginator
    paginator = Paginator(block_records, 30)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        "page_obj": page_obj,
        "block_records": page_obj.object_list,
        "search_query": search_query,
    }
    return render(request, "admin/block_history.html", context)
