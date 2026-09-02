# 🛡️ Admin User Blocking System - Quick Start Guide

## Installation & Setup

### Step 1: Install Dependencies (if needed)
```bash
cd "d:\videovlogml try2\social-media"
pip install xgboost channels daphne django-extensions
```

### Step 2: Run Database Migrations
```bash
python manage.py migrate
```

This creates the blocking system tables and fields in your database.

### Step 3: Create Admin User (if you don't have one)
```bash
python manage.py createsuperuser
```

### Step 4: Start Django Server
```bash
python manage.py runserver
```

### Step 5: Access the Admin Panel
1. **Django Admin Panel:** http://localhost:8000/admin/
2. **Admin Dashboard:** http://localhost:8000/admin/dashboard/
3. **User Management:** http://localhost:8000/admin/users/

---

## How to Block a User

### Option 1: Using Admin Dashboard (Recommended)
1. Go to http://localhost:8000/admin/users/
2. Search or scroll to find the user
3. Click the **"Block"** button
4. Enter a reason (optional) explaining why the user is blocked
5. Click **"Block User"** to confirm

### Option 2: Using Django Admin Panel
1. Go to http://localhost:8000/admin/
2. Click on **"Custom users"**
3. Find and click on the user
4. Check **"Is blocked"** checkbox
5. Enter a **"Blocked reason"** (optional)
6. Click **"Save"**

---

## How to Unblock a User

### Option 1: Using Admin Dashboard (Recommended)
1. Go to http://localhost:8000/admin/blocked-users/
2. Find the blocked user
3. Click **"Unblock"** button
4. Click **"Unblock User"** to confirm

### Option 2: Using Django Admin Panel
1. Go to http://localhost:8000/admin/
2. Click on **"Custom users"**
3. Find and click on the user
4. Uncheck **"Is blocked"** checkbox
5. Clear the **"Blocked reason"** field
6. Click **"Save"**

---

## Admin Features

### 📊 Dashboard
- View total users count
- View blocked users count
- View active blocks count
- Quick access to all functions

### 👥 User Management
- Search users by username, email, or name
- Filter by status (All / Active / Blocked)
- View user profile picture
- View join date
- One-click block/unblock

### 📋 Blocked Users
- See all currently blocked users
- Search blocked users
- View block date
- View block reason
- Quick unblock option

### 📜 Block History
- Complete history of all actions
- View who blocked whom and when
- View unblock dates
- Two view modes:
  - **Table View** - Traditional data table
  - **Timeline View** - Visual timeline of events
- Search across all history

---

## Key Endpoints

```
/admin/                       - Django Admin Panel
/admin/dashboard/             - Admin Dashboard
/admin/users/                 - User Management List
/admin/users/<id>/            - User Details & History
/admin/users/<id>/block/      - Block User Confirmation
/admin/users/<id>/unblock/    - Unblock User Confirmation
/admin/blocked-users/         - Blocked Users List
/admin/block-history/         - Complete Block History
```

---

## Block History Tracking

Every block/unblock action is logged with:
- ✅ User blocked
- ✅ Admin who performed action
- ✅ Date and time
- ✅ Reason provided
- ✅ Status (Active/Unblocked)
- ✅ Date unblocked (if applicable)

---

## What Happens When User is Blocked?

When you block a user, they:
- ❌ Cannot login to the platform
- ❌ Cannot create new posts
- ❌ Cannot like or comment
- ❌ Cannot send messages
- ❌ Cannot access their profile
- ✅ **Can be unblocked anytime** (all data preserved)

---

## Tips & Best Practices

1. **Always provide a reason** when blocking for compliance and record-keeping
2. **Review block history regularly** to catch trends or patterns
3. **Unblock promptly** when block reason is resolved
4. **Use search feature** to quickly find users
5. **Check user details** before blocking to understand their history
6. **Use timeline view** in block history for better visualization

---

## Troubleshooting

### Issue: Can't access admin panels
**Solution:** Make sure your user account has `is_staff = True`
```bash
python manage.py shell
>>> from accounts.models import CustomUser
>>> user = CustomUser.objects.get(username='your_username')
>>> user.is_staff = True
>>> user.is_superuser = True  # For full access
>>> user.save()
```

### Issue: Template not found error
**Solution:** Make sure all template files are in the correct location:
```
templates/
├── admin/
│   ├── dashboard.html
│   ├── users_list.html
│   ├── block_user.html
│   ├── unblock_user.html
│   ├── user_detail_admin.html
│   ├── blocked_users.html
│   └── block_history.html
```

### Issue: Database error during migration
**Solution:** Run migrations fresh:
```bash
python manage.py migrate --run-syncdb
```

---

## Next Steps

1. ✅ Run migrations
2. ✅ Test blocking a user
3. ✅ Test unblocking a user
4. ✅ Review block history
5. ✅ Customize templates if needed
6. ✅ Train team on usage

---

## Support & Documentation

For more detailed information, see `ADMIN_BLOCKING_SYSTEM.md`

---

**Status:** ✅ Ready to Use  
**Last Updated:** 2024  
**Version:** 1.0
