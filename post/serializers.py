from rest_framework import serializers
from django.db import models
from .models import Notification 
from accounts.models import CustomUser


class NotificationSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    sender_profile_picture = serializers.CharField(source='sender.profile_picture', read_only=True)
    
    class Meta:
        model = Notification
        fields = ['id', 'sender_username', 'sender_profile_picture', 'notification_type', 'is_read', 'created_at']