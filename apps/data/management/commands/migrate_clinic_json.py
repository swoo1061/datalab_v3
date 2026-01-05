from django.core.management.base import BaseCommand
from apps.data.models import ClinicGuide, ClinicDoctor, ClinicPrice
from django.db import transaction


class Command(BaseCommand):
    help = "ClinicGuide JSON(doctors, price_list)을 ClinicDoctor / ClinicPrice 모델로 이전"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("▶ 병원 JSON → 모델 마이그레이션 시작"))

        clinics = ClinicGuide.objects.all()

        for clinic in clinics:
            self.stdout.write(f"\n🏥 병원: {clinic.name}")

            # -------------------------
            # 1️⃣ 의료진 이전
            # -------------------------
            doctor_map = {}  # code/name → ClinicDoctor

            doctors_json = clinic.doctors or []
            for idx, d in enumerate(doctors_json):
                name = d.get("name")
                if not name:
                    continue

                code = d.get("code") or name

                doctor, created = ClinicDoctor.objects.get_or_create(
                    clinic=clinic,
                    name=name,
                    defaults={
                        "code": code,
                        "style": d.get("style", ""),
                        "specialties": d.get("specialties", []),
                        "order": idx,
                        "is_active": True,
                    }
                )

                if not created:
                    # 기존 데이터 업데이트 (선택)
                    doctor.code = doctor.code or code
                    doctor.style = doctor.style or d.get("style", "")
                    doctor.specialties = doctor.specialties or d.get("specialties", [])
                    doctor.save()

                doctor_map[code] = doctor
                doctor_map[name] = doctor

                self.stdout.write(
                    self.style.SUCCESS(f"  👨‍⚕️ 원장 {'생성' if created else '존재'}: {name}")
                )

            # -------------------------
            # 2️⃣ 수가 이전
            # -------------------------
            prices_json = clinic.price_list or []

            for idx, p in enumerate(prices_json):
                procedure = p.get("procedure")
                if not procedure:
                    continue

                doctor_code = p.get("doctor_code") or p.get("doctor")
                doctor = doctor_map.get(doctor_code)

                price_display = (
                    p.get("price_display")
                    or p.get("price")
                    or (
                        f"{p.get('price_a')}~{p.get('price_b')}만원"
                        if p.get("price_a") or p.get("price_b")
                        else ""
                    )
                )

                price, created = ClinicPrice.objects.get_or_create(
                    clinic=clinic,
                    doctor=doctor,
                    procedure=procedure,
                    defaults={
                        "price_display": price_display,
                        "note": p.get("note", ""),
                        "order": idx,
                        "is_active": True,
                    }
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"    💰 수가 {'생성' if created else '존재'}: "
                        f"{procedure} ({price_display or '상담 필요'})"
                    )
                )

        self.stdout.write(self.style.SUCCESS("\n✅ JSON → 모델 이전 완료"))