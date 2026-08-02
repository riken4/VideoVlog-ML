from django.contrib import admin
from .models import CustomUser, Follow
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model


# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin ):
    CustomUser = get_user_model()
    list_display = ('id' ,'username', 'email', 'first_name', 'last_name', 'profile_picture', 'bio', 'location', 'created_at', 'updated_at')

admin.site.register(Follow)

