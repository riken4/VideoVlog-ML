from django.shortcuts import render,redirect
from django.contrib.auth import authenticate,login,logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import CustomUser,Follow
from post.models import Notification,Post,Like,Comment
from post.serializers import NotificationSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.mail import send_mail
from django.conf import settings
import random
from django.contrib.auth.hashers import make_password
from post.train_model import train
from django.shortcuts import get_object_or_404

from post.hybrid import hybrid_recommend
from moderation.comment_predict import predict_comment
from django.http import JsonResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils.timesince import timesince

# Create your views here.


def signup_view(request):
    if request.user is authenticate:
        return redirect('home')
    if request.method=="POST":
        username=request.POST.get("username")
        email=request.POST.get("email")
        bio=request.POST.get("bio")
        location=request.POST.get("location")
        profile_picture = request.FILES.get("profile_picture")
        password = request.POST.get("password")
        password2 = request.POST.get("password2")
        
        if password != password2:
            messages.error(request, "Password don't match")
            return redirect('signup')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "email already exist")   
            return redirect('signup')
        
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exist")   
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
        messages.success(request,'user created successfully')
        return redirect('home')
    return render(request, 'pages/signup.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method=="POST":
        username=request.POST.get('username')
        password=request.POST.get('password')
        user=authenticate(request,username=username,password=password)

        if user is not None:
            login(request,user)
            messages.success(request,f"Welcome back ,{user.username}")
            return redirect("home")
        else:
            messages.error(request,"invalid username and password")
            return redirect("login")
    return render(request,"pages/login.html")

def logout_view(request):
    logout(request)
    messages.info(request,"logout successfully")
    return redirect("login")

def profile_view(request,username):
    profile_user=CustomUser.objects.get(username=username)
    posts=Post.objects.filter(author=profile_user).order_by('-created_at')
    is_following=False
    if Follow.objects.filter(follower=request.user,following=profile_user).exists():
         is_following=True
    context={
        'profile_user':profile_user,
        'posts':posts,
        'is_following':is_following,
        'following_count':profile_user.get_following_count(),
        'followers_count':profile_user.get_followers_count(),
    }    
    return render(request,'pages/profile.html',context)

@login_required
def edit_profile_view(request):
    if request.method=="POST":
        user=request.user
        bio=request.POST.get('bio')
        location=request.POST.get('location')
        profile_picture=request.FILES.get('profile_picture')
        user.bio=bio
        user.location=location
        user.profile_picture=profile_picture
        user.save()
        messages.success(request,"updated successfully")
        return redirect("profile",username=user.username)
    return render(request,"pages/edit_profile.html")

@login_required
def my_profile_view(request):
    user=request.user
    myprofile=CustomUser.objects.get(username=user)
    posts=myprofile.posts.all()
    context={
        'profile_user':myprofile,
        'posts':posts,
        'following_count':myprofile.get_following_count(),
        'followers_count':myprofile.get_followers_count(),
    }    
    return render(request,'pages/myprofile.html',context)

@login_required
def follow_toggle(request,username):
    if request.method=="POST":
        user_to_follow=CustomUser.objects.get(username=username)
        if request.user==user_to_follow:
            messages.error(request,"You cannot follow yourself")
            return redirect("profile",username=username)
        follow_instance = Follow.objects.filter(follower=request.user,following=user_to_follow).first()
        if follow_instance:
            follow_instance.delete()
        else:
            Follow.objects.create(follower=request.user,following=user_to_follow)
            messages.success(request,f"you follow {username}")
            Notification.objects.create(
                recipient=user_to_follow,
                sender=request.user,
                notification_type='follow'
            )
        return redirect('profile',username=username)
    return redirect('home')

from post.hybrid import hybrid_recommend
from post.models import Post, Like

@login_required
def home_view(request):

    latest_post = (
        Post.objects
        .order_by("-created_at")
        .first()
    )

    if latest_post:

        posts = hybrid_recommend(
            user=request.user,
            current_post_id=latest_post.id,
            top_n=20
        )

    else:

        posts = Post.objects.none()

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
def create_post(request):
    if request.method == "POST":
        content = request.POST.get('content')
        video = request.FILES.get('video')
        image = request.FILES.get('image')

        if content:
            post = Post.objects.create(
                content=content,
                video=video,
                image=image,
                author=request.user
            )

            # Retrain recommendation model
            train()

            messages.success(request, "Post created successfully")
        else:
            messages.error(request, "Content cannot be empty")
            return redirect("home")

    return redirect("home")


@login_required
def edit_post(request, post_id):
    post = Post.objects.get(id=post_id)

    if request.method == "POST":

        content = request.POST.get("content")

        # Check the edited content
        prediction = predict_comment(content)

        # Reject toxic content
        if prediction == 1:
            messages.error(
                request,
                "Your post contains inappropriate content and cannot be updated."
            )
            return redirect("edit_post", post_id=post.id)

        # Update post if content is safe
        post.content = content
        post.is_edited = True
        post.save()

        messages.success(request, "Post edited successfully.")
        return redirect("home")

    return render(request, "pages/edit_post.html", {"post": post})

@login_required
def delete_post(request,post_id):
    post=Post.objects.get(id=post_id)
    post.delete()
    messages.success(request,"Post deleted successfully")
    return redirect("home")



@login_required
def like_post(request, post_id):

    if request.method == "POST":

        post = Post.objects.get(id=post_id)

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

                Notification.objects.create(
                    recipient=post.author,
                    sender=request.user,
                    notification_type='like',
                    post=post
                )


        # Total like count
        total_likes = Like.objects.filter(
            post=post
        ).count()


        # Send WebSocket update
        channel_layer = get_channel_layer()

        async_to_sync(
            channel_layer.group_send
        )(
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


    return JsonResponse({
        "success": False
    })
from moderation.comment_predict import predict_comment

@login_required
def comment_post(request, post_id):

    if request.method == "POST":

        post = Post.objects.get(id=post_id)

        content = request.POST.get("content", "").strip()
        if not content:
            return JsonResponse({
        "success": False,
        "message": "Comment cannot be empty."
            })

        # Toxicity prediction
        prediction = predict_comment(content)

        if prediction == 1:

            return JsonResponse({
                "success": False,
                "message": "Your comment violates our community guidelines."
            })

        # Save comment
        comment = Comment.objects.create(
            post=post,
            content=content,
            author=request.user
        )

        # Notification
        if post.author != request.user:

            Notification.objects.create(
                recipient=post.author,
                sender=request.user,
                notification_type="comments",
                post=post,
                comment=comment
            )

        # WebSocket update
        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"post_{post.id}",
            {
                "type": "comment_update",
                "comment_id": comment.id,
                "author_id": request.user.id,
                "username": request.user.username,
                "comment": comment.content,
                "time": timesince(comment.created_at)
            }
        )

        return JsonResponse({
            "success": True,
            "username": request.user.username,
            "comment": comment.content
        })

    return JsonResponse({
        "success": False
    })


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

    # -------------------------
    # SEND REAL-TIME DELETE
    # -------------------------

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
from moderation.comment_predict import predict_comment

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

    # -------------------------
    # SEND REAL-TIME UPDATE
    # -------------------------

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
class NotificationListAPIView(APIView):
    permission_classes=[IsAuthenticated]
    
    def get(self,request):
        notification = Notification.objects.filter(recipient=request.user)
        serializer=NotificationSerializer(notification,many=True)
        unread_count=notification.filter(is_read=False).count()
        return Response({'notifications':serializer.data,'unread_count':unread_count})

   
class MarkNotificationReadAPIView(APIView):
    permission_classes=[IsAuthenticated]
    
    def post(self,request,notification_id):
        notification = Notification.objects.get(id=notification_id)
        notification.is_read=True
        notification.save()
        return Response({'status': "Success"})

   
class MarkAllNotificationReadAPIView(APIView):  
    permission_classes=[IsAuthenticated]
    
    def post(self,request):
        notification = Notification.objects.filter(recipient=request.user,is_read=False).update(is_read=True)
        return Response({'status': "Success"})
    
def sendmail(email):
    send_mail(
        subject="test",
        message="test message",
        from_email=settings.EMAIL_HOST,
        recipient_list=[email],
        fail_silently=False
    )
   

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')

        # check if user exists
        if CustomUser.objects.filter(email=email).exists():
            otp = random.randint(100000, 999999)

            # send email
            send_mail(
                subject="Your OTP Code",
                message=f"Your OTP is {otp}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            # redirect and set cookies
            response = redirect('verify_otp')
            response.set_cookie('reset_email', email, max_age=300)
            response.set_cookie('reset_otp', otp, max_age=300)

            messages.success(request, "OTP has been sent to your email.")
            return response
        else:
            messages.error(request, "Email not found.")
            return redirect('forgot_password.html')
    return render(request, 'pages/forgot_password.html')

def verify_otp(request):
    if request.method == "POST":
        otp= request.POST.get('otp')
        saved_otp=request.COOKIES.get('reset_otp')
        if otp == saved_otp:
            messages.success(request,'otp verified sucessfully')
            return redirect('set_password')
        else:
            messages.success(request,'Invalid otp')
            return redirect('verify_otp')
    return render(request,'pages/verify_otp.html')

def set_password(request):
    email=request.COOKIES.get('reset_otp')
    if not email:
        messages.error(request,'cookie expired')
        return redirect('forget_password')
    if request.method=="POST":
        confirm_password=request.POST.get('confirm_password')
        password=request.POST.get('password')
        if password==confirm_password:
            user=CustomUser.objects.get(email=email)
            user.password=make_password(password)
            user.save()
            messages.success(request,'message set sucessfully')
            response=redirect('login')
            response.delete_cookie('reset_email')
            response.delete_cookie('reset_otp')
            return response
    return redirect('set_password')

