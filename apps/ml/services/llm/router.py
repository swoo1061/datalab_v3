from apps.data.models import LLMUsageLog
from .openai_client import OpenAIClient
from .claude_client import ClaudeClient


CLIENTS = {
    "gpt-4.1-mini": OpenAIClient("gpt-4.1-mini"),
    "gpt-4.1": OpenAIClient("gpt-4.1"),
    "claude-4.5": ClaudeClient(),
}


def generate_review(*, user, prompt: str, model: str, source="web"):
    if model not in CLIENTS:
        raise ValueError(f"지원하지 않는 모델: {model}")

    client = CLIENTS[model]
    result = client.generate(prompt)

    # ⭐ 여기서 웹/앱 통계 통합
    LLMUsageLog.objects.create(
        user=user,
        model=model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        total_tokens=result.total_tokens,
        cost_usd=result.cost_usd,
        cost_krw=result.cost_krw,
    )

    return result