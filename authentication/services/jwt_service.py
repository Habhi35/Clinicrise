from rest_framework_simplejwt.tokens import RefreshToken


def get_tokens_for_user(user) -> dict:
    """
    Generates SimpleJWT access and refresh tokens for a user,
    enriching the token payload with essential user claims.
    """
    refresh = RefreshToken.for_user(user)

    # Attach custom claims for frontend consumption
    refresh['email'] = user.email
    refresh['phone_number'] = user.phone_number
    refresh['full_name'] = user.full_name
    refresh['is_staff'] = user.is_staff

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
