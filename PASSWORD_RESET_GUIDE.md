# Password Reset System - Security & Testing Guide

## 🔒 Security Implementation

The password reset system now properly authenticates users through **email verification**.

### How It Works (Secure Flow):

1. **User requests password reset** → Enters their email address
2. **System validates email** → Checks if email exists in database
3. **Token generated** → Creates secure random token (valid for 1 hour)
4. **Email sent** → Reset link with token sent ONLY to user's email
5. **User receives email** → Only the email owner can access the token
6. **User clicks link** → Redirected to reset password page with token
7. **Password reset** → Token validated, password updated, token marked as used

### Security Features:

✅ **Email verification** - Token only sent to registered email address  
✅ **No token exposure** - Token NOT returned in API response  
✅ **Time-limited** - Tokens expire after 1 hour  
✅ **One-time use** - Tokens invalidated after use  
✅ **Old tokens cleared** - Previous tokens invalidated when new request made  
✅ **Audit logging** - All password changes logged  

---

## 📧 Email Configuration

### Current Setup (Development):
```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```
- Emails printed to **console/terminal** where server is running
- Perfect for development and testing
- No email credentials needed

### To Test:
1. Go to forgot password page: http://127.0.0.1:8000/forgot-password/
2. Enter a valid email (e.g., `admin@cse.edu`)
3. Click "Send Reset Link"
4. **Check your terminal/console** where `python manage.py runserver` is running
5. You'll see the email with the reset link printed there
6. Copy the reset URL and paste in browser

---

## 🚀 Production Email Setup

### Option 1: Gmail (Recommended for testing)
```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-digit-app-password'  # NOT your Gmail password!
DEFAULT_FROM_EMAIL = 'CSE Inventory <your-email@gmail.com>'
```

**To get Gmail App Password:**
1. Enable 2-Factor Authentication on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate new app password for "Mail"
4. Copy the 16-digit password (no spaces)
5. Use that in `EMAIL_HOST_PASSWORD`

### Option 2: Other SMTP Providers
- **SendGrid** - 100 emails/day free
- **Mailgun** - 5,000 emails/month free
- **Amazon SES** - Very cheap, reliable
- **Your hosting provider's SMTP**

---

## 🧪 Testing Guide

### Test Users (from seed data):
| Email | Password | Role |
|-------|----------|------|
| admin@cse.edu | admin123 | Admin |
| manager@cse.edu | manager123 | Manager |
| viewer@cse.edu | viewer123 | Viewer |

### Test Scenarios:

#### 1. Valid Password Reset
1. Go to: http://127.0.0.1:8000/forgot-password/
2. Enter: `admin@cse.edu`
3. Check console for email
4. Copy reset URL from console
5. Paste URL in browser
6. Enter new password (at least 8 characters)
7. Click "Reset Password"
8. Try logging in with new password

#### 2. Invalid Email
1. Enter: `nonexistent@email.com`
2. Should show: "No user found with this email address"

#### 3. Token Expiration
1. Request password reset
2. Wait 1 hour
3. Try to use the token
4. Should show: "Reset link has expired"

#### 4. Token Reuse
1. Successfully reset password
2. Try using same token again
3. Should show: "Reset link has already been used"

---

## 🎯 Why This Fixes The Security Issue

### ❌ BEFORE (Insecure):
```
User enters email → System returns token in API response
Anyone can see the token → Can reset anyone's password
```
**Problem**: No verification that requester owns the email

### ✅ AFTER (Secure):
```
User enters email → System sends token ONLY to that email
Only email owner can access token → Only they can reset password
```
**Solution**: Email ownership proves identity

---

## 📝 What Changed

### Files Modified:

1. **settings.py** - Added email configuration
2. **views.py** - Updated to send emails instead of returning tokens
3. **forgot-password.html** - Removed token display section

### Key Changes:
- `PasswordResetRequestView` now uses Django's `send_mail()`
- Token sent in email body as reset URL
- API response only confirms "email sent" (doesn't expose token)
- Console backend for easy testing during development

---

## 🔍 Monitoring & Security

### Audit Logs:
All password resets are logged in the audit system:
- View at: http://127.0.0.1:8000/audit/
- Filter by action: "Password Reset"
- Shows: timestamp, user, IP address

### Security Best Practices:
1. ✅ Always use HTTPS in production
2. ✅ Keep token expiry short (1 hour)
3. ✅ Invalidate tokens after use
4. ✅ Log all password changes
5. ✅ Never expose tokens in API responses
6. ✅ Use environment variables for email credentials
7. ✅ Implement rate limiting (prevent abuse)

---

## 🐛 Troubleshooting

### "No user found with this email"
- Email doesn't exist in database
- Use one of the test emails: `admin@cse.edu`, `manager@cse.edu`, or `viewer@cse.edu`

### Email not appearing in console
- Make sure `EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'`
- Check the terminal where server is running (not browser)
- Look for "Subject: Password Reset Request"

### Token expired
- Tokens valid for 1 hour only
- Request a new reset link

### Gmail not sending
- Must use App Password, not regular password
- 2FA must be enabled
- Check spam folder

---

## 💡 Next Steps

1. **Test with console backend** (current setup)
2. **Configure Gmail** when ready for real emails
3. **Add rate limiting** to prevent abuse
4. **Customize email template** (make it look nicer)
5. **Add SMS verification** (optional extra security)

---

**Current Status**: ✅ Secure email-based password reset implemented with console backend for easy testing!
