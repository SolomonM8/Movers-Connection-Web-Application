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


def _send_to_tokens(tokens, title, body, url):
    """Attempt delivery to each token, returning (token, ok, error) for each."""
    app = _get_firebase_app()
    if not app:
        return [(t, False, "Firebase not configured") for t in tokens]

    from firebase_admin import messaging

    results = []
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
            results.append((token, True, None))
        except Exception as exc:
            results.append((token, False, str(exc)))
    return results


def send_push_to_user(user, title, body, url=""):
    """Send a push notification to every registered device for a user.

    No-ops silently if Firebase isn't configured, and skips any device
    token FCM rejects (e.g. the app was uninstalled) rather than raising.
    """
    tokens = list(user.device_tokens.values_list("token", flat=True))
    _send_to_tokens(tokens, title, body, url)
