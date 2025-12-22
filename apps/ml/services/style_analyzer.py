"""
스타일 분석 서비스

카페 후기 텍스트를 분석하여 스타일 특성을 추출하고
페르소나/카페 프로필을 자동 생성합니다.
"""
import re
import json
from typing import List, Dict, Optional, Tuple
from collections import Counter
from dataclasses import dataclass, asdict
import openai
from django.conf import settings


@dataclass
class QuantitativeAnalysis:
    """정량 분석 결과"""
    total_samples: int
    avg_char_count: float
    min_char_count: int
    max_char_count: int
    avg_sentence_count: float
    avg_paragraph_count: float
    emoji_usage_rate: float  # 0~1
    common_emojis: List[str]
    ending_patterns: Dict[str, float]  # 문장 끝 패턴 비율
    question_rate: float  # 질문 비율
    exclamation_rate: float  # 감탄문 비율


@dataclass
class QualitativeAnalysis:
    """정성 분석 결과 (LLM)"""
    speech_style: str  # 말투 설명
    tone: str  # 톤 (친근, 정중, 캐주얼 등)
    detail_level: str  # detailed, moderate, brief
    structure_pattern: str  # 글 구조 패턴
    common_expressions: List[str]  # 자주 쓰는 표현
    keywords: List[str]  # 핵심 키워드
    estimated_persona: Dict  # 추정 페르소나
    cafe_characteristics: Dict  # 추정 카페 특성
    writing_tips: List[str]  # 작성 팁


@dataclass
class StyleAnalysisResult:
    """전체 분석 결과"""
    quantitative: QuantitativeAnalysis
    qualitative: QualitativeAnalysis
    suggested_persona: Dict
    suggested_cafe_profile: Dict
    sample_prompt_additions: str


class StyleAnalyzer:
    """스타일 분석기"""
    
    # 이모지 패턴
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 이모티콘
        "\U0001F300-\U0001F5FF"  # 심볼 & 픽토그램
        "\U0001F680-\U0001F6FF"  # 교통 & 지도
        "\U0001F1E0-\U0001F1FF"  # 플래그
        "\U00002702-\U000027B0"  # 기타
        "\U0001F900-\U0001F9FF"  # 보충 이모지
        "]+", 
        flags=re.UNICODE
    )
    
    # 문장 끝 패턴
    ENDING_PATTERNS = {
        '~요': r'[가-힣]+요[.!?]?\s*$',
        '~임': r'[가-힣]+임[.!?]?\s*$',
        '~음': r'[가-힣]+음[.!?]?\s*$',
        '~ㅋㅋ': r'ㅋ{2,}[.!?]?\s*$',
        '~ㅎㅎ': r'ㅎ{2,}[.!?]?\s*$',
        '~습니다': r'습니다[.!?]?\s*$',
        '~해요': r'해요[.!?]?\s*$',
        '~했어요': r'했어요[.!?]?\s*$',
        '~네요': r'네요[.!?]?\s*$',
        '~던데': r'던데[.!?]?\s*$',
        '~거든요': r'거든요[.!?]?\s*$',
    }
    
    def __init__(self, texts: List[str]):
        """
        Args:
            texts: 분석할 후기 텍스트 리스트
        """
        self.texts = [t.strip() for t in texts if t.strip()]
        self.sentences_all = []
        
        # 문장 분리
        for text in self.texts:
            sentences = re.split(r'[.!?]\s+', text)
            self.sentences_all.extend([s.strip() for s in sentences if s.strip()])
    
    def analyze_quantitative(self) -> QuantitativeAnalysis:
        """정량 분석 수행"""
        if not self.texts:
            raise ValueError("분석할 텍스트가 없습니다")
        
        # 기본 통계
        char_counts = [len(t) for t in self.texts]
        sentence_counts = [len(re.split(r'[.!?]+', t)) for t in self.texts]
        paragraph_counts = [len(t.split('\n\n')) for t in self.texts]
        
        # 이모지 분석
        emoji_counts = []
        all_emojis = []
        for text in self.texts:
            emojis = self.EMOJI_PATTERN.findall(text)
            emoji_counts.append(len(emojis))
            all_emojis.extend(emojis)
        
        emoji_counter = Counter(all_emojis)
        common_emojis = [e for e, _ in emoji_counter.most_common(10)]
        
        # 텍스트당 이모지 사용률
        emoji_usage_rate = sum(1 for c in emoji_counts if c > 0) / len(self.texts)
        
        # 문장 끝 패턴 분석
        ending_counts = {pattern: 0 for pattern in self.ENDING_PATTERNS}
        for sentence in self.sentences_all:
            for pattern_name, pattern_regex in self.ENDING_PATTERNS.items():
                if re.search(pattern_regex, sentence):
                    ending_counts[pattern_name] += 1
                    break
        
        total_sentences = len(self.sentences_all)
        ending_patterns = {
            k: round(v / total_sentences, 3) if total_sentences > 0 else 0
            for k, v in ending_counts.items()
        }
        
        # 질문/감탄 비율
        question_count = sum(1 for s in self.sentences_all if '?' in s)
        exclamation_count = sum(1 for s in self.sentences_all if '!' in s)
        
        return QuantitativeAnalysis(
            total_samples=len(self.texts),
            avg_char_count=round(sum(char_counts) / len(char_counts), 1),
            min_char_count=min(char_counts),
            max_char_count=max(char_counts),
            avg_sentence_count=round(sum(sentence_counts) / len(sentence_counts), 1),
            avg_paragraph_count=round(sum(paragraph_counts) / len(paragraph_counts), 1),
            emoji_usage_rate=round(emoji_usage_rate, 2),
            common_emojis=common_emojis,
            ending_patterns=ending_patterns,
            question_rate=round(question_count / total_sentences, 3) if total_sentences > 0 else 0,
            exclamation_rate=round(exclamation_count / total_sentences, 3) if total_sentences > 0 else 0,
        )
    
    def analyze_qualitative(self, quant: QuantitativeAnalysis) -> QualitativeAnalysis:
        """LLM을 사용한 정성 분석"""
        
        # 샘플 텍스트 준비 (최대 5개, 각 1000자 제한)
        samples = self.texts[:5]
        samples_text = "\n\n---\n\n".join([t[:1000] for t in samples])
        
        prompt = f"""다음은 같은 카페/플랫폼에 올라온 병원 후기 {len(samples)}개입니다.
이 후기들의 공통적인 스타일 특성을 분석해주세요.

[후기 샘플]
{samples_text}

[정량 분석 결과 참고]
- 평균 글자수: {quant.avg_char_count}자
- 이모지 사용률: {quant.emoji_usage_rate * 100:.0f}%
- 주요 문장 끝 패턴: {', '.join([f'{k}({v*100:.0f}%)' for k, v in sorted(quant.ending_patterns.items(), key=lambda x: -x[1])[:3]])}

다음 형식의 JSON으로 응답해주세요:
{{
    "speech_style": "말투 스타일 상세 설명 (예: ~요체 위주, 부드러운 존댓말)",
    "tone": "톤 (예: 친근함, 정중함, 캐주얼, 전문적)",
    "detail_level": "detailed/moderate/brief 중 하나",
    "structure_pattern": "글 구조 패턴 설명 (예: 방문계기→상담→시술→결과 순서)",
    "common_expressions": ["자주 쓰는 표현 5개"],
    "keywords": ["핵심 키워드 5개"],
    "estimated_persona": {{
        "age_group": "추정 연령대",
        "gender": "추정 성별",
        "occupation": "추정 직업/상황",
        "personality": "추정 성격/특징"
    }},
    "cafe_characteristics": {{
        "vibe": "카페 분위기",
        "audience": "주요 독자층",
        "content_focus": "콘텐츠 초점"
    }},
    "writing_tips": ["이 스타일로 작성할 때 팁 3개"]
}}"""

        try:
            response = openai.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": "당신은 텍스트 스타일 분석 전문가입니다. JSON 형식으로만 응답하세요."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=1500,
            )
            
            result_text = response.choices[0].message.content
            
            # JSON 파싱 (```json 제거)
            result_text = re.sub(r'^```json\s*', '', result_text)
            result_text = re.sub(r'\s*```$', '', result_text)
            
            result = json.loads(result_text)
            
            return QualitativeAnalysis(
                speech_style=result.get('speech_style', ''),
                tone=result.get('tone', ''),
                detail_level=result.get('detail_level', 'moderate'),
                structure_pattern=result.get('structure_pattern', ''),
                common_expressions=result.get('common_expressions', []),
                keywords=result.get('keywords', []),
                estimated_persona=result.get('estimated_persona', {}),
                cafe_characteristics=result.get('cafe_characteristics', {}),
                writing_tips=result.get('writing_tips', []),
            )
            
        except Exception as e:
            # 폴백: 기본값 반환
            return QualitativeAnalysis(
                speech_style="분석 실패",
                tone="알 수 없음",
                detail_level="moderate",
                structure_pattern="",
                common_expressions=[],
                keywords=[],
                estimated_persona={},
                cafe_characteristics={},
                writing_tips=[f"분석 오류: {str(e)}"],
            )
    
    def generate_persona_suggestion(
        self, 
        quant: QuantitativeAnalysis, 
        qual: QualitativeAnalysis
    ) -> Dict:
        """분석 결과로부터 페르소나 제안 생성"""
        
        persona = qual.estimated_persona
        
        return {
            "name": f"{persona.get('age_group', '20대')} {persona.get('occupation', '직장인')} {persona.get('gender', '여성')}",
            "description": f"{persona.get('personality', '')} 스타일",
            "age_group": persona.get('age_group', '20대'),
            "gender": persona.get('gender', '여성'),
            "speech_style": qual.speech_style,
            "detail_level": qual.detail_level,
            "emoji_usage": quant.emoji_usage_rate > 0.3,
            "example_phrases": qual.common_expressions[:5],
            "keywords": qual.keywords[:5],
        }
    
    def generate_cafe_profile_suggestion(
        self,
        quant: QuantitativeAnalysis,
        qual: QualitativeAnalysis
    ) -> Dict:
        """분석 결과로부터 카페 프로필 제안 생성"""
        
        cafe_char = qual.cafe_characteristics
        
        # 글자수 범위 계산 (평균 ± 30%)
        min_len = int(quant.avg_char_count * 0.7)
        max_len = int(quant.avg_char_count * 1.3)
        
        return {
            "name": f"분석된 카페 스타일",
            "vibe": cafe_char.get('vibe', qual.tone),
            "min_length": min_len,
            "max_length": max_len,
            "required_sections": [],
            "forbidden_words": ["광고", "협찬", "최고", "인생"],  # 기본 금지어
            "recommended_words": qual.keywords[:3],
            "title_style": "",
            "image_required": False,
            "tips": "\n".join(qual.writing_tips),
        }
    
    def generate_prompt_additions(
        self,
        quant: QuantitativeAnalysis,
        qual: QualitativeAnalysis
    ) -> str:
        """프롬프트에 추가할 스타일 가이드 생성"""
        
        # 주요 문장 끝 패턴 추출
        top_endings = sorted(quant.ending_patterns.items(), key=lambda x: -x[1])[:3]
        endings_text = ', '.join([f'"{k}"' for k, v in top_endings if v > 0.1])
        
        emoji_text = "적극 사용" if quant.emoji_usage_rate > 0.5 else \
                     "가끔 사용" if quant.emoji_usage_rate > 0.2 else "거의 사용 안함"
        
        return f"""
═══════════════════════════════════════════════════════════════
📊 추출된 스타일 가이드
═══════════════════════════════════════════════════════════════
- 말투: {qual.speech_style}
- 톤: {qual.tone}
- 글자수: {quant.avg_char_count:.0f}자 내외 ({quant.min_char_count}~{quant.max_char_count}자 범위)
- 문장 끝 패턴: {endings_text}
- 이모지: {emoji_text} {', '.join(quant.common_emojis[:5]) if quant.common_emojis else ''}
- 자주 쓰는 표현: {', '.join(qual.common_expressions[:5])}
- 글 구조: {qual.structure_pattern}

✍️ 스타일 팁
{chr(10).join([f'- {tip}' for tip in qual.writing_tips])}
"""
    
    def analyze(self) -> StyleAnalysisResult:
        """전체 분석 수행"""
        
        # 정량 분석
        quant = self.analyze_quantitative()
        
        # 정성 분석
        qual = self.analyze_qualitative(quant)
        
        # 제안 생성
        persona_suggestion = self.generate_persona_suggestion(quant, qual)
        cafe_suggestion = self.generate_cafe_profile_suggestion(quant, qual)
        prompt_additions = self.generate_prompt_additions(quant, qual)
        
        return StyleAnalysisResult(
            quantitative=quant,
            qualitative=qual,
            suggested_persona=persona_suggestion,
            suggested_cafe_profile=cafe_suggestion,
            sample_prompt_additions=prompt_additions,
        )


def analyze_style(texts: List[str]) -> Dict:
    """
    스타일 분석 편의 함수
    
    Args:
        texts: 분석할 후기 텍스트 리스트
        
    Returns:
        분석 결과 딕셔너리
    """
    analyzer = StyleAnalyzer(texts)
    result = analyzer.analyze()
    
    return {
        "quantitative": asdict(result.quantitative),
        "qualitative": asdict(result.qualitative),
        "suggested_persona": result.suggested_persona,
        "suggested_cafe_profile": result.suggested_cafe_profile,
        "prompt_additions": result.sample_prompt_additions,
    }


def analyze_and_create_persona(texts: List[str], persona_name: Optional[str] = None):
    """
    스타일 분석 후 페르소나 모델 생성
    
    Args:
        texts: 분석할 후기 텍스트 리스트
        persona_name: 페르소나 이름 (없으면 자동 생성)
        
    Returns:
        생성된 Persona 인스턴스
    """
    from apps.data.models import Persona
    
    result = analyze_style(texts)
    suggestion = result["suggested_persona"]
    
    name = persona_name or suggestion["name"]
    
    persona = Persona.objects.create(
        name=name,
        description=suggestion.get("description", ""),
        age_group=suggestion.get("age_group", ""),
        gender=suggestion.get("gender", ""),
        speech_style=suggestion.get("speech_style", ""),
        detail_level=suggestion.get("detail_level", "moderate"),
        emoji_usage=suggestion.get("emoji_usage", False),
        example_phrases=suggestion.get("example_phrases", []),
        keywords=suggestion.get("keywords", []),
    )
    
    return persona


def analyze_and_create_cafe_profile(texts: List[str], cafe_name: str):
    """
    스타일 분석 후 카페 프로필 모델 생성
    
    Args:
        texts: 분석할 후기 텍스트 리스트
        cafe_name: 카페 이름
        
    Returns:
        생성된 CafeProfile 인스턴스
    """
    from apps.data.models import CafeProfile
    
    result = analyze_style(texts)
    suggestion = result["suggested_cafe_profile"]
    
    cafe = CafeProfile.objects.create(
        name=cafe_name,
        vibe=suggestion.get("vibe", ""),
        min_length=suggestion.get("min_length", 500),
        max_length=suggestion.get("max_length", 1500),
        required_sections=suggestion.get("required_sections", []),
        forbidden_words=suggestion.get("forbidden_words", []),
        recommended_words=suggestion.get("recommended_words", []),
        tips=suggestion.get("tips", ""),
    )
    
    return cafe
