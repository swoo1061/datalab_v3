"""
리뷰 생성 프롬프트 빌더

병원 정보, 페르소나, 카페 설정을 조합하여 최적화된 프롬프트를 생성합니다.
"""
from typing import Dict, Optional, Any
from dataclasses import dataclass


# 컨텐츠 유형별 가이드
CONTENT_TYPE_GUIDES = {
    "consultation": {
        "name": "상담후기",
        "timing": "상담 직후 (수술 전)",
        "structure": [
            "고민/배경 (15%): 현재 상태와 고민 설명",
            "탐색과정 (20%): 여러 병원 알아본 과정",
            "상담경험 (30%): 이 병원에서의 상담 경험 (핵심)",
            "원장님인상 (25%): 원장님 스타일, 느낌",
            "결정/질문 (10%): 수술 결정 또는 추가 질문"
        ],
        "must_include": [
            "현재 고민/상태",
            "여러 병원 비교 언급",
            "원장님 상담 스타일 묘사",
            "결정 이유 또는 추가 질문"
        ],
        "expressions": [
            "상담 받고 왔어요",
            "여러 곳 상담 받아봤는데",
            "원장님이 자세하게 설명해주셨어요",
            "다른 곳은 ~했는데 여기는"
        ],
        "forbidden": [
            "수술 결과 언급 (아직 안 했으니까)",
            "붓기, 회복 과정 언급",
            "최종 만족도"
        ],
        "tone": "신중함, 분석적, 기대감"
    },
    
    "procedure": {
        "name": "시술후기",
        "timing": "수술 직후 ~ 2주 (D+1 ~ D+14)",
        "structure": [
            "수술정보 (10%): 무슨 수술을 했는지",
            "당일경험 (25%): 수술 당일의 생생한 경험",
            "힘들었던점 (25%): 솔직하게 힘들었던 부분 (핵심)",
            "병원케어 (20%): 병원에서 어떻게 관리해줬는지",
            "현재상태 (20%): 지금 상태와 앞으로 기대"
        ],
        "must_include": [
            "수술 종류/범위",
            "구체적 일차 (D+N)",
            "힘들었던 점 솔직하게",
            "병원 케어",
            "현재 상태"
        ],
        "expressions": [
            "수술하고 ~일차",
            "솔직히 처음엔 힘들었어요",
            "원장님께서 케어해주셔서",
            "아직 붓기가 있지만"
        ],
        "forbidden": [
            "최종 결과 단정",
            "완전히 자리잡음",
            "과도한 고통 묘사"
        ],
        "tone": "솔직함, 생생함, 희망"
    },
    
    "recovery_1month": {
        "name": "경과후기 (1개월)",
        "timing": "수술 후 1개월 (4주차)",
        "structure": [
            "현재시점 (10%): 1개월이 됐다는 언급",
            "회복과정 (25%): 지난 한 달간의 회복 과정",
            "현재상태 (30%): 지금 상태 구체적으로 (핵심)",
            "주변반응 (20%): 친구, 가족 등 주변 반응",
            "기대감 (15%): 앞으로 더 좋아질 거라는 기대"
        ],
        "must_include": [
            "1개월 시점 명시",
            "붓기 변화",
            "현재 상태",
            "주변 반응",
            "앞으로 기대"
        ],
        "expressions": [
            "벌써 한 달이 됐네요",
            "아직 조금 남아있지만",
            "주변에서 예뻐졌다고",
            "더 자리잡으면 또 올릴게요"
        ],
        "forbidden": [
            "완전히 자리잡음 (아직 1개월)",
            "최종 결과 단정",
            "100% 확신"
        ],
        "tone": "뿌듯함, 기대감, 안도"
    },
    
    "recovery_2month": {
        "name": "경과후기 (2개월)",
        "timing": "수술 후 2개월 (8주차)",
        "structure": [
            "현재시점 (10%): 2개월이 됐다는 언급",
            "변화과정 (25%): 1개월 대비 어떻게 달라졌는지",
            "자연스러움 (30%): 얼마나 자연스러워졌는지 (핵심)",
            "일상복귀 (20%): 일상생활 어떤지",
            "만족도 (15%): 현재 만족도와 앞으로"
        ],
        "must_include": [
            "2개월 시점 명시",
            "1개월 대비 변화",
            "자연스러움",
            "일상 복귀",
            "만족도"
        ],
        "expressions": [
            "어느덧 2개월",
            "확실히 자리잡은 느낌",
            "1개월 때보다 훨씬",
            "이제 티도 안 나요"
        ],
        "forbidden": [
            "아직 붓기 심함 (2개월에 이상함)",
            "최종 결과 단정",
            "힘든 점 과도하게"
        ],
        "tone": "안정감, 만족, 자신감"
    },
    
    "recovery_3month": {
        "name": "경과후기 (3개월)",
        "timing": "수술 후 3개월 (12주차)",
        "structure": [
            "최종시점 (10%): 드디어 3개월!",
            "전체과정회고 (20%): 처음부터 지금까지 요약",
            "최종결과 (30%): 현재 결과 상세히 (핵심)",
            "만족도총평 (25%): 전체적인 평가",
            "추천 (15%): 다른 사람들에게"
        ],
        "must_include": [
            "3개월 시점 명시",
            "전체 과정 요약",
            "최종 결과",
            "총평",
            "추천 + CTA"
        ],
        "expressions": [
            "드디어 3개월",
            "완전히 자리잡았어요",
            "진짜 하길 잘했어요",
            "고민하시는 분들 추천해요"
        ],
        "forbidden": [
            "불확실한 결과",
            "애매한 만족도",
            "아직 붓기 있음"
        ],
        "tone": "만족, 자부심, 확신, 추천 의지"
    }
}


@dataclass
class ReviewPromptConfig:
    """프롬프트 생성 설정"""
    clinic_data: Dict
    doctor_code: str
    procedure: str
    content_type: str = "procedure"  # 기본값: 시술후기
    content_type_profile: Optional[Dict] = None  # ContentTypeProfile 모델 데이터
    persona: Optional[Dict] = None
    cafe: Optional[Dict] = None
    consultant_name: Optional[str] = None
    custom_instructions: Optional[str] = None


class ReviewPromptBuilder:
    """리뷰 프롬프트 빌더"""
    
    def __init__(self, config: ReviewPromptConfig):
        self.config = config
        self.clinic = config.clinic_data
        self.doctor = self._get_doctor()
        self.price_info = self._get_price_info()
        self.consultant = self._get_consultant()
    
    def _get_doctor(self) -> Optional[Dict]:
        """담당 의료진 정보 가져오기"""
        for doc in self.clinic.get('doctors', []):
            if doc.get('code') == self.config.doctor_code:
                return doc
        return None
    
    def _get_price_info(self) -> Optional[Dict]:
        """시술 가격 정보 가져오기"""
        for price in self.clinic.get('price_list', []):
            if (price.get('doctor_code') == self.config.doctor_code and 
                price.get('procedure') == self.config.procedure):
                return price
        return None
    
    def _get_consultant(self) -> Optional[Dict]:
        """상담실장 정보 가져오기"""
        if not self.config.consultant_name:
            # 첫 번째 실장 반환
            consultants = self.clinic.get('consultants', [])
            return consultants[0] if consultants else None
        
        for cons in self.clinic.get('consultants', []):
            if cons.get('name') == self.config.consultant_name:
                return cons
        return None
    
    def build(self) -> str:
        """전체 프롬프트 생성"""
        sections = [
            self._build_header(),
            self._build_content_type_section(),  # 컨텐츠 유형 가이드 추가
            self._build_persona_section(),
            self._build_cafe_section(),
            self._build_clinic_section(),
            self._build_doctor_section(),
            self._build_procedure_section(),
            self._build_process_section(),
            self._build_aftercare_section(),
            self._build_restrictions_section(),
            self._build_guidelines_section(),
        ]
        
        if self.config.custom_instructions:
            sections.append(self._build_custom_section())
        
        return "\n".join(filter(None, sections))
    
    def _build_header(self) -> str:
        ctp = self.config.content_type_profile  # ContentTypeProfile 데이터

        header = """당신은 실제로 시술을 받았거나 받을 환자로서 자연스러운 시술후기, 경험, 상담후기, 질문글들을 작성합니다.
광고가 아닌 진짜 의견과 사실, 경험담처럼 작성해주세요."""

        # ContentTypeProfile이 있으면 해당 데이터 사용
        if ctp:
            name = ctp.get('label', '')
            tone = ctp.get('tone', '')
            emotion = ctp.get('emotion_tone', '')
            purpose = ctp.get('content_purpose', '')

            # 감정 톤 매핑
            emotion_map = {
                'expectation': '기대', 'worry': '걱정', 'nervous': '긴장',
                'excited': '설렘', 'satisfied': '만족', 'regret': '아쉬움',
                'disappointed': '후회'
            }
            emotion_text = emotion_map.get(emotion, emotion)

            # 목적 매핑
            purpose_map = {
                'info': '정보제공', 'review': '후기공유', 'recommend_request': '추천요청',
                'question': '질문', 'experience': '경험담'
            }
            purpose_text = purpose_map.get(purpose, purpose)

            tone_display = tone if tone else emotion_text

            if name:
                header += f"\n\n📌 작성할 컨텐츠 유형: {name}"
            if purpose_text:
                header += f"\n📌 컨텐츠 목적: {purpose_text}"
            if tone_display:
                header += f"\n📌 전체 톤: {tone_display}"

        return header
    
    def _build_content_type_section(self) -> str:
        """컨텐츠 유형별 가이드 섹션"""
        ctp = self.config.content_type_profile  # ContentTypeProfile 데이터

        # ContentTypeProfile이 없으면 섹션 생략
        if not ctp:
            return ""

        name = ctp.get('label', '')
        core_message = ctp.get('core_message', '')
        cta_type = ctp.get('cta_type', '')

        # 글 구조
        structure = ctp.get('structure', [])
        if isinstance(structure, list) and structure:
            structure_text = "\n".join([f"  {i+1}. {s}" for i, s in enumerate(structure)])
        else:
            structure_text = ""

        # 필수 섹션
        required_sections = ctp.get('required_sections', [])
        if isinstance(required_sections, list) and required_sections:
            must_text = "\n".join([f"  ✅ {m}" for m in required_sections])
        else:
            must_text = ""

        # 자주 쓰는 표현
        common_expressions = ctp.get('common_expressions', [])
        opening_patterns = ctp.get('opening_patterns', [])
        closing_patterns = ctp.get('closing_patterns', [])
        all_expressions = []
        if isinstance(common_expressions, list):
            all_expressions.extend(common_expressions[:3])
        if isinstance(opening_patterns, list):
            all_expressions.extend(opening_patterns[:2])
        if isinstance(closing_patterns, list):
            all_expressions.extend(closing_patterns[:2])
        if all_expressions:
            expr_text = "\n".join([f"  - \"{e}\"" for e in all_expressions])
        else:
            expr_text = ""

        # 금지 요소
        forbidden_elements = ctp.get('forbidden_elements', [])
        if isinstance(forbidden_elements, list) and forbidden_elements:
            forbidden_text = "\n".join([f"  ❌ {f}" for f in forbidden_elements])
        else:
            forbidden_text = ""

        # 권장 요소
        recommended_elements = ctp.get('recommended_elements', [])
        if isinstance(recommended_elements, list) and recommended_elements:
            recommended_text = "\n".join([f"  ⭐ {r}" for r in recommended_elements])
        else:
            recommended_text = ""

        # CTA 매핑
        cta_map = {
            'comment': '댓글 유도', 'share': '공유 유도',
            'inquiry': '병원 문의 유도', 'none': '없음'
        }
        cta_display = cta_map.get(cta_type, '')

        # 타입별 세부 설정
        type_settings = ctp.get('type_settings', {})
        settings_text = ""
        if isinstance(type_settings, dict) and type_settings:
            settings_lines = []
            for key, val in type_settings.items():
                if val:
                    if isinstance(val, list):
                        val = ', '.join(str(v) for v in val[:5])
                    settings_lines.append(f"  - {key}: {val}")
            if settings_lines:
                settings_text = "\n📝 세부 설정:\n" + "\n".join(settings_lines[:10])

        # 글자수 제한
        min_len = ctp.get('min_length', 400)
        max_len = ctp.get('max_length', 1200)

        result = f"""
═══════════════════════════════════════════════════════════════
📋 컨텐츠 유형: {name}
═══════════════════════════════════════════════════════════════
"""
        if core_message:
            result += f"\n💡 핵심 메시지: {core_message}\n"

        result += f"\n📏 글자수: {min_len}~{max_len}자\n"

        if structure_text:
            result += f"\n🏗️ 글 구조:\n{structure_text}\n"

        if must_text:
            result += f"\n✅ 필수 포함 요소:\n{must_text}\n"

        if recommended_text:
            result += f"\n⭐ 권장 요소:\n{recommended_text}\n"

        if expr_text:
            result += f"\n💬 표현 예시:\n{expr_text}\n"

        if forbidden_text:
            result += f"\n❌ 피해야 할 것:\n{forbidden_text}\n"

        if cta_display and cta_display != '없음':
            result += f"\n🎯 CTA: {cta_display}\n"

        if settings_text:
            result += settings_text

        return result
    
    def _build_persona_section(self) -> str:
        persona = self.config.persona
        if not persona:
            return ""

        # 이모지 사용 레벨 매핑
        emoji_map = {'many': '많이 사용', 'moderate': '적당히 사용', 'rarely': '거의 안함'}
        emoji_text = emoji_map.get(persona.get('emoji_usage', ''), '')

        # 경험 레벨 매핑
        exp_map = {'first': '첫시술', 'few': '2~3회차', 'many': '5회이상', 'regular': '단골'}
        exp_text = exp_map.get(persona.get('experience_level', ''), '')

        # 자주 쓰는 표현
        expressions = persona.get('frequent_expressions', [])
        if isinstance(expressions, list):
            phrases = ', '.join(expressions[:3]) if expressions else ''
        elif isinstance(expressions, str):
            phrases = expressions
        else:
            phrases = ''

        name = persona.get('name', '')
        age_group = persona.get('age_group', '')
        gender = persona.get('gender', '')
        speech_style = persona.get('speech_style', '')
        intro = persona.get('intro_expression', '')
        conclusion = persona.get('conclusion_expression', '')

        result = """
═══════════════════════════════════════════════════════════════
👤 작성자 페르소나
═══════════════════════════════════════════════════════════════
"""
        if name or age_group or gender:
            setting_parts = [name, f"({age_group} {gender})".strip() if age_group or gender else '']
            result += f"- 설정: {' '.join(filter(None, setting_parts))}\n"
        if speech_style:
            result += f"- 말투: {speech_style}\n"
        if exp_text:
            result += f"- 경험: {exp_text}\n"
        if emoji_text:
            result += f"- 이모지: {emoji_text}\n"
        if intro:
            result += f"- 인트로: {intro}\n"
        if conclusion:
            result += f"- 결론: {conclusion}\n"
        if phrases:
            result += f"- 자주 쓰는 표현: {phrases}\n"

        return result
    
    def _build_cafe_section(self) -> str:
        cafe = self.config.cafe
        if not cafe:
            return ""

        # 필수/금지 요소
        required_raw = cafe.get('required_elements', [])
        if isinstance(required_raw, list):
            required = ', '.join(required_raw)
        elif isinstance(required_raw, str):
            required = required_raw
        else:
            required = ''

        forbidden_raw = cafe.get('forbidden_keywords', [])
        if isinstance(forbidden_raw, list):
            forbidden = ', '.join(forbidden_raw)
        elif isinstance(forbidden_raw, str):
            forbidden = forbidden_raw
        else:
            forbidden = ''

        # 카페 성격 매핑
        char_map = {'info_share': '정보공유형', 'chat': '수다형', 'expert': '전문가형', 'qna': 'Q&A형'}
        character = char_map.get(cafe.get('cafe_character', ''), '')

        # 광고 규제 수준 매핑
        ad_map = {'strict': '엄격', 'normal': '보통', 'loose': '느슨'}
        ad_level = ad_map.get(cafe.get('ad_restriction', ''), '')

        # 병원명 공개 매핑
        hospital_map = {'allowed': '가능', 'initial_only': '이니셜만', 'forbidden': '불가'}
        hospital_disclosure = hospital_map.get(cafe.get('hospital_name_disclosure', ''), '')

        name = cafe.get('name', '')
        min_len = cafe.get('min_length')
        max_len = cafe.get('max_length')
        tips = cafe.get('tips', '')

        result = f"""
═══════════════════════════════════════════════════════════════
📝 타겟 카페: {name}
═══════════════════════════════════════════════════════════════
"""
        if character:
            result += f"- 성격: {character}\n"
        if min_len and max_len:
            result += f"- 글 길이: {min_len}~{max_len}자\n"
        if ad_level or hospital_disclosure:
            parts = []
            if ad_level:
                parts.append(f"광고규제: {ad_level}")
            if hospital_disclosure:
                parts.append(f"병원명: {hospital_disclosure}")
            result += f"- {' / '.join(parts)}\n"
        if required:
            result += f"- 필수 요소: {required}\n"
        if forbidden:
            result += f"- 금지 단어: {forbidden}\n"
        if tips:
            result += f"- 팁: {tips}\n"

        return result
    
    def _build_clinic_section(self) -> str:
        basic = self.clinic.get('basic_info', {})
        if not isinstance(basic, dict):
            basic = {}

        features = self.clinic.get('features', {})
        if not isinstance(features, dict):
            features = {}

        feature_list = []
        if features.get('cctv'):
            feature_list.append(f"CCTV: {features['cctv']}")
        if features.get('anesthesia'):
            feature_list.append(f"마취: {features['anesthesia']}")
        if features.get('real_name'):
            feature_list.append("수술 실명제")

        features_text = ', '.join(feature_list) if feature_list else ''

        return f"""
═══════════════════════════════════════════════════════════════
🏥 병원 정보
═══════════════════════════════════════════════════════════════
- 위치: {basic.get('location', self.clinic.get('location', ''))}
- 운영시간: {basic.get('hours', self.clinic.get('hours', ''))}
- 주차: {basic.get('parking', self.clinic.get('parking', ''))}
{f'- 특징: {features_text}' if features_text else ''}"""
    
    def _build_doctor_section(self) -> str:
        if not self.doctor or not isinstance(self.doctor, dict):
            return ""

        specialties_raw = self.doctor.get('specialties', [])
        if isinstance(specialties_raw, list):
            specialties = ', '.join(specialties_raw[:5])
        elif isinstance(specialties_raw, str):
            specialties = specialties_raw
        else:
            specialties = ''

        basic_info = self.clinic.get('basic_info', {})
        if not isinstance(basic_info, dict):
            basic_info = {}
        consultation_time = basic_info.get('consultation_time', '')

        return f"""
═══════════════════════════════════════════════════════════════
👨‍⚕️ 담당 원장님
═══════════════════════════════════════════════════════════════
- 원장님: {self.doctor.get('name', '')} 원장님 ({self.doctor.get('code', '')})
- 상담 스타일: {self.doctor.get('style', '')}
{f'- 주력 시술: {specialties}' if specialties else ''}
{f'- 상담 시간: {consultation_time}' if consultation_time else ''}"""
    
    def _build_procedure_section(self) -> str:
        procedure = self.config.procedure or ""
        price_display = ""

        if self.price_info:
            price_display = self.price_info.get('price_display', self.price_info.get('price', ''))

        # 사후관리 정보
        aftercare = self.clinic.get('aftercare', {})
        aftercare_text = ""
        if isinstance(aftercare, dict):
            for key, value in aftercare.items():
                if procedure and (procedure in key or key in procedure):
                    aftercare_text = value
                    break
        elif isinstance(aftercare, str):
            aftercare_text = aftercare

        return f"""
═══════════════════════════════════════════════════════════════
💉 시술 정보
═══════════════════════════════════════════════════════════════
- 시술명: {procedure}
{f'- 가격대: {price_display}' if price_display else ''}
{f'- 사후관리: {aftercare_text}' if aftercare_text else ''}"""
    
    def _build_process_section(self) -> str:
        process = self.clinic.get('process', '')

        # process가 dict인 경우 문자열로 변환
        if isinstance(process, dict):
            process_parts = []
            for k, v in process.items():
                if v:
                    process_parts.append(f"{k}: {v}")
            process = '\n'.join(process_parts)
        elif not isinstance(process, str):
            process = str(process) if process else ''

        if not process:
            return ""

        # 실장 정보 추가
        consultant_text = ""
        if self.consultant and isinstance(self.consultant, dict):
            consultant_text = f"\n- 상담실장: {self.consultant.get('name', '')}님 ({self.consultant.get('style', '')})"

        return f"""
═══════════════════════════════════════════════════════════════
🔄 상담 프로세스
═══════════════════════════════════════════════════════════════
{process}{consultant_text}"""
    
    def _build_aftercare_section(self) -> str:
        post_care = self.clinic.get('post_care', {})

        # 해당 시술 관련 주의사항 찾기
        relevant_care = ""
        procedure = self.config.procedure or ""

        if isinstance(post_care, dict) and procedure:
            for surgery_type, care_text in post_care.items():
                if (surgery_type in procedure or
                    procedure in surgery_type or
                    ('코' in surgery_type and '코' in procedure) or
                    ('눈' in surgery_type and '눈' in procedure) or
                    ('지방' in surgery_type and ('얼지' in procedure or '지방' in procedure))):
                    # 첫 3-4줄만
                    if isinstance(care_text, str):
                        lines = care_text.split('\n')[:4]
                        relevant_care = '\n'.join(lines)
                    break
        elif isinstance(post_care, str):
            lines = post_care.split('\n')[:4]
            relevant_care = '\n'.join(lines)

        if not relevant_care:
            return ""

        return f"""
═══════════════════════════════════════════════════════════════
📋 수술 후 정보 (참고용, 일부만 자연스럽게 언급)
═══════════════════════════════════════════════════════════════
{relevant_care}"""
    
    def _build_restrictions_section(self) -> str:
        blocked = self.clinic.get('blocked_hospitals', [])
        allowed = self.clinic.get('allowed_hospitals', {})

        blocked_text = ''
        if isinstance(blocked, list):
            blocked_text = ', '.join(blocked) if blocked else ''
        elif isinstance(blocked, str):
            blocked_text = blocked

        # 해당 시술 관련 언급 가능 병원
        allowed_text = ""
        procedure = self.config.procedure or ""
        if isinstance(allowed, dict) and procedure:
            for category, hospitals in allowed.items():
                if category in procedure or procedure in category:
                    if isinstance(hospitals, list):
                        allowed_text = ', '.join(hospitals[:3])
                    break
        elif isinstance(allowed, list):
            allowed_text = ', '.join(allowed[:3]) if allowed else ''
        elif isinstance(allowed, str):
            allowed_text = allowed

        if not blocked_text and not allowed_text:
            return ""

        return f"""
═══════════════════════════════════════════════════════════════
⚠️ 언급 제한
═══════════════════════════════════════════════════════════════
{f'- 언급 금지 병원: {blocked_text}' if blocked_text else ''}
{f'- 비교 언급 가능: {allowed_text}' if allowed_text else ''}"""
    
    def _build_guidelines_section(self) -> str:
        return """
═══════════════════════════════════════════════════════════════
✍️ 작성 가이드라인
═══════════════════════════════════════════════════════════════
1. 위 정보를 바탕으로 실제 경험한 것처럼 자연스럽게 작성
2. 모든 정보를 다 넣지 말고, 자연스럽게 일부만 선택적으로 언급
3. 광고처럼 보이지 않도록 솔직한 톤 유지
4. 작은 불편함도 언급하면 더 신뢰감 있음 (예: 대기시간, 주차 불편 등)
5. 금지 단어는 절대 사용하지 않기
6. 과장된 표현 ("최고", "완전 강추", "인생병원") 자제
7. 구체적인 경험과 감정 위주로 작성"""
    
    def _build_custom_section(self) -> str:
        return f"""
═══════════════════════════════════════════════════════════════
📌 추가 지시사항
═══════════════════════════════════════════════════════════════
{self.config.custom_instructions}"""


def build_review_prompt(
    clinic_data: Dict,
    doctor_code: str,
    procedure: str,
    content_type: str = "procedure",  # 컨텐츠 유형 추가
    content_type_profile: Optional[Dict] = None,  # ContentTypeProfile 데이터
    persona: Optional[Dict] = None,
    cafe: Optional[Dict] = None,
    consultant_name: Optional[str] = None,
    custom_instructions: Optional[str] = None
) -> str:
    """
    리뷰 생성 프롬프트 빌드 (편의 함수)

    Args:
        clinic_data: 파싱된 병원 데이터
        doctor_code: 담당 의료진 코드 (예: "Dr.H")
        procedure: 시술명
        content_type: 컨텐츠 유형
        content_type_profile: ContentTypeProfile 데이터 (dict)
        persona: 페르소나 설정 (dict 또는 Persona 모델)
        cafe: 카페 설정 (dict 또는 CafeProfile 모델)
        consultant_name: 상담실장 이름 (선택)
        custom_instructions: 추가 지시사항 (선택)

    Returns:
        생성된 프롬프트 문자열
    """
    # Django 모델인 경우 dict로 변환
    if persona and hasattr(persona, '__dict__') and hasattr(persona, 'name'):
        # 말투 스타일 조합
        speech_style_parts = []
        if hasattr(persona, 'honorific_level'):
            honorific_map = {'formal': '존댓말', 'informal': '반말', 'mixed': '혼용'}
            speech_style_parts.append(honorific_map.get(persona.honorific_level, ''))
        if hasattr(persona, 'sentence_ending'):
            ending_map = {'yo': '~요체', 'yong': '~용체', 'dang': '~당체', 'eum': '~음체', 'mixed': '혼용'}
            speech_style_parts.append(ending_map.get(persona.sentence_ending, ''))

        persona = {
            'name': persona.name,
            'age_group': getattr(persona, 'age_group', ''),
            'gender': getattr(persona, 'gender', ''),
            'occupation': getattr(persona, 'occupation', ''),
            'region': getattr(persona, 'region', ''),
            # 말투 스타일
            'speech_style': ', '.join(filter(None, speech_style_parts)),
            'honorific_level': getattr(persona, 'honorific_level', 'formal'),
            'exclamation_freq': getattr(persona, 'exclamation_freq', 'medium'),
            'emoji_usage': getattr(persona, 'emoji_usage', 'moderate'),
            'sentence_ending': getattr(persona, 'sentence_ending', 'yo'),
            'sentence_length': getattr(persona, 'sentence_length', 'medium'),
            # 시술 경험
            'experience_level': getattr(persona, 'experience_level', 'first'),
            'fear_level': getattr(persona, 'fear_level', 'normal'),
            'price_sensitivity': getattr(persona, 'price_sensitivity', 'medium'),
            # 표현 라이브러리
            'intro_expression': getattr(persona, 'intro_expression', ''),
            'transition_expression': getattr(persona, 'transition_expression', ''),
            'conclusion_expression': getattr(persona, 'conclusion_expression', ''),
            'recommend_expression': getattr(persona, 'recommend_expression', ''),
            'frequent_expressions': getattr(persona, 'frequent_expressions', []),
            # 신뢰 요소
            'own_money_emphasis': getattr(persona, 'own_money_emphasis', 'always'),
            'cons_mention_style': getattr(persona, 'cons_mention_style', 'medium'),
            'cons_examples': getattr(persona, 'cons_examples', []),
            'comparison_mention': getattr(persona, 'comparison_mention', True),
            'choice_reason': getattr(persona, 'choice_reason', []),
        }

    if cafe and hasattr(cafe, '__dict__') and hasattr(cafe, 'name'):
        cafe = {
            'name': cafe.name,
            'platform_type': getattr(cafe, 'platform_type', 'cafe'),
            'cafe_character': getattr(cafe, 'cafe_character', 'info_share'),
            'board_type': getattr(cafe, 'board_type', 'review'),
            # 글 형식
            'length_range': getattr(cafe, 'length_range', '800_1500'),
            'min_length': cafe.min_length,  # property
            'max_length': cafe.max_length,  # property
            'required_elements': getattr(cafe, 'required_elements', []),
            'subtitle_style': getattr(cafe, 'subtitle_style', 'square'),
            'paragraph_style': getattr(cafe, 'paragraph_style', 'medium'),
            'photo_mention': getattr(cafe, 'photo_mention', 'full'),
            # 상호작용
            'question_inducement': getattr(cafe, 'question_inducement', ''),
            'info_request': getattr(cafe, 'info_request', ''),
            'reply_style': getattr(cafe, 'reply_style', 'kind_detailed'),
            # 카페 규칙
            'ad_restriction': getattr(cafe, 'ad_restriction', 'strict'),
            'hospital_name_disclosure': getattr(cafe, 'hospital_name_disclosure', 'allowed'),
            'price_disclosure': getattr(cafe, 'price_disclosure', 'range_only'),
            'photo_required': getattr(cafe, 'photo_required', 'recommended'),
            # SEO/노출
            'title_prefix': getattr(cafe, 'title_prefix', 'none'),
            'hashtag_count': getattr(cafe, 'hashtag_count', '5_10'),
            'required_keywords': getattr(cafe, 'required_keywords', []),
            'forbidden_keywords': getattr(cafe, 'forbidden_keywords', []),
            # 대상
            'target_reader': getattr(cafe, 'target_reader', 'beginner'),
            # 기존 호환
            'tips': getattr(cafe, 'tips', ''),
        }
    
    config = ReviewPromptConfig(
        clinic_data=clinic_data,
        doctor_code=doctor_code,
        procedure=procedure,
        content_type=content_type,  # 컨텐츠 유형 전달
        content_type_profile=content_type_profile,  # ContentTypeProfile 데이터 전달
        persona=persona,
        cafe=cafe,
        consultant_name=consultant_name,
        custom_instructions=custom_instructions,
    )

    builder = ReviewPromptBuilder(config)
    return builder.build()


def build_prompt_from_models(
    clinic,  # ClinicGuide model
    doctor_code: str,
    procedure: str,
    content_type: str = "procedure",  # 컨텐츠 유형 추가
    content_type_profile=None,  # ContentTypeProfile model
    persona=None,  # Persona model
    cafe=None,  # CafeProfile model
    consultant_name: Optional[str] = None,
    custom_instructions: Optional[str] = None
) -> str:
    """
    Django 모델에서 직접 프롬프트 빌드

    Args:
        clinic: ClinicGuide 모델 인스턴스
        doctor_code: 담당 의료진 코드
        procedure: 시술명
        content_type: 컨텐츠 유형 (consultation, procedure, recovery_1month, recovery_2month, recovery_3month)
        content_type_profile: ContentTypeProfile 모델 인스턴스 (선택)
        persona: Persona 모델 인스턴스 (선택)
        cafe: CafeProfile 모델 인스턴스 (선택)
        consultant_name: 상담실장 이름 (선택)
        custom_instructions: 추가 지시사항 (선택)

    Returns:
        생성된 프롬프트 문자열
    """
    # ClinicGuide를 dict로 변환 (None인 경우 빈 데이터 사용)
    if clinic:
        clinic_data = {
            'basic_info': {
                'location': clinic.location,
                'hours': clinic.hours,
                'parking': clinic.parking,
            },
            'doctors': clinic.doctors,
            'consultants': clinic.consultants,
            'price_list': clinic.price_list,
            'process': clinic.process,
            'aftercare': clinic.aftercare,
            'post_care': clinic.post_care,
            'features': clinic.features,
            'allowed_hospitals': clinic.allowed_hospitals,
            'blocked_hospitals': clinic.blocked_hospitals,
        }
    else:
        # clinic이 None인 경우 기본 빈 데이터
        clinic_data = {
            'basic_info': {},
            'doctors': [],
            'consultants': [],
            'price_list': [],
            'process': {},
            'aftercare': {},
            'post_care': {},
            'features': {},
            'allowed_hospitals': [],
            'blocked_hospitals': [],
        }
    
    # ContentTypeProfile을 dict로 변환
    content_type_data = None
    if content_type_profile and hasattr(content_type_profile, '__dict__') and hasattr(content_type_profile, 'value'):
        # get_type_settings 메서드로 세부 설정 가져오기
        type_settings = {}
        if hasattr(content_type_profile, 'get_type_settings'):
            type_settings = content_type_profile.get_type_settings() or {}

        content_type_data = {
            'value': content_type_profile.value,
            'label': content_type_profile.label,
            'description': getattr(content_type_profile, 'description', ''),
            # 공통 셋팅
            'content_purpose': getattr(content_type_profile, 'content_purpose', 'review'),
            'core_message': getattr(content_type_profile, 'core_message', ''),
            'emotion_tone': getattr(content_type_profile, 'emotion_tone', 'satisfied'),
            'cta_type': getattr(content_type_profile, 'cta_type', 'comment'),
            # 구조
            'structure': getattr(content_type_profile, 'structure', []),
            'required_sections': getattr(content_type_profile, 'required_sections', []),
            # 표현
            'common_expressions': getattr(content_type_profile, 'common_expressions', []),
            'opening_patterns': getattr(content_type_profile, 'opening_patterns', []),
            'closing_patterns': getattr(content_type_profile, 'closing_patterns', []),
            # 금지/권장
            'forbidden_elements': getattr(content_type_profile, 'forbidden_elements', []),
            'recommended_elements': getattr(content_type_profile, 'recommended_elements', []),
            # 톤/감정
            'tone': getattr(content_type_profile, 'tone', ''),
            'emotion_flow': getattr(content_type_profile, 'emotion_flow', []),
            # 글자수
            'min_length': getattr(content_type_profile, 'min_length', 400),
            'max_length': getattr(content_type_profile, 'max_length', 1200),
            # 기타
            'image_required': getattr(content_type_profile, 'image_required', False),
            'tips': getattr(content_type_profile, 'tips', ''),
            # 타입별 세부 설정
            'type_settings': type_settings,
        }

    return build_review_prompt(
        clinic_data=clinic_data,
        doctor_code=doctor_code,
        procedure=procedure,
        content_type=content_type,  # 컨텐츠 유형 전달
        content_type_profile=content_type_data,  # ContentTypeProfile 데이터 전달
        persona=persona,
        cafe=cafe,
        consultant_name=consultant_name,
        custom_instructions=custom_instructions,
    )
