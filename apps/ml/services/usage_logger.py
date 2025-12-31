from apps.data.models import LLMUsageLog

USD_TO_KRW = 1450


def log_llm_usage(*, user, model, usage: dict):
    if not user or not user.is_authenticated:
        return

    cost_usd = usage.get("cost_usd", 0) or 0
    cost_krw = cost_usd * USD_TO_KRW

    LLMUsageLog.objects.create(
        user=user,
        model=model,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        cost_usd=cost_usd,
        cost_krw=cost_krw,
    )