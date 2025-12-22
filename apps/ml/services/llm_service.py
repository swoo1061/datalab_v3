"""
LLM 서비스 - 리뷰 생성

OpenAI 및 Claude API를 사용하여 자연스러운 리뷰를 생성합니다.
"""
import base64
from openai import OpenAI
from anthropic import Anthropic
from django.conf import settings
from typing import Optional, Dict, List


# 클라이언트 초기화 (싱글톤)
_openai_client = None
_anthropic_client = None


# 사용 가능한 모델 정의 (가격: $/1M tokens)
AVAILABLE_MODELS = {
    "openai": {
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
    model: str = "gpt-5-mini",
    max_tokens: int = 1500,
    temperature: float = 0.75,
    return_usage: bool = False
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
    system_prompt = "당신은 실제로 시술을 받았거나 받을 환자로서 자연스러운 시술후기, 경험, 상담후기, 질문글들을 작성합니다. 광고가 아닌 진짜 의견과 사실, 경험담처럼 작성해주세요."

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
    
    return generate_review_with_prompt(prompt, max_tokens=500)


def generate_review_advanced(
    clinic_data: Dict,
    doctor_code: str,
    procedure: str,
    persona: Optional[Dict] = None,
    cafe: Optional[Dict] = None,
    consultant_name: Optional[str] = None,
    custom_instructions: Optional[str] = None,
    model: str = "gpt-5-mini"
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
    
    # 리뷰 생성
    review = generate_review_with_prompt(prompt, model=model)
    
    return {
        'review': review,
        'prompt': prompt,
        'model': model,
    }


def regenerate_with_feedback(
    original_prompt: str,
    original_review: str,
    feedback: str,
    model: str = "gpt-5-mini"
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
    
    return generate_review_with_prompt(regenerate_prompt, model=model)
