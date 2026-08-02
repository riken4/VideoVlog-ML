from django.db import models
from accounts.models import CustomUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import Follow
# Create your models here.

class Post(models.Model):
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="post"
    )

    # New field
    title = models.CharField(max_length=255, blank=True)

    # Keep your existing content field
    content = models.TextField()

    image = models.ImageField(
        upload_to="post_image/",
        blank=True
    )

    # Make video optional
    video = models.FileField(
        upload_to="post_video/",
        blank=True,
        null=True
    )

    # Optional thumbnail
    thumbnail = models.ImageField(
        upload_to="thumbnails/",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_edited = models.BooleanField(default=False)

    def __str__(self):
        return self.title if self.title else f"Post {self.id}"

    @property
    def total_likes(self):
        return self.post.count()

    @property
    def total_comments(self):
        return self.comments.count()
    
class Like(models.Model):
    user=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='user_like')
    post=models.ForeignKey(Post, on_delete=models.CASCADE,related_name='post')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return  f"{self.user.username} like {self.post.id}"


class Comment(models.Model):
    post=models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author=models.ForeignKey(CustomUser, on_delete=models.CASCADE,related_name='user_comments')
    content=models.TextField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
          return f"{self.author.username} comments on{self.post.id}"

class Notification(models.Model):
    NOTIFICATION_TYPES=(
        ('like','Like'),
        ('comment','Comment'),
        ('follow','Follow')
    )
    recipient=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notification')
    sender=models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_notification')
    notification_type=models.CharField(max_length=255, choices=NOTIFICATION_TYPES)
    post=models.ForeignKey(Post, on_delete=models.CASCADE, blank=True, null=True)
    comment=models.ForeignKey(Comment, on_delete=models.CASCADE, blank=True, null=True)
    is_read=models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)    

    def __str__(self):
        return f"{self.notification_type}"
    

# notifications
@receiver(post_save,sender=Follow)
def create_follow_notification(sender,instance,created,**kwargs):
    if created:
        Notification.objects.create(recipient=instance.following,sender=instance.follower,notification_type='follow')
        
class WatchHistory(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="watch_history"
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="watch_history"
    )

    watched_at = models.DateTimeField(auto_now_add=True)

    watch_duration = models.PositiveIntegerField(default=0)
    # Seconds watched

    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-watched_at"]

    def __str__(self):
        return f"{self.user.username} watched {self.post.id}"