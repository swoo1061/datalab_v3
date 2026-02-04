import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.data.models import ClinicPost, CrawledPostContent


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

CONTENT_CLASSES = {
    "se-main-container",
    "article_viewer",
    "content",
    "ContentRenderer",
    "se-viewer",
    "post-contents",
    "writeContents",
    "board_view",
    "view_content",
    "con_detail",
    "content__article",
    "bd_cont",
    "board-contents",
    "article_container",
    "article_content",
    "content_area",
    "post_article",
}

CONTENT_IDS = {
    "bo_v_con",
    "article_content",
    "articleBodyContents",
    "postViewArea",
    "contents",
    "content",
}

TITLE_CLASSES = {"title_text", "title", "tit", "post-title", "article-title"}
TITLE_IDS = {"bo_v_title", "postTitle", "articleTitle", "title"}


class TitleContentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._capture_title = 0
        self._capture_content = 0
        self._skip = 0
        self._content_starts = []
        self._title_starts = []
        self.title_parts = []
        self.content_parts = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
            return

        class_attr = attrs_dict.get("class", "")
        classes = set(class_attr.split()) if class_attr else set()
        elem_id = attrs_dict.get("id", "")

        title_start = False
        if tag in {"h1", "h2", "h3"} and (classes & TITLE_CLASSES or elem_id in TITLE_IDS):
            self._capture_title += 1
            title_start = True
        self._title_starts.append((tag, title_start))

        content_start = False
        if tag in {"div", "article", "section"} and (classes & CONTENT_CLASSES or elem_id in CONTENT_IDS):
            self._capture_content += 1
            content_start = True
        self._content_starts.append((tag, content_start))

        if tag == "br":
            if self._capture_title:
                self.title_parts.append("\n")
            if self._capture_content:
                self.content_parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self._skip > 0:
            self._skip -= 1
            return
        if self._title_starts:
            end_tag, started = self._title_starts.pop()
            if started and self._capture_title > 0:
                self._capture_title -= 1
        if self._content_starts:
            end_tag, started = self._content_starts.pop()
            if started and self._capture_content > 0:
                self._capture_content -= 1

    def handle_data(self, data):
        if self._skip:
            return
        text = data.strip()
        if not text:
            return
        if self._capture_title:
            self.title_parts.append(text)
        if self._capture_content:
            self.content_parts.append(text)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def extract_title_content(html: str):
    parser = TitleContentParser()
    parser.feed(html)
    title = _normalize_text(" ".join(parser.title_parts))
    content = _normalize_text("\n".join(parser.content_parts))

    if not title:
        m = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if m:
            title = _normalize_text(re.sub(r"\s+\|\s+.*$", "", m.group(1)))
    if not title:
        m = re.search(r'<meta[^>]+name=["\\\']title["\\\'][^>]+content=["\\\'](.*?)["\\\']', html, flags=re.IGNORECASE)
        if m:
            title = _normalize_text(m.group(1))
    if not title:
        m = re.search(r'<meta[^>]+property=["\\\']og:title["\\\'][^>]+content=["\\\'](.*?)["\\\']', html, flags=re.IGNORECASE)
        if m:
            title = _normalize_text(m.group(1))

    return title, content


def extract_counts(html: str):
    def _to_int(value: str):
        try:
            return int(value.replace(",", ""))
        except Exception:
            return None
    def _find_first_int(patterns):
        for pattern in patterns:
            m = re.search(pattern, html, flags=re.IGNORECASE)
            if m:
                value = _to_int(m.group(1))
                if value is not None:
                    return value
        return None

    views = _find_first_int(
        [
            r"조회(?:수)?\s*([0-9,]+)",
            r"조회수\"?\s*[:=]\s*\"?([0-9,]+)",
            r"(?:viewCount|readCount)\"?\s*[:=]\s*\"?([0-9,]+)",
            r"(?:viewCount|readCount)\\\"?\s*[:=]\s*\\\"?([0-9,]+)",
            r"data-view-count\s*=\s*\"?([0-9,]+)",
            r"조회\s*<[^>]*>\s*([0-9,]+)",
            r"조회수\s*<[^>]*>\s*([0-9,]+)",
        ]
    )
    comments = _find_first_int(
        [
            r"댓글(?:수)?\s*([0-9,]+)",
            r"댓글수\"?\s*[:=]\s*\"?([0-9,]+)",
            r"(?:commentCount|replyCount|commentCnt)\"?\s*[:=]\s*\"?([0-9,]+)",
            r"(?:commentCount|replyCount|commentCnt)\\\"?\s*[:=]\s*\\\"?([0-9,]+)",
            r"comment_count\"?\s*[:=]\s*\"?([0-9,]+)",
            r"data-comment-count\s*=\s*\"?([0-9,]+)",
            r"댓글\s*<[^>]*>\s*([0-9,]+)",
            r"댓글\s*</span>\s*<span[^>]*>\s*([0-9,]+)",
            r"댓글수\s*<[^>]*>\s*([0-9,]+)",
        ]
    )

    return views, comments


def is_login_required(html: str, final_url: str) -> bool:
    if "nidlogin" in final_url or "login" in final_url and "naver.com" in final_url:
        return True
    keywords = [
        "로그인이 필요",
        "로그인 후 이용",
        "회원만 이용",
        "로그인 하세요",
        "Sign in to continue",
    ]
    return any(k in html for k in keywords)


def normalize_url(url: str, platform: str) -> str:
    if platform != "naver":
        return url
    parsed = urlparse(url)
    if parsed.netloc not in {"cafe.naver.com", "m.cafe.naver.com"}:
        return url
    # Already mobile
    if parsed.netloc == "m.cafe.naver.com":
        return url

    qs = parse_qs(parsed.query)
    clubid = qs.get("clubid", [None])[0]
    articleid = qs.get("articleid", [None])[0]
    if clubid and articleid:
        return f"https://m.cafe.naver.com/ca-fe/cafes/{clubid}/articles/{articleid}"

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[1].isdigit():
        cafe_name = parts[0]
        article_id = parts[1]
        return f"https://m.cafe.naver.com/{cafe_name}/{article_id}"

    return url


def sanitize_url(url: str) -> str:
    if not url:
        return url
    cleaned = url.strip()
    if cleaned.startswith("http"):
        return cleaned
    # handle common prefix typos like "fhttps://"
    idx = cleaned.find("http")
    if idx != -1:
        return cleaned[idx:]
    return cleaned


def fetch_html(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
        return html, resp.geturl()


def fetch_html_rendered(url: str, storage_state: str | None = None):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        raise RuntimeError("playwright_missing")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if storage_state:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
                storage_state=storage_state,
            )
        else:
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
            )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Give JS time to render
        try:
            page.wait_for_timeout(1500)
        except Exception:
            pass
        html = page.content()
        final_url = page.url
        context.close()
        browser.close()
        return html, final_url


class Command(BaseCommand):
    help = "ClinicPost URL 기준 크롤링 (네이버 카페/성예사)"

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
        platforms = [p.strip() for p in options["platforms"].split(",") if p.strip()]
        limit = options["limit"]
        months = options["months"]
        dry_run = options["dry_run"]
        skip_if_crawled = options["skip_if_crawled"]
        render_naver = options["render_naver"]
        naver_storage_state = (options.get("naver_storage_state") or "").strip()
        render_seongyesa = options["render_seongyesa"]

        qs = ClinicPost.objects.filter(platform__in=platforms, url__isnull=False).exclude(url="")
        if months and months > 0:
            cutoff = timezone.now() - timezone.timedelta(days=months * 30)
            qs = qs.filter(published_at__isnull=False, published_at__gte=cutoff)

        if skip_if_crawled:
            success_qs = CrawledPostContent.objects.filter(post=OuterRef("pk"), status="success")
            qs = qs.annotate(has_success=Exists(success_qs)).filter(has_success=False)

        if limit:
            qs = qs[:limit]

        total = qs.count()
        self.stdout.write(self.style.NOTICE(f"대상 {total}건 크롤링 시작"))

        processed = 0
        for post in qs:
            processed += 1
            url = post.url
            platform = post.platform
            url = sanitize_url(url)
            fetch_url = normalize_url(url, platform)
            self.stdout.write(f"[{processed}/{total}] {post.id} {platform} {url}")

            status = "success"
            error_message = ""
            title = ""
            content = ""
            views = None
            comments = None
            try:
                if platform == "naver" and render_naver:
                    html, final_url = fetch_html_rendered(fetch_url, storage_state=naver_storage_state or None)
                elif platform == "seongyesa" and render_seongyesa:
                    html, final_url = fetch_html_rendered(fetch_url)
                else:
                    html, final_url = fetch_html(fetch_url)
                if is_login_required(html, final_url):
                    status = "skipped"
                    error_message = "login_required"
                else:
                    title, content = extract_title_content(html)
                    views, comments = extract_counts(html)
                    if not content:
                        status = "skipped"
                        error_message = "content_not_found"
            except RuntimeError as e:
                status = "failed"
                error_message = str(e)
            except urllib.error.HTTPError as e:
                status = "failed"
                error_message = f"http_error:{e.code}"
            except urllib.error.URLError as e:
                status = "failed"
                error_message = f"url_error:{e.reason}"
            except Exception as e:
                status = "failed"
                error_message = f"error:{type(e).__name__}"

            if dry_run:
                self.stdout.write(f"  -> {status} title_len={len(title)} content_len={len(content)}")
                continue

            crawled = CrawledPostContent.objects.create(
                post=post,
                url=url,
                platform=platform,
                title=title,
                content=content,
                views=views,
                comments=comments,
                status=status,
                error_message=error_message,
                content_length=len(content or ""),
            )

            if status in {"success", "skipped"}:
                updated = False
                if views is not None:
                    post.views = views
                    updated = True
                if comments is not None:
                    post.comments = comments
                    updated = True
                if updated:
                    post.last_crawled_at = timezone.now()
                    post.updated_at = timezone.now()
                    post.save(update_fields=["views", "comments", "last_crawled_at", "updated_at"])

            self.stdout.write(
                f"  -> {status} title_len={len(title)} content_len={len(content)} id={crawled.id}"
            )
