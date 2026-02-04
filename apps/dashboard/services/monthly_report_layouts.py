"""
월간 보고서 레이아웃 프리셋
- 병원마다 보고서 틀이 달라도 공통 엔진으로 렌더링하기 위한 설정
"""

from copy import deepcopy


DEFAULT_LAYOUT = {
    "title": "월간 작업 보고서",
    "subtitle": "월 단위 작업/게시글/리뷰 현황",
    "section_order": [
        "summary_kpi",
        "platform_mix",
        "generated_status",
        "worklog_detail",
        "recent_posts",
    ],
    "labels": {
        "summary_kpi": "요약 지표",
        "platform_mix": "플랫폼 분포",
        "generated_status": "AI 리뷰 상태",
        "worklog_detail": "작업 로그",
        "recent_posts": "최근 게시글",
    },
}


CLINIC_LAYOUT_OVERRIDES = {
    # 샘플 xlsm 구조 기반: 마케팅 보고서 느낌 우선
    "다름성형외과": {
        "title": "월간 마케팅 보고서",
        "subtitle": "네이버/성예사 중심 월별 성과 리포트",
        "section_order": [
            "summary_kpi",
            "platform_mix",
            "recent_posts",
            "generated_status",
            "worklog_detail",
        ],
    },
}


def get_monthly_report_layout(clinic_name: str | None):
    layout = deepcopy(DEFAULT_LAYOUT)
    if clinic_name and clinic_name in CLINIC_LAYOUT_OVERRIDES:
        override = CLINIC_LAYOUT_OVERRIDES[clinic_name]
        layout.update({k: v for k, v in override.items() if k != "labels"})
        if "labels" in override:
            layout["labels"].update(override["labels"])
    return layout
