import hashlib
import re
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.data.models import CrawledPostContent
from apps.ml.services.ft_prompt_builder import build_ft_record, make_jsonl_line


def _clean_text(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"<[^>]+>", " ", text)
    t = re.sub(r"(더보기|펼치기|접기|원본|원문|출처)\s*", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "CrawledPostContent에서 본문을 추출해 파인튜닝 JSONL 생성"

    def add_arguments(self, parser):
        parser.add_argument("--output", default="ft_crawled.jsonl")
        parser.add_argument("--platforms", default="")
        parser.add_argument("--min-length", type=int, default=200)
        parser.add_argument("--max-length", type=int, default=3000)
        parser.add_argument("--months", type=int, default=0)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--procedure-source",
            choices=["title", "default"],
            default="title",
        )
        parser.add_argument("--default-procedure", default="리뷰 시술")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        output_path = options["output"]
        platforms = [p.strip() for p in options["platforms"].split(",") if p.strip()]
        min_len = options["min_length"]
        max_len = options["max_length"]
        months = options["months"]
        limit = options["limit"]
        procedure_source = options["procedure_source"]
        default_procedure = options["default_procedure"]
        dry_run = options["dry_run"]

        qs = CrawledPostContent.objects.select_related("post", "post__clinic").filter(
            status="success",
        ).exclude(content__isnull=True).exclude(content__exact="")

        if platforms:
            qs = qs.filter(platform__in=platforms)

        if months:
            cutoff = timezone.now() - timedelta(days=30 * months)
            qs = qs.filter(fetched_at__gte=cutoff)

        qs = qs.order_by("-fetched_at")

        seen = set()
        rows = []
        total = 0
        kept = 0

        for item in qs.iterator(chunk_size=500):
            total += 1
            content = _clean_text(item.content)
            if not content:
                continue
            if len(content) < min_len or len(content) > max_len:
                continue
            h = _hash_text(content)
            if h in seen:
                continue
            seen.add(h)

            post = item.post
            clinic_name = post.clinic.name if post and post.clinic_id else None
            doctor_name = post.doctor_name if post and post.doctor_name else None
            if procedure_source == "title" and post and post.title:
                procedure = post.title.strip()
            else:
                procedure = default_procedure

            content_type = "procedure"
            if post and post.review_subtype == "consultation":
                content_type = "consultation"

            record = build_ft_record(
                procedure=procedure,
                clinic_name=clinic_name,
                doctor_name=doctor_name,
                content_type=content_type,
                target_review_text=content,
            )
            rows.append(make_jsonl_line(record))
            kept += 1

            if limit and kept >= limit:
                break

        if dry_run:
            self.stdout.write(
                f"DRY RUN: total={total} kept={kept} output={output_path}"
            )
            return

        with open(output_path, "w", encoding="utf-8") as fout:
            for line in rows:
                fout.write(line + "\n")

        self.stdout.write(
            f"완료: total={total} kept={kept} output={output_path}"
        )
