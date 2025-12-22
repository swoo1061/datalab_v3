"""
컨텐츠 유형별 분석 시스템

5가지 컨텐츠 유형:
1. 상담후기 (consultation)
2. 시술후기 (procedure)
3. 경과후기 1개월 (recovery_1month)
4. 경과후기 2개월 (recovery_2month)
5. 경과후기 3개월 (recovery_3month)
"""
import re
import json
from typing import List, Dict, Optional, Tuple
from collections import Counter
from dataclasses import dataclass, field, asdict
from enum import Enum
import openai
from django.conf import settings


class ContentType(Enum):
    """컨텐츠 유형"""
    CONSULTATION = "consultation"  # 상담후기
    PROCEDURE = "procedure"  # 시술후기
    RECOVERY_1MONTH = "recovery_1month"  # 경과 1개월
    RECOVERY_2MONTH = "recovery_2month"  # 경과 2개월
    RECOVERY_3MONTH = "recovery_3month"  # 경과 3개월
    
    @property
    def display_name(self) -> str:
        names = {
            "consultation": "상담후기",
            "procedure": "시술후기",
            "recovery_1month": "경과후기 (1개월)",
            "recovery_2month": "경과후기 (2개월)",
            "recovery_3month": "경과후기 (3개월)",
        }
        return names.get(self.value, self.value)
    
    @property
    def description(self) -> str:
        descriptions = {
            "consultation": "상담 받고 온 직후, 병원 비교 및 원장님 상담 스타일 공유",
            "procedure": "수술 직후~2주, 생생한 경험과 초기 회복 과정",
            "recovery_1month": "수술 후 1개월, 붓기 빠지고 초기 결과 확인",
            "recovery_2month": "수술 후 2개월, 자리잡고 자연스러워지는 시기",
            "recovery_3month": "수술 후 3개월, 최종 결과와 총평",
        }
        return descriptions.get(self.value, "")


@dataclass
class ContentTypePattern:
    """컨텐츠 유형별 패턴 정의"""
    content_type: ContentType
    
    # 구조 패턴
    sections: List[str] = field(default_factory=list)
    section_weights: Dict[str, float] = field(default_factory=dict)
    
    # 필수 요소
    required_elements: List[str] = field(default_factory=list)
    
    # 표현 패턴
    common_expressions: List[str] = field(default_factory=list)
    opening_patterns: List[str] = field(default_factory=list)
    closing_patterns: List[str] = field(default_factory=list)
    
    # 톤/감정
    emotion_flow: List[str] = field(default_factory=list)
    dominant_emotions: List[str] = field(default_factory=list)
    
    # 금지/권장
    forbidden_elements: List[str] = field(default_factory=list)
    recommended_elements: List[str] = field(default_factory=list)
    
    # 통계
    avg_length: int = 0
    length_range: Tuple[int, int] = (0, 0)


# 기본 패턴 정의
DEFAULT_PATTERNS: Dict[ContentType, ContentTypePattern] = {
    ContentType.CONSULTATION: ContentTypePattern(
        content_type=ContentType.CONSULTATION,
        sections=["고민/배경", "탐색과정", "상담경험", "원장님인상", "결정/질문"],
        section_weights={"고민/배경": 0.15, "탐색과정": 0.20, "상담경험": 0.30, "원장님인상": 0.25, "결정/질문": 0.10},
        required_elements=["현재 고민", "병원 비교", "원장님 상담 스타일", "결정 이유 또는 추가 질문"],
        common_expressions=[
            "상담 받고 왔어요", "여러 곳 상담 받아봤는데", "원장님이 자세하게 설명해주셨어요",
            "다른 곳은 ~했는데 여기는", "수술 결정했어요", "아직 고민 중이에요"
        ],
        opening_patterns=["~ 상담 받고 왔어요", "상담 다녀왔습니다", "드디어 상담 갔다왔어요"],
        closing_patterns=["수술 결정했어요", "더 알아봐야겠어요", "궁금한 거 있으면 물어봐 주세요"],
        emotion_flow=["불안/고민", "비교/분석", "인상적", "결정/안심"],
        dominant_emotions=["신중함", "분석적", "기대감"],
        forbidden_elements=["수술 결과", "붓기", "회복 과정"],
        recommended_elements=["CT/사진 분석 언급", "상담 시간", "원장님 말투/스타일"],
        avg_length=800,
        length_range=(500, 1200),
    ),
    
    ContentType.PROCEDURE: ContentTypePattern(
        content_type=ContentType.PROCEDURE,
        sections=["수술정보", "당일경험", "힘들었던점", "병원케어", "현재상태"],
        section_weights={"수술정보": 0.10, "당일경험": 0.25, "힘들었던점": 0.25, "병원케어": 0.20, "현재상태": 0.20},
        required_elements=["수술 종류/범위", "당일 경험", "힘들었던 점(솔직)", "병원 케어", "현재 상태"],
        common_expressions=[
            "수술하고 왔어요", "솔직히 처음엔 힘들었어요", "붓기가 아직 있어요",
            "원장님께서 케어해주셔서", "생각보다 괜찮았어요", "아직 붓기가 있지만"
        ],
        opening_patterns=["수술하고 ~일차", "드디어 수술했어요", "~ 수술 받고 왔어요"],
        closing_patterns=["경과 또 올릴게요", "붓기 빠지면 또 후기 쓸게요", "기대되네요"],
        emotion_flow=["긴장", "힘듦", "안도", "기대"],
        dominant_emotions=["솔직함", "생생함", "희망"],
        forbidden_elements=["최종 결과", "완전히 자리잡음", "3개월 후"],
        recommended_elements=["구체적 일차", "통증/붓기 정도", "병원 연락/케어"],
        avg_length=700,
        length_range=(400, 1000),
    ),
    
    ContentType.RECOVERY_1MONTH: ContentTypePattern(
        content_type=ContentType.RECOVERY_1MONTH,
        sections=["현재시점", "회복과정", "현재상태", "주변반응", "기대감"],
        section_weights={"현재시점": 0.10, "회복과정": 0.25, "현재상태": 0.30, "주변반응": 0.20, "기대감": 0.15},
        required_elements=["1개월 시점 명시", "붓기 변화", "현재 상태", "주변 반응", "앞으로 기대"],
        common_expressions=[
            "수술한 지 한 달", "붓기가 거의 빠졌어요", "아직 조금 남아있지만",
            "주변에서 예뻐졌다고", "자연스러워지고 있어요", "더 기대돼요"
        ],
        opening_patterns=["벌써 한 달이 됐네요", "수술 1개월차", "한 달 경과 후기"],
        closing_patterns=["더 자리잡으면 또 올릴게요", "2개월차도 기대돼요", "진짜 잘한 것 같아요"],
        emotion_flow=["회고", "만족", "기대"],
        dominant_emotions=["뿌듯함", "기대감", "안도"],
        forbidden_elements=["최종 결과", "완전히 자리잡음"],
        recommended_elements=["붓기 변화 구체적", "주변 반응", "일상생활 언급"],
        avg_length=600,
        length_range=(400, 900),
    ),
    
    ContentType.RECOVERY_2MONTH: ContentTypePattern(
        content_type=ContentType.RECOVERY_2MONTH,
        sections=["현재시점", "변화과정", "자연스러움", "일상복귀", "만족도"],
        section_weights={"현재시점": 0.10, "변화과정": 0.25, "자연스러움": 0.30, "일상복귀": 0.20, "만족도": 0.15},
        required_elements=["2개월 시점 명시", "1개월 대비 변화", "자연스러움", "일상생활", "중간 만족도"],
        common_expressions=[
            "2개월 됐어요", "확실히 자리잡은 느낌", "1개월 때보다 훨씬",
            "이제 티도 안 나요", "일상생활 완전 복귀", "점점 만족스러워요"
        ],
        opening_patterns=["어느덧 2개월", "수술 2개월차", "두 달이 지났네요"],
        closing_patterns=["3개월 되면 또 올릴게요", "점점 좋아지고 있어요", "기다린 보람이 있네요"],
        emotion_flow=["안정", "만족", "확신"],
        dominant_emotions=["안정감", "만족", "자신감"],
        forbidden_elements=["붓기 심함", "힘들었던 점 과도하게"],
        recommended_elements=["1개월과 비교", "자연스러움 강조", "일상 복귀"],
        avg_length=550,
        length_range=(350, 800),
    ),
    
    ContentType.RECOVERY_3MONTH: ContentTypePattern(
        content_type=ContentType.RECOVERY_3MONTH,
        sections=["최종시점", "전체과정회고", "최종결과", "만족도총평", "추천"],
        section_weights={"최종시점": 0.10, "전체과정회고": 0.20, "최종결과": 0.30, "만족도총평": 0.25, "추천": 0.15},
        required_elements=["3개월 시점 명시", "전체 과정 요약", "최종 결과", "총평", "추천 여부"],
        common_expressions=[
            "드디어 3개월", "완전히 자리잡았어요", "최종 결과",
            "진짜 잘한 선택", "하길 정말 잘했다", "고민하시는 분들 추천"
        ],
        opening_patterns=["3개월 최종 후기", "드디어 3개월 됐어요", "수술 3개월차 총평"],
        closing_patterns=["정말 추천해요", "하길 잘했어요", "궁금한 거 있으면 물어봐 주세요"],
        emotion_flow=["회고", "만족", "자부심", "추천의지"],
        dominant_emotions=["만족", "자부심", "확신"],
        forbidden_elements=["아직 붓기 있음", "불확실한 결과"],
        recommended_elements=["전후 비교", "총 비용", "재방문/사후관리 언급"],
        avg_length=700,
        length_range=(500, 1000),
    ),
}


@dataclass
class ContentTypeAnalysisResult:
    """유형별 분석 결과"""
    content_type: ContentType
    sample_count: int
    
    # 구조 분석
    detected_sections: Dict[str, float]  # 섹션별 등장 비율
    avg_section_order: List[str]  # 평균적인 섹션 순서
    
    # 표현 분석
    extracted_expressions: List[str]
    opening_patterns: List[str]
    closing_patterns: List[str]
    
    # 통계
    avg_length: int
    length_range: Tuple[int, int]
    
    # 감정/톤
    emotion_keywords: List[str]
    tone_description: str
    
    # 추출된 템플릿
    template: ContentTypePattern


class ContentTypeClassifier:
    """컨텐츠 유형 분류기"""
    
    # 유형별 키워드
    TYPE_KEYWORDS = {
        ContentType.CONSULTATION: [
            "상담 받고", "상담 다녀", "상담 갔다", "상담 후기",
            "여러 곳 상담", "비교", "원장님이 설명", "수술 결정"
        ],
        ContentType.PROCEDURE: [
            "수술하고", "수술 받고", "수술 당일", "D-day",
            "일차", "붓기", "힘들었", "아직 붓기", "멍"
        ],
        ContentType.RECOVERY_1MONTH: [
            "한 달", "1개월", "한달", "4주",
            "붓기 빠", "주변에서", "자리잡"
        ],
        ContentType.RECOVERY_2MONTH: [
            "두 달", "2개월", "두달", "8주",
            "확실히 자리", "자연스러", "티 안 나"
        ],
        ContentType.RECOVERY_3MONTH: [
            "세 달", "3개월", "세달", "12주",
            "최종", "완전히", "총평", "추천"
        ],
    }
    
    @classmethod
    def classify(cls, text: str) -> Tuple[ContentType, float]:
        """
        텍스트를 컨텐츠 유형으로 분류
        
        Returns:
            (유형, 신뢰도)
        """
        text_lower = text.lower()
        scores = {}
        
        for content_type, keywords in cls.TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[content_type] = score
        
        if not any(scores.values()):
            return ContentType.PROCEDURE, 0.3  # 기본값
        
        best_type = max(scores, key=scores.get)
        max_score = scores[best_type]
        total_keywords = len(cls.TYPE_KEYWORDS[best_type])
        confidence = min(max_score / total_keywords * 2, 1.0)
        
        return best_type, confidence
    
    @classmethod
    def classify_with_llm(cls, text: str) -> Tuple[ContentType, float]:
        """LLM을 사용한 정확한 분류"""
        
        prompt = f"""다음 후기 글의 유형을 분류해주세요.

[후기]
{text[:1000]}

[유형 선택지]
1. consultation - 상담후기: 상담 받고 온 직후, 병원 비교/원장님 스타일 공유
2. procedure - 시술후기: 수술 직후~2주, 생생한 경험과 초기 회복
3. recovery_1month - 경과후기 1개월: 붓기 빠지고 초기 결과 확인
4. recovery_2month - 경과후기 2개월: 자리잡고 자연스러워지는 시기
5. recovery_3month - 경과후기 3개월: 최종 결과와 총평

JSON 형식으로 응답:
{{"type": "유형코드", "confidence": 0.0~1.0, "reason": "판단 이유"}}
"""
        
        try:
            response = openai.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": "후기 유형 분류 전문가입니다. JSON으로만 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=200,
            )
            
            result_text = response.choices[0].message.content
            result_text = re.sub(r'^```json\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
            result = json.loads(result_text)
            
            type_map = {
                "consultation": ContentType.CONSULTATION,
                "procedure": ContentType.PROCEDURE,
                "recovery_1month": ContentType.RECOVERY_1MONTH,
                "recovery_2month": ContentType.RECOVERY_2MONTH,
                "recovery_3month": ContentType.RECOVERY_3MONTH,
            }
            
            content_type = type_map.get(result.get("type"), ContentType.PROCEDURE)
            confidence = float(result.get("confidence", 0.5))
            
            return content_type, confidence
            
        except Exception as e:
            # 폴백: 키워드 기반
            return cls.classify(text)


class ContentTypeAnalyzer:
    """컨텐츠 유형별 분석기"""
    
    def __init__(self, texts: List[str], content_type: Optional[ContentType] = None):
        """
        Args:
            texts: 분석할 후기 텍스트 리스트 (같은 유형이어야 함)
            content_type: 컨텐츠 유형 (None이면 자동 분류)
        """
        self.texts = [t.strip() for t in texts if t.strip()]
        
        if content_type:
            self.content_type = content_type
        else:
            # 첫 번째 텍스트로 유형 추정
            self.content_type, _ = ContentTypeClassifier.classify(self.texts[0])
        
        self.base_pattern = DEFAULT_PATTERNS.get(self.content_type)
    
    def analyze_structure(self) -> Dict[str, float]:
        """글 구조 분석 - 섹션별 등장 비율"""
        
        section_keywords = {
            "고민/배경": ["고민", "스트레스", "오래 고민", "콤플렉스", "때문에"],
            "탐색과정": ["여러 곳", "비교", "찾아보", "알아보", "상담 예약"],
            "상담경험": ["상담", "설명해주", "분석", "CT", "원장님이"],
            "원장님인상": ["원장님", "선생님", "친절", "자세하게", "느낌"],
            "수술정보": ["수술", "시술", "진행", "마취", "시간"],
            "당일경험": ["당일", "그날", "수술실", "수술대", "들어가"],
            "힘들었던점": ["힘들", "아프", "힘든", "못 먹", "불편"],
            "병원케어": ["케어", "체크", "연락", "관리", "걱정"],
            "현재상태": ["지금", "현재", "아직", "상태", "붓기"],
            "주변반응": ["주변", "친구", "가족", "예뻐", "달라"],
            "회복과정": ["회복", "빠지", "나아", "좋아"],
            "자연스러움": ["자연스럽", "티 안 나", "어색하지 않"],
            "만족도": ["만족", "잘한", "좋아요", "뿌듯"],
            "추천": ["추천", "강추", "가보세요", "고민하시는 분"],
            "기대감": ["기대", "기다려", "궁금", "다음"],
            "결정/질문": ["결정", "결심", "궁금", "물어", "질문"],
        }
        
        section_counts = {section: 0 for section in section_keywords}
        
        for text in self.texts:
            for section, keywords in section_keywords.items():
                if any(kw in text for kw in keywords):
                    section_counts[section] += 1
        
        total = len(self.texts)
        section_rates = {
            section: round(count / total, 2) if total > 0 else 0
            for section, count in section_counts.items()
        }
        
        # 비율이 0.3 이상인 섹션만 반환
        return {k: v for k, v in section_rates.items() if v >= 0.3}
    
    def extract_expressions(self) -> Dict[str, List[str]]:
        """표현 패턴 추출"""
        
        # 문장 시작 패턴 (도입부)
        opening_sentences = []
        for text in self.texts:
            first_sentences = re.split(r'[.!?]\s+', text)[:2]
            opening_sentences.extend(first_sentences)
        
        # 문장 끝 패턴 (마무리)
        closing_sentences = []
        for text in self.texts:
            last_sentences = re.split(r'[.!?]\s+', text)[-2:]
            closing_sentences.extend(last_sentences)
        
        return {
            "openings": opening_sentences[:10],
            "closings": closing_sentences[:10],
        }
    
    def analyze_statistics(self) -> Dict:
        """통계 분석"""
        
        lengths = [len(t) for t in self.texts]
        
        return {
            "avg_length": int(sum(lengths) / len(lengths)) if lengths else 0,
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "sample_count": len(self.texts),
        }
    
    def analyze_with_llm(self) -> Dict:
        """LLM을 사용한 심층 분석"""
        
        samples = self.texts[:5]
        samples_text = "\n\n---\n\n".join([t[:800] for t in samples])
        
        prompt = f"""다음은 "{self.content_type.display_name}" 유형의 후기 {len(samples)}개입니다.
이 유형의 특성을 분석해주세요.

[후기 샘플]
{samples_text}

다음 JSON 형식으로 응답:
{{
    "structure": {{
        "sections": ["이 유형에서 등장하는 섹션 순서대로"],
        "section_descriptions": {{"섹션명": "해당 섹션에서 다루는 내용"}}
    }},
    "expressions": {{
        "common": ["자주 쓰는 표현 10개"],
        "opening": ["시작 표현 5개"],
        "closing": ["마무리 표현 5개"]
    }},
    "tone": {{
        "description": "전체적인 톤 설명",
        "emotions": ["주요 감정 키워드 5개"],
        "flow": ["감정 흐름 (시작→끝)"]
    }},
    "requirements": {{
        "must_have": ["필수 포함 요소 5개"],
        "should_avoid": ["피해야 할 요소 3개"]
    }},
    "tips": ["이 유형 작성 시 팁 3개"]
}}
"""
        
        try:
            response = openai.chat.completions.create(
                model="gpt-5-nano",
                messages=[
                    {"role": "system", "content": "후기 스타일 분석 전문가입니다. JSON으로만 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=1500,
            )
            
            result_text = response.choices[0].message.content
            result_text = re.sub(r'^```json\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
            
            return json.loads(result_text)
            
        except Exception as e:
            return {"error": str(e)}
    
    def analyze(self) -> ContentTypeAnalysisResult:
        """전체 분석 수행"""
        
        # 구조 분석
        detected_sections = self.analyze_structure()
        
        # 표현 추출
        expressions = self.extract_expressions()
        
        # 통계
        stats = self.analyze_statistics()
        
        # LLM 분석
        llm_result = self.analyze_with_llm()
        
        # 템플릿 업데이트
        template = ContentTypePattern(
            content_type=self.content_type,
            sections=llm_result.get("structure", {}).get("sections", self.base_pattern.sections),
            required_elements=llm_result.get("requirements", {}).get("must_have", self.base_pattern.required_elements),
            common_expressions=llm_result.get("expressions", {}).get("common", []),
            opening_patterns=llm_result.get("expressions", {}).get("opening", []),
            closing_patterns=llm_result.get("expressions", {}).get("closing", []),
            emotion_flow=llm_result.get("tone", {}).get("flow", []),
            dominant_emotions=llm_result.get("tone", {}).get("emotions", []),
            forbidden_elements=llm_result.get("requirements", {}).get("should_avoid", []),
            avg_length=stats["avg_length"],
            length_range=(stats["min_length"], stats["max_length"]),
        )
        
        return ContentTypeAnalysisResult(
            content_type=self.content_type,
            sample_count=stats["sample_count"],
            detected_sections=detected_sections,
            avg_section_order=template.sections,
            extracted_expressions=template.common_expressions,
            opening_patterns=template.opening_patterns,
            closing_patterns=template.closing_patterns,
            avg_length=stats["avg_length"],
            length_range=(stats["min_length"], stats["max_length"]),
            emotion_keywords=template.dominant_emotions,
            tone_description=llm_result.get("tone", {}).get("description", ""),
            template=template,
        )


def analyze_by_content_type(
    all_texts: List[str],
    auto_classify: bool = True
) -> Dict[ContentType, ContentTypeAnalysisResult]:
    """
    전체 텍스트를 유형별로 분류하고 각각 분석
    
    Args:
        all_texts: 전체 후기 텍스트 리스트 (혼합)
        auto_classify: 자동 분류 여부
        
    Returns:
        유형별 분석 결과
    """
    # 유형별 분류
    classified: Dict[ContentType, List[str]] = {ct: [] for ct in ContentType}
    
    for text in all_texts:
        if auto_classify:
            content_type, confidence = ContentTypeClassifier.classify(text)
            if confidence >= 0.3:
                classified[content_type].append(text)
        else:
            # 수동 분류 필요
            pass
    
    # 유형별 분석
    results = {}
    for content_type, texts in classified.items():
        if len(texts) >= 2:  # 최소 2개 이상
            analyzer = ContentTypeAnalyzer(texts, content_type)
            results[content_type] = analyzer.analyze()
    
    return results


def generate_content_type_template_markdown(
    analysis_result: ContentTypeAnalysisResult
) -> str:
    """분석 결과를 마크다운 템플릿으로 변환"""
    
    template = analysis_result.template
    ct = analysis_result.content_type
    
    md = f"""# {ct.display_name} 작성 가이드

> {ct.description}

## 📊 분석 기반 정보
- 분석 샘플: {analysis_result.sample_count}개
- 평균 글자수: {analysis_result.avg_length}자
- 글자수 범위: {analysis_result.length_range[0]}~{analysis_result.length_range[1]}자

---

## 🏗️ 글 구조

"""
    
    for i, section in enumerate(template.sections, 1):
        weight = template.section_weights.get(section, 0)
        weight_text = f" ({int(weight*100)}%)" if weight else ""
        md += f"{i}. **{section}**{weight_text}\n"
    
    md += f"""
---

## ✅ 필수 포함 요소

"""
    
    for elem in template.required_elements:
        md += f"- {elem}\n"
    
    md += f"""
---

## 💬 자주 쓰는 표현

### 시작 표현
"""
    
    for expr in template.opening_patterns[:5]:
        md += f"- "{expr}"\n"
    
    md += """
### 중간 표현
"""
    
    for expr in template.common_expressions[:7]:
        md += f"- "{expr}"\n"
    
    md += """
### 마무리 표현
"""
    
    for expr in template.closing_patterns[:5]:
        md += f"- "{expr}"\n"
    
    md += f"""
---

## 🎭 톤 & 감정

**전체 톤**: {analysis_result.tone_description}

**감정 흐름**: {' → '.join(template.emotion_flow)}

**주요 감정**: {', '.join(template.dominant_emotions)}

---

## ⚠️ 주의사항

### 피해야 할 것
"""
    
    for elem in template.forbidden_elements:
        md += f"- ❌ {elem}\n"
    
    md += """
### 권장사항
"""
    
    for elem in template.recommended_elements:
        md += f"- ✅ {elem}\n"
    
    md += """
---

## 📝 작성 예시 구조

```
[도입]
{opening_example}

[본문]
- 섹션 1: ...
- 섹션 2: ...
- ...

[마무리]
{closing_example}
```
"""
    
    return md
