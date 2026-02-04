"""
LLM 서비스 - 리뷰 생성

OpenAI 및 Claude API를 사용하여 자연스러운 리뷰를 생성합니다.
"""
import base64
import re
import json
from openai import OpenAI
from anthropic import Anthropic
from django.conf import settings
from typing import Optional, Dict, List
from apps.ml.services.prompt_generator import TONE_KEYWORDS


# 클라이언트 초기화 (싱글톤)
_openai_client = None
_anthropic_client = None


# 사용 가능한 모델 정의 (가격: $/1M tokens)
AVAILABLE_MODELS = {
    "openai": {
        "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk": {
            "name": "구공이(V_3)",
            "desc": "파인튜닝 모델. 리뷰 생성 전용.",
            "max_tokens": 4096,
            "input_price": 0.30,
            "output_price": 1.20,
            "cached_input_price": 0.03,
        },
        "gpt-5-mini": {"name": "GPT-5 Mini", "desc": "저렴. 약간 느리고 중품질. 멍청.", "max_tokens": 4096,
                      "input_price": 0.25, "output_price": 2.00, "cached_input_price": 0.025},
        "gpt-5.2": {"name": "GPT-5.2", "desc": "일반. 빠르고 고품질. 똑똑. (추천)", "max_tokens": 4096,
                   "input_price": 1.75, "output_price": 14.00, "cached_input_price": 0.175},
    },
    "claude": {
        "claude-sonnet-4-5-20250929": {"name": "Claude Sonnet 4.5", "desc": "일반. 빠르고 고품질. 똑똑. (추천)", "max_tokens": 4096,
                                       "input_price": 3.00, "output_price": 15.00, "cached_input_price": 0.30},
        "claude-opus-4-5-20251101": {"name": "Claude Opus 4.5", "desc": "비쌈. 빠르고 초고품질. 개똑똑.", "max_tokens": 4096,
                                     "input_price": 5.00, "output_price": 25.00, "cached_input_price": 0.50},
    }
}


def get_model_pricing(model: str) -> dict:
    """모델의 가격 정보 반환"""
    for provider, models in AVAILABLE_MODELS.items():
        if model in models:
            return {
                "input_price": models[model].get("input_price", 0),
                "output_price": models[model].get("output_price", 0),
                "cached_input_price": models[model].get("cached_input_price", 0),
            }
    return {"input_price": 0, "output_price": 0, "cached_input_price": 0}


def calculate_cost(model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    """토큰 사용량으로 비용 계산 (USD)

    Args:
        model: 모델 ID
        input_tokens: 입력 토큰 (캐시 제외)
        output_tokens: 출력 토큰
        cached_input_tokens: 캐시된 입력 토큰
    """
    pricing = get_model_pricing(model)
    # 캐시되지 않은 입력 토큰 비용
    uncached_input_tokens = input_tokens - cached_input_tokens
    input_cost = (uncached_input_tokens / 1_000_000) * pricing["input_price"]
    # 캐시된 입력 토큰 비용
    cached_cost = (cached_input_tokens / 1_000_000) * pricing["cached_input_price"]
    # 출력 토큰 비용
    output_cost = (output_tokens / 1_000_000) * pricing["output_price"]
    return input_cost + cached_cost + output_cost


def get_openai_client():
    """OpenAI 클라이언트 싱글톤"""
    global _openai_client
    if _openai_client is None:
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. 환경변수를 확인해주세요.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client


def get_anthropic_client():
    """Anthropic 클라이언트 싱글톤"""
    global _anthropic_client
    if _anthropic_client is None:
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY가 설정되지 않았습니다. 환경변수를 확인해주세요.")
        _anthropic_client = Anthropic(api_key=api_key)
    return _anthropic_client


def get_provider_from_model(model: str) -> str:
    """모델명으로 provider 추론"""
    if model.startswith("claude"):
        return "claude"
    return "openai"


def apply_review_type_guard(prompt: str) -> str:
    """리뷰 유형 강제 규칙을 프롬프트에 선삽입."""
    if not prompt or not isinstance(prompt, str):
        return prompt

    guard = (
        "중요 규칙:\n"
        "1) '리뷰 유형'이 명시되어 있으면 반드시 그 유형으로 작성.\n"
        "2) 다른 유형의 글(후기/질문/고민/상담)과 섞지 말 것.\n"
        "3) '리뷰 유형'이 없으면 일반 후기로 작성.\n"
        "4) 아래에 출력 형식(JSON 등)이 지정되어 있으면 그 형식을 최우선으로 준수.\n"
        "5) 요청된 유형과 어긋나면 전체가 실패로 간주됨."
    )

    if "요청된 유형과 어긋나면 전체가 실패로 간주됨" in prompt:
        return prompt

    return f"{guard}\n\n{prompt}"


def _normalize_keywords(keywords: Optional[List[str]]) -> List[str]:
    if not keywords:
        return []
    seen = set()
    result = []
    for k in keywords:
        if not k:
            continue
        clean = str(k).strip()
        if not clean or clean in {"없음", "없어요"}:
            continue
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result




def _is_age_gender_token(token: str) -> bool:
    if re.fullmatch(r"\d{1,2}대(초반|중반|후반)?", token):
        return True
    if token in {"남성", "여성", "남자", "여자", "남", "여"}:
        return True
    return False


def _split_keywords(raw: str) -> List[str]:
    parts = re.split(r"[,\u00b7/|]|·", raw)
    return [p.strip() for p in parts if p and p.strip()]


def _extract_keywords_from_prompt(prompt: str) -> tuple[List[str], List[str]]:
    if not prompt:
        return [], []
    keywords: List[str] = []
    tone_keywords: List[str] = []
    for line in prompt.splitlines():
        if "페르소나" in line:
            raw = line.split(":", 1)[-1].strip()
            if raw:
                parts = _split_keywords(raw)
                for p in parts:
                    if _is_age_gender_token(p):
                        continue
                    if "말투" in p or "톤" in p or any(k in p for k in TONE_KEYWORDS):
                        tone_keywords.append(p)
                    else:
                        keywords.append(p)
            continue
        m = re.search(r"(강조\s*포인트|강조\s*키워드|필수\s*키워드|사용\s*키워드|키워드)\s*:\s*(.+)", line)
        if not m:
            continue
        raw = m.group(2).strip()
        if not raw or raw in {"없음", "없어요"}:
            continue
        for p in _split_keywords(raw):
            if p:
                keywords.append(p)
    return _normalize_keywords(keywords), _normalize_keywords(tone_keywords)


def _extract_length_constraints(prompt: str) -> tuple[Optional[int], Optional[int]]:
    if not prompt:
        return None, None

    min_len = None
    max_len = None

    range_match = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*자", prompt)
    if range_match:
        a = int(range_match.group(1))
        b = int(range_match.group(2))
        min_len = min(a, b)
        max_len = max(a, b)
        return min_len, max_len

    matches = list(re.finditer(r"(\d+)\s*자\s*(이상|부터|이내|이하|내외|정도)?", prompt))
    if not matches:
        return None, None

    m = matches[-1]
    n = int(m.group(1))
    suffix = m.group(2) or ""
    if suffix in {"이상", "부터"}:
        min_len = n
    elif suffix in {"이내", "이하"}:
        max_len = n
    elif suffix in {"내외", "정도"}:
        min_len = max(30, int(n * 0.7))
        max_len = int(n * 1.3)
    else:
        min_len = max(30, int(n * 0.9))
        max_len = int(n * 1.1)

    return min_len, max_len


def _is_json_expected(prompt: str) -> bool:
    if not prompt:
        return False
    lowered = prompt.lower()
    if "json" in lowered:
        return True
    if "출력 형식" in prompt and "{" in prompt and "}" in prompt:
        return True
    return False


KEYWORD_SYNONYMS = {
    "재방문 의사": [
        "재방문", "재방문할", "다시 받을", "또 받을", "다음에도", "다시 갈", "다시 방문",
        "또 여기서", "재시술", "재시술할", "다시 이용", "또 방문", "다음에도 여기",
        "재방문 의사", "재방문 생각", "다시 시술", "또 받을 생각", "다시 받아볼"
    ],
    "자연스러움": [
        "자연스럽", "자연스러운", "자연스럽게", "티 안", "티가 안", "티 안남", "티가 안남",
        "부자연스럽지", "부자연스럽지 않", "과하지 않", "과하지 않게", "무난하게",
        "부담스럽지", "부담스럽지 않", "티나는 느낌 없"
    ],
    "지인 추천": [
        "지인", "지인 추천", "지인한테", "친구 추천", "친구가 추천", "친구한테 추천",
        "가족 추천", "추천해준", "소개받", "소개로", "추천받", "추천받아서", "지인 소개"
    ],
    "통증 적음": [
        "통증 적", "통증이 적", "통증 거의", "통증이 덜", "덜 아픔", "아프지",
        "아픈 편 아니", "통증이 약", "통증이 크지", "통증 심하지", "통증이 별로",
        "통증이 거의 없"
    ],
    "회복 빠름": [
        "회복 빠", "회복이 빠", "빨리 회복", "금방 회복", "회복이 빨랐", "회복 속도",
        "붓기 빨리", "붓기 빨", "붓기 금방", "부기 빨리", "멍 금방", "멍이 빨리",
        "회복이 생각보다 빠"
    ],
    "친절한 상담": [
        "친절", "상담 친절", "상담이 친절", "친절했", "친절하게", "상담이 꼼꼼",
        "꼼꼼한 상담", "설명 잘", "설명을 자세히", "차분히 설명", "친절한 안내",
        "응대가 친절"
    ],
    "가격 만족": [
        "가격 만족", "가격이 괜찮", "가격 부담 적", "가성비", "합리적 가격",
        "가격 대비", "가격이 합리적", "가격 부담이 크지", "가격이 부담스럽지",
        "비용이 괜찮", "비용 부담 적"
    ],
    "대기시간 짧음": [
        "대기시간 짧", "대기 짧", "기다림 짧", "대기 거의", "대기 거의 없",
        "대기 오래 안", "기다리는 시간 적", "대기시간 길지", "대기시간 부담 없",
        "바로 봐주", "금방 들어"
    ],
}


def _keyword_satisfied(text: str, keyword: str) -> bool:
    if keyword in text:
        return True
    variants = KEYWORD_SYNONYMS.get(keyword, [])
    return any(v in text for v in variants)


def _contains_all_keywords(text: str, keywords: List[str]) -> List[str]:
    if not keywords:
        return []
    missing = []
    for k in keywords:
        if not _keyword_satisfied(text, k):
            missing.append(k)
    return missing


def _looks_like_prompt_echo(text: str, prompt: str) -> bool:
    if not text or not prompt:
        return False
    markers = [
        "질문 예시",
        "참고용",
        "자연스러운 질문글 형태",
        "작성해주세요",
        "작성해 주세요",
        "작성해줘",
        "위 조건을 반영해",
        "중요 규칙",
        "출력 형식",
        "JSON 출력",
    ]
    if any(m in text for m in markers):
        return True
    # If response contains a large chunk of prompt, consider it echo
    snippet = prompt.strip()[:120]
    if snippet and snippet in text:
        return True
    return False


OVER_EXPLAIN_PHRASES = [
    "하나하나 설명해",
    "자세히 설명해",
    "다 짚어",
    "안내해줬",
    "이해하기 쉬웠",
]

HARD_CONFIDENT_ENDINGS = [
    "꼭 받을",
    "무조건 받을",
    "완전 만족",
    "기대감 폭발",
    "여기서 꼭",
    "예약했",
]

HEDGE_ENDING_MARKERS = [
    "일단",
    "아직",
    "생각",
    "같",
    "편",
    "보려",
    "예정",
]

GENERIC_OPENERS = [
    "상담 다녀왔",
    "상담 받고 왔",
    "후기 찾아봤",
    "말씀드렸는데 오늘",
]

STOCK_PHRASES = [
    "신뢰가 갔",
    "믿음이 갔",
    "현실적으로",
    "꼼꼼하게",
    "부담 없이",
    "부담없",
    "하나하나 짚어",
    "자세하게 설명",
    "도움이 많이 됐",
]

STARTER_LABELS = [
    "상황형 -",
    "고민형 -",
    "우연형 -",
    "결과형 -",
]


def _has_over_explaining_habit(text: str) -> bool:
    if not text:
        return False
    hits = sum(text.count(p) for p in OVER_EXPLAIN_PHRASES)
    return hits >= 2


def _has_hard_confident_ending(text: str) -> bool:
    if not text:
        return False
    tail = text[-140:]
    if not any(p in tail for p in HARD_CONFIDENT_ENDINGS):
        return False
    # 여지형 마무리 단서가 있으면 통과
    if any(m in tail for m in HEDGE_ENDING_MARKERS):
        return False
    return True


def _starts_with_generic_opener(text: str) -> bool:
    if not text:
        return False
    first = re.split(r"[.!?\n]", text.strip(), maxsplit=1)[0].strip()
    if not first:
        return False
    return any(first.startswith(p) for p in GENERIC_OPENERS)


def _has_stock_phrase_habit(text: str) -> bool:
    if not text:
        return False
    total_hits = sum(text.count(p) for p in STOCK_PHRASES)
    # 특정 상투어는 1회까지만 허용
    trust_hits = (
        text.count("신뢰가 갔")
        + text.count("신뢰감")
        + text.count("믿음이 갔")
        + text.count("믿음 갔")
    )
    if trust_hits >= 2:
        return True
    return total_hits >= 3


def _has_starter_label_leak(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    return any(stripped.startswith(label) for label in STARTER_LABELS)


def _has_connector_repetition_habit(text: str) -> bool:
    if not text:
        return False
    # 설명 연결형 문장 버릇 감지
    and_hits = len(re.findall(r"해주셨고|알려주셨고|보여주셨고|말해주셨고", text))
    explain_hits = len(re.findall(r"설명해주", text))
    return and_hits >= 3 or explain_hits >= 4


MBTI_TONE_MAP = {
    "ISTJ": "신중하고 논리적이며 담담한 톤. 핵심 위주로 깔끔하게.",
    "ISFJ": "배려가 느껴지는 따뜻한 톤. 조심스럽고 공감 위주.",
    "INFJ": "조용하고 진지한 톤. 고민과 의미를 곁들여 서술.",
    "INTJ": "분석적이고 간결한 톤. 핵심만 정리해 말하기.",
    "ISTP": "담백하고 현실적인 톤. 과장 없이 사실 중심.",
    "ISFP": "부드럽고 감성적인 톤. 느낌과 분위기 묘사.",
    "INFP": "감성적이고 공감적인 톤. 마음 표현을 자연스럽게.",
    "INTP": "분석적이고 차분한 톤. 이유/근거 중심.",
    "ESTP": "직설적이고 활기찬 톤. 생동감 있게.",
    "ESFP": "밝고 친근한 톤. 재미/리액션 자연스럽게.",
    "ENFP": "에너지 있고 따뜻한 톤. 공감과 기대감 강조.",
    "ENTP": "가볍고 위트 있는 톤. 호기심 섞인 표현.",
    "ESTJ": "단정하고 실용적인 톤. 결론 중심으로.",
    "ESFJ": "친절하고 정중한 톤. 배려 표현 포함.",
    "ENFJ": "공감적이고 이끄는 톤. 격려 표현 자연스럽게.",
    "ENTJ": "단호하고 명확한 톤. 구조적으로 정리.",
}

# 말투 강제 규칙 (MBTI에 따라 적용)
MBTI_TONE_RULES = {
    "ISTJ": "반드시 담담하고 단정한 문장으로 작성. 군더더기 없이 핵심 위주.",
    "ISFJ": "반드시 따뜻하고 배려하는 말투로 작성. 공감 표현을 적절히 포함.",
    "INFJ": "반드시 진지하고 차분한 말투로 작성. 고민/의미 표현 포함.",
    "INTJ": "반드시 분석적이고 간결한 말투로 작성. 이유/근거 중심.",
    "ISTP": "반드시 담백하고 현실적인 말투로 작성. 과장 표현 금지.",
    "ISFP": "반드시 부드럽고 감성적인 말투로 작성. 느낌/분위기 묘사.",
    "INFP": "반드시 감성적이고 공감적인 말투로 작성. 마음 표현 포함.",
    "INTP": "반드시 차분하고 논리적인 말투로 작성. 정리된 설명.",
    "ESTP": "반드시 직설적이고 활기찬 말투로 작성. 리액션은 과하지 않게.",
    "ESFP": "반드시 밝고 친근한 말투로 작성. 가벼운 리액션 허용.",
    "ENFP": "반드시 에너지 있고 따뜻한 말투로 작성. 기대감 표현 포함.",
    "ENTP": "반드시 위트 있고 가볍게 작성. 호기심 표현 포함.",
    "ESTJ": "반드시 단정하고 실용적인 말투로 작성. 결론 중심.",
    "ESFJ": "반드시 친절하고 정중한 말투로 작성. 배려 표현 포함.",
    "ENFJ": "반드시 공감적이고 이끄는 말투로 작성. 격려 표현 포함.",
    "ENTJ": "반드시 단호하고 명확한 말투로 작성. 구조적으로 정리.",
}

# 말투 키워드에 따른 리액션/이모지 규칙
TONE_REACTION_RULES = {
    "귀여": "이모지/리액션을 문장 3~5개마다 1번 정도 포함. ㅎㅎ/ㅠㅠ 사용 허용.",
    "발랄": "경쾌한 리액션을 3~4문장마다 1번 포함.",
    "감성": "감정 표현(ㅠㅠ/ㅎㅎ 등)을 4~6문장마다 1번 포함.",
    "따뜻": "따뜻한 표현 + 간단한 리액션을 4~6문장마다 1번 포함.",
}


def _extract_mbti_from_prompt(prompt: str) -> Optional[str]:
    if not prompt:
        return None
    m = re.search(r"\b(ISTJ|ISFJ|INFJ|INTJ|ISTP|ISFP|INFP|INTP|ESTP|ESFP|ENFP|ENTP|ESTJ|ESFJ|ENFJ|ENTJ)\b", prompt, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _build_prompt_summary(prompt: str) -> str:
    """FT 모델용 프롬프트 상단 요약 (3~5줄)"""
    if not prompt:
        return ""
    fields = {
        "병원": None,
        "시술": None,
        "리뷰 유형": None,
        "후기 시점": None,
        "페르소나": None,
        "강조 포인트": None,
        "길이": None,
    }
    for line in prompt.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip()
        if key in fields and val:
            fields[key] = val

    summary_lines = []
    if fields["리뷰 유형"] or fields["후기 시점"]:
        summary_lines.append(
            f"리뷰: {fields['리뷰 유형'] or '-'} / {fields['후기 시점'] or '-'}"
        )
    if fields["병원"] or fields["시술"]:
        summary_lines.append(
            f"대상: {fields['병원'] or '-'} / {fields['시술'] or '-'}"
        )
    if fields["페르소나"]:
        summary_lines.append(f"페르소나: {fields['페르소나']}")
    if fields["강조 포인트"]:
        summary_lines.append(f"키워드: {fields['강조 포인트']}")
    if fields["길이"]:
        summary_lines.append(f"길이: {fields['길이']}")

    return "\n".join(summary_lines[:5])


def _looks_polite(text: str) -> bool:
    return len(re.findall(r"(습니다|니다|해요|어요|예요)", text)) >= 2


def _looks_casual(text: str) -> bool:
    # casual: avoid polite endings
    return len(re.findall(r"(습니다|니다|해요|어요|예요)", text)) <= 1


def _force_append_keywords(text: str, missing: List[str]) -> str:
    # 키워드 강제 삽입 문장은 사용자 경험을 해치므로 비활성화
    return text


def generate_review_with_prompt_enforced(
    prompt: str,
    model: str = "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    max_tokens: int = 1500,
    temperature: float = 0.65,
    top_p: float = 0.9,
    frequency_penalty: float = 0.4,
    presence_penalty: float = 0.2,
    return_usage: bool = False,
    keywords: Optional[List[str]] = None,
    min_len: Optional[int] = None,
    max_len: Optional[int] = None,
    max_retries: int = 6,
) -> str | dict:
    is_json = _is_json_expected(prompt)
    mbti = _extract_mbti_from_prompt(prompt)

    extracted_keywords: List[str] = []
    tone_keywords: List[str] = []
    if not is_json:
        extracted_keywords, tone_keywords = _extract_keywords_from_prompt(prompt)

    if keywords is None:
        keywords = extracted_keywords
    else:
        keywords = (keywords or []) + extracted_keywords
    if min_len is None and max_len is None:
        if not is_json:
            min_len, max_len = _extract_length_constraints(prompt)

    # FT 구공이 모델 기본 길이 보정 (길이 힌트가 없을 때만)
    if not is_json and (min_len is None and max_len is None):
        if model == "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk":
            min_len, max_len = 500, 1000

    keywords = _normalize_keywords(keywords)
    base_prompt = prompt
    if mbti and model == "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk":
        tone_guide = MBTI_TONE_MAP.get(mbti)
        tone_rule = MBTI_TONE_RULES.get(mbti)
        if tone_guide or tone_rule:
            header_lines = []
            if tone_guide:
                header_lines.append(f"MBTI 성향: {mbti} - {tone_guide}")
            if tone_rule:
                header_lines.append(f"[말투 규칙] {tone_rule}")
            base_prompt = "\n".join(header_lines) + "\n\n" + base_prompt

    # FT 모델 상단 요약 (프롬프트 집중도 강화)
    if model.startswith("ft:"):
        summary = _build_prompt_summary(base_prompt)
        if summary:
            base_prompt = f"[요약]\n{summary}\n\n{base_prompt}"

    # 구공이 전용 룰셋 (금지 표현 + 유형별 규칙)
    if model == "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk":
        type_line = ""
        for line in prompt.splitlines():
            if line.strip().startswith("리뷰 유형"):
                type_line = line.split(":", 1)[-1].strip()
                break

        # 구공이 전용 룰 요약(3~5줄)
        if "고민" in type_line or "질문" in type_line:
            type_rule = "질문글 형태로 작성하고, 마지막에 질문 1~2개 포함."
            ban_rule = "시술 완료/결과 단정 금지."
        elif "상담" in type_line:
            type_rule = "상담 후기 형태(상담 과정/느낌 위주)."
            ban_rule = "시술 완료/결과 단정 금지."
        else:
            type_rule = "후기형 서술(자연스러운 경험담)."
            ban_rule = "과장/광고성 표현 금지."

        forbidden_short = "인생병원/완전강추/무조건추천/할인/이벤트/협찬/홍보 금지."
        rule_block = [
            "[구공이 요약 규칙]",
            f"- {type_rule}",
            f"- {ban_rule}",
            f"- {forbidden_short}",
            "- 설명을 100% 완벽하게 다 하지 않아도 됨.",
            "- 결론/확신형 마무리를 강요하지 말고 여지형 마무리 허용(일단/아직/생각).",
            "- 설명 문장 일부(10~15%)를 감정/체감 문장으로 바꿔 작성.",
            "- 첫 문장은 아래 4가지 중 1개로 시작: 고민형/상황형/우연형/결과형.",
            "- 반복 금지: '자세히 설명해줬어요/안내해줬어요/다 짚어줬어요' 류를 연속 사용하지 말 것.",
            "- 상투 표현 반복 금지: '신뢰가 갔어요/믿음이 갔어요/현실적으로/꼼꼼하게'를 한 글에서 과다 반복하지 말 것.",
            "- '상황형 -/고민형 -/우연형 -/결과형 -' 라벨 텍스트를 본문에 그대로 출력하지 말 것.",
            "- 접속 반복 금지: '~해주셨고' 형태를 연속적으로 남발하지 말 것.",
        ]
        base_prompt = "\n".join(rule_block) + "\n\n" + base_prompt

    # 말투 키워드에 따른 리액션/이모지 규칙 추가
    if tone_keywords:
        reaction_lines = []
        for key, rule in TONE_REACTION_RULES.items():
            if any(key in t for t in tone_keywords):
                reaction_lines.append(rule)
        if reaction_lines:
            base_prompt = "[리액션 규칙] " + " ".join(reaction_lines) + "\n\n" + base_prompt

    for attempt in range(max_retries + 1):
        result = generate_review_with_prompt(
            prompt=base_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            return_usage=return_usage,
        )

        text = result["text"] if isinstance(result, dict) else result
        missing = _contains_all_keywords(text, keywords)
        echoed = _looks_like_prompt_echo(text, prompt)
        tone_ok = True
        if tone_keywords:
            if any(t in tone_keywords for t in ["존댓말", "공손한", "정중한"]):
                tone_ok = _looks_polite(text)
            elif any(t in tone_keywords for t in ["반말"]):
                tone_ok = _looks_casual(text)
        too_short = min_len is not None and len(text) < min_len
        too_long = max_len is not None and len(text) > max_len
        style_guard_failed = False
        if model == "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk" and not is_json:
            style_guard_failed = (
                _has_over_explaining_habit(text)
                or _has_hard_confident_ending(text)
                or _starts_with_generic_opener(text)
                or _has_stock_phrase_habit(text)
                or _has_starter_label_leak(text)
                or _has_connector_repetition_habit(text)
            )

        if not missing and not too_short and not too_long and tone_ok and not echoed and not style_guard_failed:
            return result

        if attempt < max_retries:
            rules = ["[중요] 조건 재강조:"]
            if keywords:
                rules.append(f"- 필수 키워드: {', '.join(keywords)} (모두 포함, 동의어로만 대체 금지)")
            if tone_keywords:
                rules.append(f"- 말투/톤: {', '.join(tone_keywords)} (반드시 반영)")
            if min_len is not None:
                rules.append(f"- 길이: 최소 {min_len}자 이상")
            if max_len is not None:
                rules.append(f"- 길이: 최대 {max_len}자 이하")
            rules.append("- 프롬프트나 지시문을 그대로 복사하지 말고 결과만 출력")
            rules.append("- 각 키워드는 본문에 자연스럽게 직접 언급")
            if model == "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk":
                rules.append("- 설명문 과다 반복 금지(자세히/안내/다 짚어 반복 금지)")
                rules.append("- 상투 문구 반복 금지(신뢰가 갔어요/믿음이 갔어요/현실적으로/꼼꼼하게)")
                rules.append("- 시작 라벨 텍스트 출력 금지(상황형-/고민형-/우연형-/결과형-)")
                rules.append("- '~해주셨고' 접속형 반복 최소화")
                rules.append("- 감정/체감 문장 비율을 15~20%로 높여 작성")
                rules.append("- 마지막 문장은 확신형 단정 대신 여지형 표현 허용")
                rules.append("- 첫 문장 패턴을 바꿔 시작(고민형/상황형/우연형/결과형)")
            rules.append("- 위 조건을 만족하지 않으면 실패입니다.")
            base_prompt = "\n".join(rules) + "\n\n" + prompt
            continue

        if missing and not is_json:
            new_text = _force_append_keywords(text, missing)
            if isinstance(result, dict):
                result = {**result, "text": new_text}
            else:
                result = new_text
        return result


def generate_title_suggestions(
    review_text: str,
    model: str,
    title_style: Optional[str] = None,
    max_titles: int = 3,
) -> List[str]:
    if not review_text or not review_text.strip():
        return []

    style_line = f"\n제목 스타일: {title_style}" if title_style else ""
    title_prompt = (
        "아래 리뷰 내용을 바탕으로 제목을 3개 추천해줘.\n"
        "- 한국어\n"
        "- 광고/과장 표현 금지\n"
        "- 중복 금지\n"
        "- 각각 15~30자 내외\n"
        "- 결과는 JSON 배열로만 출력\n"
        f"{style_line}\n\n"
        f"리뷰:\n{review_text}\n\n"
        '출력 예시: ["제목1", "제목2", "제목3"]'
    )
    system_prompt = "너는 리뷰 제목 추천 전문가다. 조건을 정확히 지켜라."

    raw = generate_review_with_prompt(
        prompt=title_prompt,
        model=model,
        max_tokens=200,
        temperature=0.7,
        top_p=0.9,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        return_usage=False,
        system_prompt_override=system_prompt,
    )

    text = raw if isinstance(raw, str) else raw.get("text", "")
    if "```" in text:
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        else:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()
    titles: List[str] = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            titles = [str(t).strip() for t in data if str(t).strip()]
    except Exception:
        pass

    if not titles:
        for line in text.splitlines():
            line = line.strip().lstrip("-").lstrip("*").strip()
            line = re.sub(r"^\d+[\).\s]+", "", line).strip()
            if line:
                titles.append(line)

    titles = [t for t in titles if t]
    # 중복 제거 + 길이 제한
    seen = set()
    deduped = []
    for t in titles:
        if t in seen:
            continue
        seen.add(t)
        deduped.append(t)

    if len(deduped) < max_titles:
        base = review_text.strip().replace("\n", " ")
        fallback = base[:30].rstrip()
        while len(deduped) < max_titles:
            deduped.append(f"{fallback} 후기 {len(deduped)+1}")

    return deduped[:max_titles]


def extract_text_from_image(image_data: bytes, mime_type: str = "image/png") -> str:
    """
    GPT-4o Vision을 사용하여 이미지에서 텍스트 추출

    Args:
        image_data: 이미지 바이너리 데이터
        mime_type: 이미지 MIME 타입 (image/png, image/jpeg 등)

    Returns:
        추출된 텍스트
    """
    client = get_openai_client()

    # Base64 인코딩
    base64_image = base64.b64encode(image_data).decode('utf-8')

    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=[
            {
                "role": "system",
                "content": """당신은 이미지에서 텍스트를 추출하는 전문가입니다.
이미지에 있는 모든 텍스트를 정확하게 추출해주세요.

규칙:
- 이미지에 보이는 텍스트만 추출 (해석이나 요약 금지)
- 원본 텍스트의 줄바꿈과 구조를 최대한 유지
- 이모지가 있으면 그대로 포함
- 텍스트가 없으면 "[텍스트 없음]" 반환
- 읽기 어려운 부분은 [?]로 표시"""
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "이 이미지에서 모든 텍스트를 추출해주세요."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ],
        max_completion_tokens=2000,
    )

    return response.choices[0].message.content


def extract_texts_from_images(images: List[tuple]) -> List[str]:
    """
    여러 이미지에서 텍스트 추출

    Args:
        images: [(image_data, mime_type), ...] 형태의 리스트

    Returns:
        추출된 텍스트 리스트
    """
    texts = []
    for image_data, mime_type in images:
        try:
            text = extract_text_from_image(image_data, mime_type)
            if text and text.strip() and text != "[텍스트 없음]":
                texts.append(text.strip())
        except Exception as e:
            print(f"이미지 텍스트 추출 실패: {e}")
            continue
    return texts


def generate_review_with_prompt(
    prompt: str,
    model: str = "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk",
    max_tokens: int = 1500,
    temperature: float = 0.65,
    top_p: float = 0.9,
    frequency_penalty: float = 0.4,
    presence_penalty: float = 0.2,
    return_usage: bool = False,
    system_prompt_override: Optional[str] = None
) -> str | dict:
    """
    프롬프트를 사용하여 리뷰 생성 (OpenAI 또는 Claude)

    Args:
        prompt: 생성 프롬프트
        model: 사용할 모델 (gpt-5-mini, claude-sonnet-4-5-20241022 등)
        max_tokens: 최대 토큰 수
        temperature: 창의성 (0.0 ~ 1.0)
        return_usage: True면 토큰 사용량/비용 정보 포함 딕셔너리 반환

    Returns:
        return_usage=False: 생성된 리뷰 텍스트
        return_usage=True: {"text": str, "input_tokens": int, "output_tokens": int, "cached_input_tokens": int, "total_tokens": int, "cost_usd": float}
    """
    provider = get_provider_from_model(model)
    system_prompt = (
        system_prompt_override
        or "당신은 실제로 시술을 받았거나 받을 환자로서 자연스러운 시술후기, 경험, 상담후기, 질문글들을 작성합니다. 광고가 아닌 진짜 의견과 사실, 경험담처럼 작성해주세요."
    )

    input_tokens = 0
    output_tokens = 0
    cached_input_tokens = 0
    text = ""

    if provider == "claude":
        # Claude API 사용
        client = get_anthropic_client()
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=temperature,
        )
        text = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        # Claude 캐시된 토큰: cache_read_input_tokens
        cached_input_tokens = getattr(response.usage, 'cache_read_input_tokens', 0) or 0
    else:
        # OpenAI API 사용
        client = get_openai_client()

        # gpt-5.2-pro는 completions API 사용 (chat 모델 아님)
        if model == "gpt-5.2-pro":
            full_prompt = f"{system_prompt}\n\n{prompt}"
            response = client.completions.create(
                model=model,
                prompt=full_prompt,
                max_tokens=max_tokens,
            )
            text = response.choices[0].text
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            # completions API는 캐시 정보 없음
            cached_input_tokens = 0
        else:
            # 일반 chat 모델
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
            )
            text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            # OpenAI 캐시된 토큰: prompt_tokens_details.cached_tokens
            if response.usage and hasattr(response.usage, 'prompt_tokens_details') and response.usage.prompt_tokens_details:
                cached_input_tokens = getattr(response.usage.prompt_tokens_details, 'cached_tokens', 0) or 0
            else:
                cached_input_tokens = 0

    if return_usage:
        cost_usd = calculate_cost(model, input_tokens, output_tokens, cached_input_tokens)
        return {
            "text": text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_input_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost_usd,
        }
    return text


def generate_review(
    clinic_name: str,
    treatment: str,
    tone: str = "친절한 후기 스타일"
) -> str:
    """
    간단한 리뷰 생성 (기존 호환용)
    
    Args:
        clinic_name: 병원명
        treatment: 시술명
        tone: 톤
    
    Returns:
        생성된 리뷰 텍스트
    """
    prompt = f"""
    병의원 바이럴 리뷰 작성.

    병원명: {clinic_name}
    시술: {treatment}
    톤: {tone}

    조건:
    - 실제 후기처럼 자연스럽게 작성
    - 과장 광고 금지
    - 부정적인 내용 없이 긍정적으로 설명
    - 최소 5문장 이상
    """
    prompt = apply_review_type_guard(prompt)

    return generate_review_with_prompt_enforced(prompt, max_tokens=500)


def generate_review_advanced(
    clinic_data: Dict,
    doctor_code: str,
    procedure: str,
    persona: Optional[Dict] = None,
    cafe: Optional[Dict] = None,
    consultant_name: Optional[str] = None,
    custom_instructions: Optional[str] = None,
    model: str = "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk"
) -> Dict:
    """
    고급 리뷰 생성 (전체 컨텍스트 사용)
    
    Args:
        clinic_data: 병원 데이터
        doctor_code: 담당 원장 코드
        procedure: 시술명
        persona: 페르소나 설정
        cafe: 카페 설정
        consultant_name: 상담실장명
        custom_instructions: 추가 지시사항
        model: 사용할 모델
    
    Returns:
        {
            'review': 생성된 리뷰,
            'prompt': 사용된 프롬프트,
            'model': 사용된 모델
        }
    """
    from .prompt_generator import build_review_prompt
    
    # 프롬프트 생성
    prompt = build_review_prompt(
        clinic_data=clinic_data,
        doctor_code=doctor_code,
        procedure=procedure,
        persona=persona,
        cafe=cafe,
        consultant_name=consultant_name,
        custom_instructions=custom_instructions,
    )
    prompt = apply_review_type_guard(prompt)
    
    # 리뷰 생성
    review = generate_review_with_prompt_enforced(prompt, model=model)
    
    return {
        'review': review,
        'prompt': prompt,
        'model': model,
    }


def regenerate_with_feedback(
    original_prompt: str,
    original_review: str,
    feedback: str,
    model: str = "ft:gpt-4.1-2025-04-14:personal::D3gDuLBk"
) -> str:
    """
    피드백을 반영하여 리뷰 재생성
    
    Args:
        original_prompt: 원본 프롬프트
        original_review: 원본 리뷰
        feedback: 수정 요청 피드백
        model: 사용할 모델
    
    Returns:
        수정된 리뷰 텍스트
    """
    regenerate_prompt = f"""
이전에 아래 프롬프트로 리뷰를 생성했습니다:

=== 원본 프롬프트 ===
{original_prompt}

=== 생성된 리뷰 ===
{original_review}

=== 수정 요청 ===
{feedback}

위 피드백을 반영하여 리뷰를 다시 작성해주세요.
"""
    regenerate_prompt = apply_review_type_guard(regenerate_prompt)

    return generate_review_with_prompt_enforced(regenerate_prompt, model=model)
