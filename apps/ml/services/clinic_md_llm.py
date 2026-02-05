import json
import re
from typing import Dict, Any

# ✅ 여기 경로가 핵심: 너 프로젝트에서 generate_review_with_prompt가 있는 실제 위치로 맞춰야 함
# 너가 올린 코드 기준으로는 이쪽이 가장 그럴듯함:
from apps.ml.services.llm_service import generate_review_with_prompt


_JSON_SCHEMA_EXAMPLE = {
    "basic_info": {
        "location": "",
        "hours": "",
        "parking": "",
        "consult_fee": "",
    },
    "doctors": [
        {
            "name": "",
            "age": "",
            "style": "",
            "specialties": [],
        }
    ],
    "consultants": [
        {
            "name": "",
            "age": "",
            "style": "",
        }
    ],
    "price_list": [],
    "process": "",
    "aftercare": {},
    "post_care": {},
    "features": {},
    "allowed_hospitals": {},
    "blocked_hospitals": [],
    "raw_data": {}
}


def _extract_json(text: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON만 안전하게 뽑아오기
    - ```json ... ``` 블록 대응
    - 앞/뒤 설명 섞여도 { ... } 덩어리만 추출
    """
    # 1) ```json ... ``` 우선
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return json.loads(m.group(1))

    # 2) 첫 { 부터 마지막 } 까지
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])

    raise ValueError("LLM 응답에서 JSON을 추출하지 못했습니다.")


def _normalize_result(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    최소 필드 보장 + 타입 보정
    """
    # 기본 틀
    base = json.loads(json.dumps(_JSON_SCHEMA_EXAMPLE, ensure_ascii=False))

    # 얕은 merge
    for k, v in data.items():
        base[k] = v

    # basic_info 보정
    base.setdefault("basic_info", {})
    for k in ["location", "hours", "parking", "consult_fee"]:
        base["basic_info"].setdefault(k, "")

    # 리스트/딕트 타입 보정
    for k in ["doctors", "consultants", "price_list", "blocked_hospitals"]:
        if not isinstance(base.get(k), list):
            base[k] = []
    for k in ["allowed_hospitals", "aftercare", "post_care", "features", "raw_data"]:
        if not isinstance(base.get(k), dict):
            base[k] = {}

    # doctors 내부 보정
    fixed_doctors = []
    for d in base["doctors"]:
        if not isinstance(d, dict):
            continue
        fixed_doctors.append({
            "name": str(d.get("name", "")).strip(),
            "age": str(d.get("age", "")).strip(),
            "style": str(d.get("style", "")).strip(),
            "specialties": d.get("specialties", []) if isinstance(d.get("specialties", []), list) else [],
        })
    base["doctors"] = fixed_doctors

    # consultants 내부 보정
    fixed_cons = []
    for c in base["consultants"]:
        if not isinstance(c, dict):
            continue
        fixed_cons.append({
            "name": str(c.get("name", "")).strip(),
            "age": str(c.get("age", "")).strip(),
            "style": str(c.get("style", "")).strip(),
        })
    base["consultants"] = fixed_cons

    return base


def _clean_md_block(text: str) -> str:
    t = str(text or "")
    t = re.sub(r"</?aside>", "", t, flags=re.IGNORECASE)
    t = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", t)
    t = re.sub(r"\*\*", "", t)
    t = re.sub(r"\r\n?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _extract_special_sections(md_content: str) -> Dict[str, str]:
    """
    사치바이오형 제품 가이드 섹션을 원문에서 직접 추출.
    LLM 출력 누락 시에도 UI에 필요한 raw_data를 보장한다.
    """
    content = str(md_content or "")
    sections: Dict[str, str] = {}

    def row_value(pattern: str) -> str:
        m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if not m:
            return ""
        return _clean_md_block(m.group(1))

    product_intro = row_value(r"\|\s*\*\*제품소개\*\*\s*\|\s*(.*?)(?=\n\|\s*\*\*|$)")
    timeline = row_value(r"\|\s*\*\*제품 기전 및[\s\S]*?\*\*\s*\|\s*(.*?)(?=\n\|\s*\*\*|$)")
    keywords = row_value(r"\|\s*\*\*제품 키워드\*\*\s*\|\s*(.*?)(?=\n\|\s*\*\*|\n-\s*\*\*커뮤니티|$)")

    comm_match = re.search(
        r"-\s*\*\*커뮤니티 참고사항\*\*\s*(.*?)(?=\n-\s*\*\*수가표\*\*|$)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    community = _clean_md_block(comm_match.group(1)) if comm_match else ""

    price_match = re.search(r"-\s*\*\*수가표\*\*\s*(.*)$", content, re.DOTALL | re.IGNORECASE)
    price_guide = _clean_md_block(price_match.group(1)) if price_match else ""

    if product_intro:
        sections["제품소개"] = product_intro
    if timeline:
        sections["제품 기전 및 타임라인별 소구포인트"] = timeline
    if keywords:
        sections["제품 키워드"] = keywords
    if community:
        sections["커뮤니티 참고사항"] = community
    if price_guide:
        sections["수가표"] = price_guide

    return sections


def parse_clinic_md_with_llm(md_content: str, model: str = "gpt-5-mini") -> Dict[str, Any]:
    """
    Notion MD(또는 너가 올린 탭/줄 형태 텍스트) → JSON 구조화
    실패하면 에러를 던짐 (views에서 잡아줌)
    """
    schema_text = json.dumps(_JSON_SCHEMA_EXAMPLE, ensure_ascii=False, indent=2)

    prompt = f"""
너는 "병원 가이드 문서"를 JSON으로 구조화하는 파서다.

아래 입력(md_content)은 Notion Markdown export일 수도 있고,
'업체정보(위치)  ~~' 같은 줄바꿈/탭 기반 텍스트일 수도 있다.

반드시 아래 스키마 형태의 JSON만 출력해라.
- 설명/문장/코드블록 없이 JSON만
- 값이 없으면 빈 문자열/빈 리스트/빈 딕트로 유지
- doctors, consultants는 가능한 한 추출해라
- allowed_hospitals는 "코: [..], 윤곽: [..]" 처럼 부위별 리스트 딕트
- blocked_hospitals는 병원명 리스트
- raw_data에는 원문에서 중요한 문장(사후관리 주의 등)도 적당히 요약해서 넣어도 된다.

JSON 스키마 예시:
{schema_text}

입력(md_content):
\"\"\"{md_content}\"\"\"
""".strip()

    result = generate_review_with_prompt(
        prompt=prompt,
        model=model,
        max_tokens=1200,
        temperature=0.2,
        return_usage=False,
    )

    data = _extract_json(result)
    normalized = _normalize_result(data)

    # 사치바이오형 문서는 표/섹션이 길어서 LLM이 일부 키를 누락할 수 있어 원문 보강.
    special_sections = _extract_special_sections(md_content)
    if special_sections:
        raw = normalized.get("raw_data")
        if not isinstance(raw, dict):
            raw = {}
        raw.update(special_sections)
        normalized["raw_data"] = raw

    return normalized
