from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.

class CustomUser(AbstractUser):
    bio=models.TextField(max_length=255,blank=True)
    profile_picture=models.ImageField(upload_to="pic/",blank=True)
    location=models.CharField(max_length=255,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

    def get_followers_count(self):
        return self.followers.count()
    
    def get_following_count(self):
        return self.following.count()
    
class Follow(models.Model):
    follower=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='following')    
    following=models.ForeignKey(CustomUser, on_delete=models.CASCADE,related_name='followers')
    created_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.follower.username} follows{self.following}"

