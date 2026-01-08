from dataclasses import dataclass


@dataclass
class LLMResult:
    text: str

    # 토큰 / 비용
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    cost_usd: float = 0.0
    cost_krw: float = 0.0