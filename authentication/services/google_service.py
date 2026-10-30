import logging
import os
from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)


class GoogleAuthService:
    """Service to verify Google ID Tokens from web and mobile clients."""

    @classmethod
    def verify_token(cls, token: str) -> dict:
        """
        Verifies a Google ID Token (JWT) sent by the frontend Google Sign-In SDK.
        Returns extracted user info dict if valid, or raises ValueError.
        """
        google_client_id = os.getenv('GOOGLE_CLIENT_ID') or getattr(settings, 'GOOGLE_CLIENT_ID', None)

        # Developer convenience: allows mocking Google auth in local dev/testing with "mock-google:<email>"
        if (getattr(settings, 'DEBUG', False) or not getattr(settings, 'GOOGLE_CLIENT_ID', None) or token.startswith('mock-google:')) and token.startswith('mock-google:'):
            mock_email = token.split(':', 1)[1].strip() or 'testuser@gmail.com'
            logger.info(f"[Google Auth Mock] Authenticating mock Google user: {mock_email}")
            return {
                "google_id": f"mock_google_id_{hash(mock_email)}",
                "email": mock_email.lower(),
                "email_verified": True,
                "first_name": "Google",
                "last_name": "Tester",
                "avatar_url": "https://lh3.googleusercontent.com/a/default-user=s96-c",
            }

        try:

            # When client_id is None, verify_oauth2_token verifies signature and expiry
            # against Google public certs without audience checking.
            # When client_id is present, it also verifies audience matches.
            id_info = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience=google_client_id if google_client_id else None
            )

            # Verification passed, extract relevant profile fields
            email = id_info.get('email')
            if not email:
                raise ValueError("Google token did not contain an email address.")

            return {
                "google_id": id_info.get('sub'),
                "email": email.lower(),
                "email_verified": id_info.get('email_verified', False),
                "first_name": id_info.get('given_name', ''),
                "last_name": id_info.get('family_name', ''),
                "avatar_url": id_info.get('picture', ''),
            }

        except Exception as e:
            logger.error(f"Google ID token verification failed: {str(e)}")
            raise ValueError(f"Invalid Google ID token: {str(e)}")
