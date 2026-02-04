from django.core.management.base import BaseCommand

from apps.data.models import ClinicPost


class Command(BaseCommand):
    help = "Backfill opinion/review subtypes for clinic posts when missing."

    def handle(self, *args, **options):
        updated = 0
        qs = (
            ClinicPost.objects
            .filter(type__in=["opinion", "review"])
            .prefetch_related("photos")
        )

        for post in qs:
            if post.type == "opinion":
                if post.opinion_subtype:
                    continue
                post.opinion_subtype = "concern"
                post.save(update_fields=["opinion_subtype"])
                updated += 1
                continue

            if post.type == "review":
                if post.review_subtype:
                    continue
                title = (post.title or "")
                if "상담" in title:
                    post.review_subtype = "consultation"
                elif post.photos.exists():
                    post.review_subtype = "photo"
                else:
                    post.review_subtype = "text"
                post.save(update_fields=["review_subtype"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"Updated {updated} posts."))
