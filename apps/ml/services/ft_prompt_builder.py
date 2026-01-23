"""
FT Prompt Builder (파인튜닝 데이터용)

- 목적: 파인튜닝 학습용 입력 프롬프트를 "짧고 고정된 포맷"으로 생성
- 주의: prompt_generator.py(실시간 생성용)처럼 긴 가이드/섹션을 넣지 않는다.
- 결과: (input_prompt, jsonl_record) 형태로 쉽게 데이터셋 생성 가능
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Tuple
import json


# ==============================
# Config
# ==============================

@dataclass
class FTPromptConfig:
    """
    FT용 입력 프롬프트 설정

    - provider/platform 별로 나누기 전 "리뷰 작성 베이스"용을 가정
    - 학습 안정성을 위해 입력 필드 개수를 제한한다.
    """
    # 최소 필수
    procedure: str

    # 선택(가능하면 일관되게 채우기)
    clinic_name: Optional[str] = None
    doctor_name: Optional[str] = None
    content_type: str = "procedure"  # consultation | procedure | recovery_1month | ...
    timing: Optional[str] = None     # 예: "D+7", "상담 직후", "수술 후 1개월"

    # 환자/상황(짧게)
    concern: Optional[str] = None    # 고민/배경 한 줄
    context: Optional[str] = None    # 상담/시술/회복 상황 한 줄

    # 출력 스타일(아주 짧게)
    tone: Optional[str] = None       # 예: "솔직하고 담담하게", "~요체"
    length_hint: Optional[str] = None  # 예: "500~900자"

    # 안전/제약(FT에 과한 규칙 넣지 말고 최소만)
    avoid: List[str] = field(default_factory=list)  # 예: ["과장 표현", "최종 결과 단정"]

    # 프롬프트 고정 문구
    system_prompt: str = "자연스러운 시술 후기를 작성합니다."


# ==============================
# Builder
# ==============================

class FTPromptBuilder:
    """
    파인튜닝 데이터용 입력 프롬프트 생성기

    핵심 원칙:
    - 입력 포맷은 최대한 고정
    - 길고 복잡한 가이드는 절대 넣지 않음
    - 학습 데이터(assistant 정답) 쪽에 스타일이 담기게 설계
    """

    def __init__(self, cfg: FTPromptConfig):
        self.cfg = cfg
        self._validate()

    def _validate(self) -> None:
        if not self.cfg.procedure or not self.cfg.procedure.strip():
            raise ValueError("procedure는 필수입니다.")
        if self.cfg.content_type not in {
            "consultation", "procedure", "recovery_1month", "recovery_2month", "recovery_3month"
        }:
            # 확장 가능: 여기서 제한을 빡세게 걸면 데이터 품질이 좋아짐
            # 다만 기존 시스템이 더 많은 타입을 쓰면 허용 리스트를 늘리면 됨
            pass

    def build_input_prompt(self) -> str:
        """
        FT 학습용 user 입력 텍스트 생성

        예시 출력:
        시술명: 비절개 인중축소
        컨텐츠: procedure
        시점: D+7
        고민: 인중이 길어 보여서 신경 쓰임
        상황: 회복 부담 적은 시술을 원함
        톤: 솔직하고 담담하게
        길이: 500~900자
        금지: 과장 표현, 최종 결과 단정
        """
        c = self.cfg
        lines: List[str] = []

        # 필수
        lines.append(f"시술명: {c.procedure.strip()}")

        # 고정 필드(가능하면 항상 포함)
        if c.content_type:
            lines.append(f"컨텐츠: {c.content_type}")

        if c.timing:
            lines.append(f"시점: {c.timing}")

        # 선택 필드
        if c.clinic_name:
            lines.append(f"병원: {c.clinic_name}")
        if c.doctor_name:
            lines.append(f"의료진: {c.doctor_name}")

        if c.concern:
            lines.append(f"고민: {c.concern}")
        if c.context:
            lines.append(f"상황: {c.context}")

        if c.tone:
            lines.append(f"톤: {c.tone}")
        if c.length_hint:
            lines.append(f"길이: {c.length_hint}")

        if c.avoid:
            # 너무 길게 쓰지 말고 2~4개 정도로 제한 추천
            avoid_txt = ", ".join([a.strip() for a in c.avoid if a and a.strip()])[:200]
            if avoid_txt:
                lines.append(f"금지: {avoid_txt}")

        return "\n".join(lines).strip()

    def to_jsonl_record(self, target_review_text: str) -> Dict[str, Any]:
        """
        파인튜닝 JSONL 한 줄 레코드 생성

        - target_review_text: 사람이 검수한 '정답 리뷰' (assistant)
        """
        if not target_review_text or not target_review_text.strip():
            raise ValueError("target_review_text(정답 리뷰)가 비어있습니다.")

        user_prompt = self.build_input_prompt()

        return {
            "messages": [
                {"role": "system", "content": self.cfg.system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": target_review_text.strip()},
            ]
        }


# ==============================
# Convenience helpers
# ==============================

def build_ft_prompt(
    *,
    procedure: str,
    clinic_name: Optional[str] = None,
    doctor_name: Optional[str] = None,
    content_type: str = "procedure",
    timing: Optional[str] = None,
    concern: Optional[str] = None,
    context: Optional[str] = None,
    tone: Optional[str] = None,
    length_hint: Optional[str] = None,
    avoid: Optional[List[str]] = None,
) -> str:
    """
    함수형 편의 API: 입력 프롬프트만 필요할 때
    """
    cfg = FTPromptConfig(
        procedure=procedure,
        clinic_name=clinic_name,
        doctor_name=doctor_name,
        content_type=content_type,
        timing=timing,
        concern=concern,
        context=context,
        tone=tone,
        length_hint=length_hint,
        avoid=avoid or [],
    )
    return FTPromptBuilder(cfg).build_input_prompt()


def make_jsonl_line(record: Dict[str, Any]) -> str:
    """
    JSONL 파일에 저장할 1줄 문자열로 변환
    ensure_ascii=False: 한글 보존
    """
    return json.dumps(record, ensure_ascii=False)


def build_ft_record(
    *,
    procedure: str,
    target_review_text: str,
    clinic_name: Optional[str] = None,
    doctor_name: Optional[str] = None,
    content_type: str = "procedure",
    timing: Optional[str] = None,
    concern: Optional[str] = None,
    context: Optional[str] = None,
    tone: Optional[str] = None,
    length_hint: Optional[str] = None,
    avoid: Optional[List[str]] = None,
    system_prompt: str = "자연스러운 시술 후기를 작성합니다.",
) -> Dict[str, Any]:
    """
    함수형 편의 API: 바로 JSONL 레코드 생성
    """
    cfg = FTPromptConfig(
        procedure=procedure,
        clinic_name=clinic_name,
        doctor_name=doctor_name,
        content_type=content_type,
        timing=timing,
        concern=concern,
        context=context,
        tone=tone,
        length_hint=length_hint,
        avoid=avoid or [],
        system_prompt=system_prompt,
    )
    return FTPromptBuilder(cfg).to_jsonl_record(target_review_text)