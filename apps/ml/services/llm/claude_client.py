from .base import LLMResult


class ClaudeClient:
    model_name = "claude-4.5"

    def generate(self, prompt: str) -> LLMResult:
        """
        Claude 호출
        """
        text = "Claude로 생성된 리뷰 텍스트"

        input_tokens = 1000
        output_tokens = 900
        total_tokens = input_tokens + output_tokens

        cost_usd = total_tokens * 0.000012
        cost_krw = cost_usd * 1300

        return LLMResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            cost_krw=cost_krw,
        )