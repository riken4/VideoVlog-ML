from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.

class CustomUser(AbstractUser):
    bio=models.TextField(max_length=255,blank=True)
    profile_picture=models.ImageField(upload_to="pic/",blank=True)
    location=models.CharField(max_length=255,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    is_blocked=models.BooleanField(default=False)
    blocked_reason=models.TextField(blank=True, null=True)
    blocked_date=models.DateTimeField(null=True, blank=True)

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


class BlockedUser(models.Model):
    user=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='blocked_records')
    blocked_by=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='users_blocked_by_admin')
    reason=models.TextField(blank=True)
    blocked_at=models.DateTimeField(auto_now_add=True)
    unblocked_at=models.DateTimeField(null=True, blank=True)
    is_active=models.BooleanField(default=True)

    class Meta:
        ordering = ['-blocked_at']

    def __str__(self):
        return f"{self.user.username} blocked on {self.blocked_at}"

