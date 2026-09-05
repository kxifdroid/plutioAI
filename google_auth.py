"""Google OAuth 2.0 authentication client for PlutioAI."""

from __future__ import annotations

import os
import urllib.parse
from typing import Any, Dict, Optional
import requests


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPES = "openid email profile"


class GoogleAuthClient:
    """Handles Google OAuth 2.0 authorization, token exchange, and userinfo."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ):
        self.client_id = (os.environ.get("GOOGLE_CLIENT_ID", "") if client_id is None else client_id).strip()
        self.client_secret = (os.environ.get("GOOGLE_CLIENT_SECRET", "") if client_secret is None else client_secret).strip()
        self.redirect_uri = (os.environ.get("GOOGLE_REDIRECT_URI", "") if redirect_uri is None else redirect_uri).strip()

    def is_configured(self) -> bool:
        """Return True if required Google OAuth credentials are present."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str, redirect_uri: Optional[str] = None) -> str:
        """Generate Google OAuth authorization redirect URL."""
        if not self.is_configured():
            raise ValueError("Google OAuth credentials are not configured.")

        cb_url = redirect_uri or self.redirect_uri
        if not cb_url:
            raise ValueError("Redirect URI is required for Google OAuth.")

        params = {
            "client_id": self.client_id,
            "redirect_uri": cb_url,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Exchange authorization code for access and ID tokens."""
        if not self.is_configured():
            raise ValueError("Google OAuth credentials are not configured.")

        cb_url = redirect_uri or self.redirect_uri
        if not cb_url:
            raise ValueError("Redirect URI is required for Google OAuth.")

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": cb_url,
        }
        resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch user profile information using access token."""
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
