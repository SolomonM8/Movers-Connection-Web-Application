import json
import os

_firebase_app = None
_firebase_unavailable = False


def _get_firebase_app():
    """Lazily initialize the Firebase app from FIREBASE_CREDENTIALS_JSON.

    Returns None (without raising) when the credentials aren't configured yet,
    so push sending is a silent no-op until Firebase is set up.
    """
    global _firebase_app, _firebase_unavailable
    if _firebase_app is not None:
        return _firebase_app
    if _firebase_unavailable:
        return None

    creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not creds_json:
        _firebase_unavailable = True
        return None

    import firebase_admin
    from firebase_admin import credentials

    cred = credentials.Certificate(json.loads(creds_json))
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def send_push_to_user(user, title, body, url=""):
    """Send a push notification to every registered device for a user.

    No-ops silently if Firebase isn't configured, and skips any device
    token FCM rejects (e.g. the app was uninstalled) rather than raising.
    """
    app = _get_firebase_app()
    if not app:
        return

    from firebase_admin import messaging

    tokens = list(user.device_tokens.values_list("token", flat=True))
    for token in tokens:
        try:
            messaging.send(
                messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data={"url": url or ""},
                    token=token,
                ),
                app=app,
            )
        except Exception:
            continue
