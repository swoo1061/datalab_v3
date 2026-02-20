import csv
import os
import re
from datetime import datetime, time
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.data.models import ClinicGuide, ClinicPost
from accounts.models import UserProfile


PLATFORM_LABEL_TO_KEY = {
    "네이버": "naver",
    "JP강남언니": "gn_jp",
    "강남언니": "gangnam",
    "바비톡": "babytok",
    "토닥톡": "todaktok",
    "여신티켓": "yeoshin",
    "성예사": "seongyesa",
    "대다모": "dadamo",
}


def normalize_name(value):
    base = re.split(r"\(", value or "", maxsplit=1)[0]
    base = re.sub(r"\s+", " ", base).strip()
    base = re.sub(r"\s*(병원|의원)\s*$", "", base).strip()
    return base.lower()

def infer_clinic_name_from_filename(filename):
    name = os.path.splitext(os.path.basename(filename or ""))[0]
    name = re.sub(r"\s*DB\s*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*(여론|후기)\s*$", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def normalize_assignee(value):
    if not value:
        return ""
    cleaned = re.sub(r"\s*(매니저|팀장|대표이사|대표)\s*$", "", value).strip()
    return cleaned


def parse_int(value):
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0


def position_from_label(value):
    if not value:
        return "manager"
    if "대표이사" in value or "대표" in value:
        return "ceo"
    if "팀장" in value:
        return "leader"
    return "manager"


def make_username(base, existing):
    seed = re.sub(r"\s+", "", base)
    if not seed:
        seed = "user"
    candidate = seed
    counter = 1
    while candidate in existing:
        counter += 1
        candidate = f"{seed}{counter}"
    return candidate


def get_or_create_assignee(raw_value, users, profiles):
    if not raw_value:
        return None
    name = normalize_assignee(raw_value)
    if not name:
        return None

    for profile in profiles:
        if name == (profile.name or "").strip():
            return profile.user

    for user in users:
        if name == user.username:
            return user
        full_name = f"{user.last_name}{user.first_name}".strip()
        if name == full_name:
            return user

    username_set = {u.username for u in users}
    username = make_username(name, username_set)
    user = get_user_model().objects.create(username=username)
    user.set_unusable_password()
    user.save()
    profile = UserProfile.objects.create(
        user=user,
        name=name,
        position=position_from_label(raw_value),
        is_approved=True,
    )
    users.append(user)
    profiles.append(profile)
    return user


def platform_from_url(url):
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    if "naver.com" in host:
        return "naver"
    if "gangnamunni" in host or "gnunni" in host or "gp-unni" in host:
        return "gangnam"
    if "babytok" in host:
        return "babytok"
    if "todaktok" in host or "todoc" in host:
        return "todaktok"
    if "yeoshin" in host:
        return "yeoshin"
    if "seongyesa" in host:
        return "seongyesa"
    if "dadamo" in host:
        return "dadamo"
    return ""


class Command(BaseCommand):
    help = "Import clinic posts from CSV files in electron-llm-app/csv"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            dest="file",
            help="CSV 파일명(예: 봄빛병원 여론DB.csv). 지정 시 해당 파일만 임포트.",
        )

    def handle(self, *args, **options):
        csv_dir = os.path.join(settings.BASE_DIR, "electron-llm-app", "csv")
        if not os.path.isdir(csv_dir):
            self.stdout.write(self.style.ERROR(f"CSV 폴더 없음: {csv_dir}"))
            return

        clinic_map = {normalize_name(c.name): c for c in ClinicGuide.objects.all()}
        users = list(get_user_model().objects.all())
        profiles = list(UserProfile.objects.select_related("user").all())

        created = 0
        updated = 0
        missing_clinic = 0
        missing_url = 0
        missing_date = 0
        created_clinic = 0

        target_file = options.get("file")
        if not target_file:
            self.stdout.write(self.style.WARNING("기존 게시글 데이터 삭제 중..."))
            ClinicPost.objects.all().delete()
        filenames = []
        if target_file:
            safe_name = os.path.basename(target_file)
            file_path = os.path.join(csv_dir, safe_name)
            if not os.path.exists(file_path):
                self.stdout.write(self.style.ERROR(f"지정한 CSV 파일이 없습니다: {file_path}"))
                return
            filenames = [safe_name]
        else:
            filenames = [f for f in os.listdir(csv_dir) if f.lower().endswith(".csv")]

        for filename in filenames:
            file_path = os.path.join(csv_dir, filename)
            inferred_type = "review" if "후기" in filename else "opinion"
            inferred_clinic_name = infer_clinic_name_from_filename(filename)

            with open(file_path, "r", encoding="utf-8-sig", newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    date_str = (row.get("날짜") or "").strip()
                    title = (row.get("글 제목") or "").strip()
                    url = (row.get("게시글 URL") or "").strip()
                    clinic_raw = (row.get("병원") or "").strip()

                    if not date_str:
                        missing_date += 1
                        continue
                    if not clinic_raw:
                        clinic_raw = inferred_clinic_name or "미지정"
                        if not inferred_clinic_name:
                            missing_clinic += 1

                    if not title and url:
                        title = url
                    if not title:
                        missing_url += 1
                        title = "제목 없음"
                    if not url:
                        missing_url += 1
                        safe_name = re.sub(r"[^0-9a-zA-Z]+", "-", clinic_raw).strip("-") or "post"
                        url = f"https://local.invalid/{safe_name}/{date_str}/{row.get('글 제목', '')}"

                    clinic_key = normalize_name(clinic_raw)
                    clinic = clinic_map.get(clinic_key)
                    if clinic is None:
                        # fallback: partial match
                        for key, value in clinic_map.items():
                            if clinic_key in key or key in clinic_key:
                                clinic = value
                                break
                    if clinic is None:
                        clinic = ClinicGuide.objects.create(name=clinic_raw)
                        clinic_map[normalize_name(clinic_raw)] = clinic
                        created_clinic += 1

                    existing = ClinicPost.objects.filter(clinic=clinic, url=url).first()

                    platform_label = (row.get("?플랫폼") or "").strip()
                    platform = platform_from_url(url) or PLATFORM_LABEL_TO_KEY.get(platform_label, "all")
                    views = parse_int(row.get("조회수"))
                    comments = parse_int(row.get("댓글"))
                    messages = parse_int(row.get("쪽지 수량"))
                    assignee_raw = (row.get("작업자") or "").strip()
                    assignee = get_or_create_assignee(assignee_raw, users, profiles)

                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        missing_date += 1
                        continue
                    published_at = timezone.make_aware(datetime.combine(date_obj, time.min))

                    with transaction.atomic():
                        if existing:
                            ClinicPost.objects.filter(pk=existing.pk).update(
                                assignee=assignee,
                                type=inferred_type,
                                platform=platform,
                                title=title,
                                views=views,
                                comments=comments,
                                message_count=messages,
                                published_at=published_at,
                                created_at=published_at,
                                updated_at=published_at,
                            )
                            updated += 1
                        else:
                            post = ClinicPost.objects.create(
                                clinic=clinic,
                                assignee=assignee,
                                type=inferred_type,
                                platform=platform,
                                title=title,
                                url=url,
                                views=views,
                                comments=comments,
                                message_count=messages,
                                published_at=published_at,
                            )
                            ClinicPost.objects.filter(pk=post.pk).update(
                                created_at=published_at,
                                updated_at=published_at,
                            )
                            created += 1

        self.stdout.write(self.style.SUCCESS(f"가져온 건수: {created}"))
        self.stdout.write(self.style.WARNING(f"업데이트: {updated}"))
        self.stdout.write(self.style.WARNING(f"병원 매칭 실패: {missing_clinic}"))
        self.stdout.write(self.style.WARNING(f"URL/제목 누락: {missing_url}"))
        self.stdout.write(self.style.WARNING(f"새로 생성된 병원: {created_clinic}"))
        self.stdout.write(self.style.WARNING(f"날짜 누락: {missing_date}"))
