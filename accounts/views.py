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

    like_obj = Like.objects.filter(user=request.user)

    users_likes = like_obj.values_list(
        "post_id",
        flat=True
    )

    context = {
        "posts": posts,
        "users_likes": users_likes,
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
def like_post(request,post_id):
    if request.method=="POST":
        post=Post.objects.get(id=post_id)
        like_instance=Like.objects.filter(user=request.user,post=post)
        if like_instance:
            like_instance.delete()
        else:
            Like.objects.create(user=request.user,post=post)
            if post.author!=request.user:
                Notification.objects.create(recipient=post.author,sender=request.user,notification_type='like',post=post)
        return redirect('home')
    return redirect('home')


@login_required
def comment_post(request, post_id):

    if request.method == "POST":

        post = Post.objects.get(id=post_id)
        content = request.POST.get("content")

        # Predict comment using Logistic Regression
        prediction = predict_comment(content)

        # Reject toxic comments
        if prediction == 1:
            messages.error(
                request,
                "Your comment violates our community guidelines and cannot be posted."
            )
            return redirect("home")

        # Save safe comment
        comment = Comment.objects.create(
            post=post,
            content=content,
            author=request.user
        )

        if post.author != request.user:
            Notification.objects.create(
                recipient=post.author,
                sender=request.user,
                notification_type="comments",
                post=post,
                comment=comment
            )

        messages.success(request, "Comment added successfully.")

        return redirect("home")

    return redirect("home")@login_required

def delete_comment(request,comment_id):
        comment=Comment.objects.get(id=comment_id)
        comment.delete()
        messages.success(request,"comment deleted successfully")
        return redirect('home')

from moderation.comment_predict import predict_comment

@login_required
def edit_comment(request, comment_id):

    comment = Comment.objects.get(id=comment_id)

    if comment.author != request.user:
        messages.error(request, "You are not authorized to edit this comment.")
        return redirect("home")

    if request.method == "POST":

        content = request.POST.get("content")

        prediction = predict_comment(content)

        if prediction == 1:
            messages.error(
                request,
                "Your comment violates our community guidelines."
            )
            return redirect("home")

        comment.content = content
        comment.save()

        messages.success(request, "Comment updated successfully.")

    return redirect("home")

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

