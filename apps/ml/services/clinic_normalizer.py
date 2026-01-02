from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
import re


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        return str(v)
    return str(v).strip()


def _extract_range(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    "300~350", "300 ~ 350", "300-350" 등에서 a,b 추출
    """
    t = _clean_str(text)
    if not t:
        return None, None

    # 숫자만 있는 경우
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return t, None

    # 범위
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:~|-)\s*(\d+(?:\.\d+)?)", t)
    if m:
        return m.group(1), m.group(2)

    # 그 외는 그대로 단일 price로 취급
    return t, None


def normalize_price_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    어떤 형태로 오든 템플릿이 안전하게 쓰는 키로 맞춤:
    - doctor_name, doctor_code, procedure
    - price (단일) 또는 price_a/price_b (범위)
    - price_display (화면 표시용)
    - note
    """
    procedure = _clean_str(item.get("procedure") or item.get("시술") or item.get("시술명"))
    doctor_name = _clean_str(item.get("doctor_name") or item.get("원장") or item.get("doctor") or "")
    doctor_code = _clean_str(item.get("doctor_code") or item.get("code") or "")

    # 가격 후보 키들(여기서 다 흡수)
    raw_price = (
        item.get("price_display")
        or item.get("price")
        or item.get("price_만원")
        or item.get("price_manwon")
        or item.get("금액")
        or item.get("금액(만원)")
        or item.get("amount")
        or ""
    )
    raw_price = _clean_str(raw_price)

    # 이미 범위로 분리된 케이스
    price_a = item.get("price_a")
    price_b = item.get("price_b")

    if price_a or price_b:
        a = _clean_str(price_a)
        b = _clean_str(price_b)
    else:
        a, b = _extract_range(raw_price)

    a = _clean_str(a) if a is not None else ""
    b = _clean_str(b) if b is not None else ""

    note = _clean_str(item.get("note") or item.get("비고") or item.get("memo") or "")

    # price: 단일이면 price에 넣고, 범위면 price_a/price_b 사용
    price = ""
    if a and not b and re.fullmatch(r"\d+(\.\d+)?", a):
        price = a

    # 표시 문자열
    if a and b and re.fullmatch(r"\d+(\.\d+)?", a) and re.fullmatch(r"\d+(\.\d+)?", b):
        price_display = f"{a} ~ {b} 만원"
    elif price:
        price_display = f"{price} 만원"
    elif raw_price:
        # 숫자 범위 파싱 실패했으면 원문 유지(최후의 안전망)
        price_display = raw_price if ("만원" in raw_price or "원" in raw_price) else f"{raw_price} 만원"
    else:
        price_display = ""

    return {
        "doctor_name": doctor_name,
        "doctor_code": doctor_code,
        "procedure": procedure,
        "price": price,           # 템플릿이 찾는 핵심 키
        "price_a": a if b else "",  # 범위일 때만 의미
        "price_b": b if b else "",
        "price_display": price_display,
        "note": note,
    }


def normalize_price_list(price_list: Any) -> List[Dict[str, Any]]:
    if not isinstance(price_list, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in price_list:
        if isinstance(item, dict):
            normalized.append(normalize_price_item(item))
    # 빈 시술 제거(선택)
    normalized = [x for x in normalized if x.get("procedure")]
    return normalized


def normalize_clinic_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    전체 데이터에서 화면/저장 시 깨지기 쉬운 부분만 표준화.
    """
    if not isinstance(data, dict):
        return {}

    data = dict(data)  # shallow copy

    # basic_info 안전장치
    basic = data.get("basic_info") or {}
    if not isinstance(basic, dict):
        basic = {}
    data["basic_info"] = {
        "location": _clean_str(basic.get("location")),
        "hours": _clean_str(basic.get("hours")),
        "parking": _clean_str(basic.get("parking")),
        **{k: v for k, v in basic.items() if k not in ("location", "hours", "parking")},
    }

    # price_list 정규화(핵심)
    data["price_list"] = normalize_price_list(data.get("price_list"))

    # blocked_hospitals 타입 보정
    bh = data.get("blocked_hospitals")
    if isinstance(bh, str):
        data["blocked_hospitals"] = [x.strip() for x in bh.split(",") if x.strip()]
    elif not isinstance(bh, list):
        data["blocked_hospitals"] = []

    return data