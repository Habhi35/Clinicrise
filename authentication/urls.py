from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from authentication.views import (
    GoogleAuthView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    SendOTPView,
    UserProfileView,
    VerifyOTPView,
)

app_name = 'authentication'

urlpatterns = [
    # Mobile OTP Authentication
    path('otp/send/', SendOTPView.as_view(), name='otp_send'),
    path('otp/verify/', VerifyOTPView.as_view(), name='otp_verify'),

    # Google Authentication
    path('google/', GoogleAuthView.as_view(), name='google_auth'),

    # Session & JWT Management
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', UserProfileView.as_view(), name='user_profile'),

    # Account Recovery & Password Management
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),

    # Standard Email/Password Auth
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
]
