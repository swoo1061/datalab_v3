import os
from openai import OpenAI
from .base import LLMResult


USD_TO_KRW = float(os.getenv("USD_TO_KRW", "1300"))

# 모델별 1K 토큰 비용 (예시)
MODEL_PRICING = {
    "gpt-4.1-mini": {
        "input": 0.00015,
        "output": 0.0006,
    },
    "gpt-4.1": {
        "input": 0.0003,
        "output": 0.0012,
    },
}


class OpenAIClient:
    def __init__(self, model_name: str | None = None):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model_name = model_name or os.getenv(
            "OPENAI_DEFAULT_MODEL", "gpt-4.1-mini"
        )

        if self.model_name not in MODEL_PRICING:
            raise ValueError(f"모델 가격 정보 없음: {self.model_name}")

    def generate(self, prompt: str) -> LLMResult:
        """
        OpenAI 실제 호출
        """

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "너는 병원 후기 작성을 도와주는 마케팅 전문 AI다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
        )

        text = response.choices[0].message.content.strip()

        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens

        pricing = MODEL_PRICING[self.model_name]

        cost_usd = (
            input_tokens / 1000 * pricing["input"]
            + output_tokens / 1000 * pricing["output"]
        )
        cost_krw = cost_usd * USD_TO_KRW

        return LLMResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=round(cost_usd, 6),
            cost_krw=round(cost_krw, 2),
        )