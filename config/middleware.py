from django.conf import settings
from django.http import HttpResponse


class ElectronCorsMiddleware:
    """
    Minimal CORS handling for Electron file:// (Origin: null) and local dev.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_origins = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
        self.allowed_origins.update(
            [
                "http://127.0.0.1:8000",
                "http://localhost:8000",
                "null",
            ]
        )

    def __call__(self, request):
        if (
            request.method == "OPTIONS"
            and request.headers.get("Origin")
            and request.headers.get("Access-Control-Request-Method")
        ):
            response = HttpResponse(status=200)
            return self._add_cors_headers(request, response)

        response = self.get_response(request)
        return self._add_cors_headers(request, response)

    def _add_cors_headers(self, request, response):
        origin = request.headers.get("Origin")
        if origin and origin in self.allowed_origins:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response.setdefault("Vary", "Origin")
            response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken, X-Sessionid"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        return response


class SessionHeaderMiddleware:
    """
    Allow session auth via X-Sessionid header when cookies fail in Electron.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_key = request.headers.get("X-Sessionid")
        if session_key:
            try:
                from django.contrib.sessions.backends.db import SessionStore

                store = SessionStore(session_key=session_key)
                if store.exists(session_key):
                    request.session = store
            except Exception:
                pass

        return self.get_response(request)
