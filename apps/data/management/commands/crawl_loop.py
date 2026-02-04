import time
from datetime import datetime, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "지정 간격으로 크롤링 반복 실행 (기본 6시간)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval-hours",
            type=float,
            default=6.0,
            help="실행 간격(시간). 기본 6",
        )
        parser.add_argument(
            "--platforms",
            default="naver,seongyesa",
            help="크롤링 플랫폼 (comma-separated, default: naver,seongyesa)",
        )
        parser.add_argument("--limit", type=int, default=0, help="처리 개수 제한 (0=전체)")
        parser.add_argument(
            "--months",
            type=int,
            default=0,
            help="게시글 작성일(published_at) 기준 최근 N개월만 처리 (0=전체)",
        )
        parser.add_argument("--dry-run", action="store_true", help="저장 없이 테스트")
        parser.add_argument(
            "--skip-if-crawled",
            action="store_true",
            help="이미 성공 크롤링 이력이 있으면 스킵",
        )
        parser.add_argument(
            "--render-naver",
            action="store_true",
            help="네이버 카페는 Playwright로 렌더링하여 수집",
        )
        parser.add_argument(
            "--naver-storage-state",
            default="",
            help="네이버 로그인 storage_state 경로 (Playwright).",
        )
        parser.add_argument(
            "--render-seongyesa",
            action="store_true",
            help="성예사는 Playwright로 렌더링하여 수집",
        )
        parser.add_argument("--once", action="store_true", help="1회만 실행 후 종료")

    def handle(self, *args, **options):
        interval_hours = max(options["interval_hours"], 0.1)
        platforms = options["platforms"]
        limit = options["limit"]
        months = options["months"]
        dry_run = options["dry_run"]
        skip_if_crawled = options["skip_if_crawled"]
        render_naver = options["render_naver"]
        naver_storage_state = (options.get("naver_storage_state") or "").strip()
        render_seongyesa = options["render_seongyesa"]
        once = options["once"]

        self.stdout.write(
            self.style.NOTICE(
                f"크롤링 루프 시작 (간격 {interval_hours}시간, platforms={platforms})"
            )
        )

        while True:
            started = datetime.now()
            try:
                call_command(
                    "crawl_clinic_posts",
                    platforms=platforms,
                    limit=limit,
                    months=months,
                    dry_run=dry_run,
                    skip_if_crawled=skip_if_crawled,
                    render_naver=render_naver,
                    naver_storage_state=naver_storage_state,
                    render_seongyesa=render_seongyesa,
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"크롤링 실패: {exc}"))

            if once:
                self.stdout.write(self.style.SUCCESS("1회 실행 완료, 종료합니다."))
                break

            next_run = started + timedelta(hours=interval_hours)
            self.stdout.write(self.style.NOTICE(f"다음 실행 예정: {next_run:%Y-%m-%d %H:%M:%S}"))
            time.sleep(interval_hours * 3600)
