"""
접속 로그 미들웨어
"""
from apps.data.models import AccessLog


class AccessLogMiddleware:
    """모든 요청에 대해 접속 로그를 기록하는 미들웨어"""

    # 로깅 제외 경로 (static, api 등)
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/favicon.ico',
        '/__debug__/',
    ]

    # 로깅 제외 확장자
    EXCLUDED_EXTENSIONS = [
        '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.woff', '.woff2', '.ttf'
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 요청 전 처리 - 로그 기록
        self._log_request(request)

        response = self.get_response(request)
        return response

    def _should_log(self, path):
        """로깅 대상인지 확인"""
        # 제외 경로 체크
        for excluded in self.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False

        # 제외 확장자 체크
        for ext in self.EXCLUDED_EXTENSIONS:
            if path.endswith(ext):
                return False

        return True

    def _get_client_ip(self, request):
        """클라이언트 IP 추출"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip

    def _log_request(self, request):
        """요청 로그 기록"""
        path = request.path

        if not self._should_log(path):
            return

        try:
            AccessLog.objects.create(
                ip_address=self._get_client_ip(request),
                path=path,
                method=request.method,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                referer=request.META.get('HTTP_REFERER', '')[:500],
            )
        except Exception:
            # 로깅 실패해도 요청은 계속 처리
            pass
