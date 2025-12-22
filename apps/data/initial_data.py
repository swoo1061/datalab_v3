"""
초기 데이터: 페르소나, 카페, 컨텐츠 유형 프리셋
presetss.txt 기반 144개 항목 전체 반영

Django shell이나 management command로 실행:
    python manage.py shell < apps/data/initial_data.py
"""

# =====================================================
# 페르소나 프리셋 (26개 항목)
# =====================================================

PERSONA_PRESETS = [
    {
        # 기본 신원
        "name": "하윤쓰",
        "age_group": "20_late",
        "gender": "female",
        "occupation": "office",
        "region": "seoul",
        # 말투 스타일
        "honorific_level": "formal",
        "exclamation_freq": "high",
        "emoji_usage": "many",
        "sentence_ending": "yo",
        "sentence_length": "medium",
        # 시술 경험
        "experience_level": "first",
        "fear_level": "very_scared",
        "price_sensitivity": "high",
        "skin_concerns": ["기미", "잡티"],
        "skin_type": "combination",
        # 표현 라이브러리
        "intro_expression": "솔직히 처음엔 걱정했는데",
        "transition_expression": "아무튼!",
        "conclusion_expression": "결론은 대만족이에요!",
        "recommend_expression": "저처럼 겁많은 분들도 괜찮을 거예요",
        "frequent_expressions": ["고민하시는 분들 참고하세요", "진짜 후회 안 해요", "대박"],
        # 신뢰 요소
        "own_money_emphasis": "always",
        "cons_mention_style": "medium",
        "cons_examples": ["대기 시간이 좀 있어요", "주차가 조금 불편"],
        "comparison_mention": True,
        "choice_reason": ["후기 보고", "가격", "위치"],
        # 메타
        "description": "20대 후반 직장인, 첫 시술 도전, 꼼꼼하게 비교하는 스타일",
    },
    {
        "name": "뷰티로그",
        "age_group": "30_early",
        "gender": "female",
        "occupation": "housewife",
        "region": "gyeonggi",
        "honorific_level": "formal",
        "exclamation_freq": "medium",
        "emoji_usage": "moderate",
        "sentence_ending": "yo",
        "sentence_length": "long",
        "experience_level": "few",
        "fear_level": "little",
        "price_sensitivity": "medium",
        "skin_concerns": ["주름", "탄력"],
        "skin_type": "dry",
        "intro_expression": "애 낳고 나서 처음으로",
        "transition_expression": "그래서요",
        "conclusion_expression": "육아맘들 참고하시면 좋을 것 같아요",
        "recommend_expression": "시간 내기 어려운 분들께 추천",
        "frequent_expressions": ["남편 몰래 상담받고 왔어요", "드디어 자기관리", "추천이요"],
        "own_money_emphasis": "always",
        "cons_mention_style": "weak",
        "cons_examples": ["아이 맡기고 가야 해서 시간 맞추기 힘들어요"],
        "comparison_mention": True,
        "choice_reason": ["지인추천", "위치", "원장경력"],
        "description": "30대 초반 주부, 육아하면서 자기관리 시작, 신중하고 꼼꼼함",
    },
    {
        "name": "성형일기",
        "age_group": "30_late",
        "gender": "female",
        "occupation": "office",
        "region": "seoul",
        "honorific_level": "formal",
        "exclamation_freq": "low",
        "emoji_usage": "rarely",
        "sentence_ending": "yo",
        "sentence_length": "short",
        "experience_level": "many",
        "fear_level": "brave",
        "price_sensitivity": "low",
        "skin_concerns": ["모공", "탄력", "턱선"],
        "skin_type": "oily",
        "intro_expression": "바쁜 직장인으로서",
        "transition_expression": "결론적으로",
        "conclusion_expression": "시간 대비 만족도 높았어요",
        "recommend_expression": "효율적으로 받을 수 있어서",
        "frequent_expressions": ["회복기간이 짧아서 다행", "핵심만 정리하면", "추천"],
        "own_money_emphasis": "sometimes",
        "cons_mention_style": "strong",
        "cons_examples": ["가격이 좀 있어요", "예약이 빡빡해요"],
        "comparison_mention": True,
        "choice_reason": ["원장경력", "후기", "위치"],
        "description": "30대 후반 커리어우먼, 바쁜 일정 속 효율적인 관리 추구, 전문적인 시각",
    },
    {
        "name": "예쁨이되고파",
        "age_group": "20_early",
        "gender": "female",
        "occupation": "student",
        "region": "seoul",
        "honorific_level": "mixed",
        "exclamation_freq": "high",
        "emoji_usage": "many",
        "sentence_ending": "yong",
        "sentence_length": "short",
        "experience_level": "first",
        "fear_level": "very_scared",
        "price_sensitivity": "high",
        "skin_concerns": ["잡티", "모공"],
        "skin_type": "oily",
        "intro_expression": "친구가 여기서 했는데 너무 자연스러워서",
        "transition_expression": "근데요!",
        "conclusion_expression": "학생 할인 있어서 좋았어용",
        "recommend_expression": "방학 때 하면 딱이에요",
        "frequent_expressions": ["대박 대박", "진짜 자연스러움", "완전 추천"],
        "own_money_emphasis": "always",
        "cons_mention_style": "weak",
        "cons_examples": ["대학생이라 가격 부담됐는데"],
        "comparison_mention": False,
        "choice_reason": ["지인추천", "가격"],
        "description": "20대 초반 대학생, 처음 시술 도전, 친구 추천으로 방문",
    },
    {
        "name": "비즈니스맨K",
        "age_group": "40_plus",
        "gender": "male",
        "occupation": "self_employed",
        "region": "seoul",
        "honorific_level": "formal",
        "exclamation_freq": "low",
        "emoji_usage": "rarely",
        "sentence_ending": "yo",
        "sentence_length": "short",
        "experience_level": "few",
        "fear_level": "brave",
        "price_sensitivity": "low",
        "skin_concerns": ["주름", "탄력"],
        "skin_type": "combination",
        "intro_expression": "남자도 관리가 필요한 시대",
        "transition_expression": "결론은",
        "conclusion_expression": "자연스러운 변화를 원했습니다",
        "recommend_expression": "비즈니스 미팅이 많아서",
        "frequent_expressions": ["주변에서 못 알아볼 정도", "자연스럽게", "만족"],
        "own_money_emphasis": "never",
        "cons_mention_style": "weak",
        "cons_examples": [],
        "comparison_mention": False,
        "choice_reason": ["원장경력", "후기"],
        "description": "40대 남성, 비즈니스 이미지 관리, 간결하고 실용적",
    },
    {
        "name": "인스타그래머_지니",
        "age_group": "20_mid",
        "gender": "female",
        "occupation": "freelancer",
        "region": "seoul",
        "honorific_level": "informal",
        "exclamation_freq": "high",
        "emoji_usage": "many",
        "sentence_ending": "eum",
        "sentence_length": "short",
        "experience_level": "many",
        "fear_level": "normal",
        "price_sensitivity": "medium",
        "skin_concerns": ["잡티", "탄력", "코"],
        "skin_type": "combination",
        "intro_expression": "인스타 보고 찾아갔는데",
        "transition_expression": "아 그리고",
        "conclusion_expression": "사진빨 아니고 진짜임",
        "recommend_expression": "틱톡에서 핫한 그 시술",
        "frequent_expressions": ["브이로그 찍어도 될 정도", "인생샷", "핫플"],
        "own_money_emphasis": "always",
        "cons_mention_style": "medium",
        "cons_examples": ["사람 많음", "예약 빡빡"],
        "comparison_mention": True,
        "choice_reason": ["후기", "가격"],
        "description": "20대 중반 인플루언서 지망, SNS 활동 많음, 트렌디하고 감각적",
    },
]


# =====================================================
# 카페 프리셋 (21개 항목)
# =====================================================

CAFE_PRESETS = [
    {
        # 플랫폼 정보
        "platform_type": "cafe",
        "name": "성형시술정보",
        "cafe_character": "info_share",
        "board_type": "review",
        # 글 형식
        "length_range": "800_1500",
        "required_elements": ["제목", "본문", "사진설명"],
        "subtitle_style": "square",
        "paragraph_style": "medium",
        "photo_mention": "full",
        # 상호작용
        "question_inducement": "혹시 해보신 분 계세요?",
        "info_request": "궁금한 거 댓글로 물어봐 주세요",
        "reply_style": "kind_detailed",
        # 카페 규칙
        "ad_restriction": "strict",
        "hospital_name_disclosure": "allowed",
        "price_disclosure": "range_only",
        "photo_required": "recommended",
        # SEO/노출
        "title_prefix": "review",
        "hashtag_count": "none",
        "required_keywords": ["시술명", "병원명", "후기"],
        "forbidden_keywords": ["협찬", "광고", "제공", "원고료", "최고", "완전 강추"],
        # 대상 설정
        "target_reader": "beginner",
        # 기타
        "url": "",
        "tips": "다른 병원과 비교한 내용 있으면 신뢰도 상승, 가격 언급 시 대략적인 범위로",
    },
    {
        "platform_type": "cafe",
        "name": "강남맘카페",
        "cafe_character": "chat",
        "board_type": "free",
        "length_range": "300_800",
        "required_elements": ["제목", "본문"],
        "subtitle_style": "none",
        "paragraph_style": "short",
        "photo_mention": "partial",
        "question_inducement": "",
        "info_request": "",
        "reply_style": "kind_detailed",
        "ad_restriction": "strict",
        "hospital_name_disclosure": "initial_only",
        "price_disclosure": "range_only",
        "photo_required": "optional",
        "title_prefix": "none",
        "hashtag_count": "none",
        "required_keywords": ["동네", "근처"],
        "forbidden_keywords": ["광고", "협찬", "최고", "무조건", "찐추천"],
        "target_reader": "beginner",
        "url": "",
        "tips": "동네 엄마들한테 공유하는 느낌으로, 너무 상세한 시술 정보보다는 경험 위주",
    },
    {
        "platform_type": "cafe",
        "name": "피부시술러",
        "cafe_character": "expert",
        "board_type": "review",
        "length_range": "1500_3000",
        "required_elements": ["제목", "본문", "사진설명", "해시태그"],
        "subtitle_style": "arrow",
        "paragraph_style": "medium",
        "photo_mention": "full",
        "question_inducement": "궁금한 점 있으시면 댓글 주세요",
        "info_request": "자세한 후기 필요하시면 말씀해 주세요",
        "reply_style": "kind_detailed",
        "ad_restriction": "strict",
        "hospital_name_disclosure": "allowed",
        "price_disclosure": "specific",
        "photo_required": "required",
        "title_prefix": "honest",
        "hashtag_count": "5_10",
        "required_keywords": ["시술명", "경과", "회복"],
        "forbidden_keywords": ["광고", "협찬", "최고의", "인생시술"],
        "target_reader": "experienced",
        "url": "",
        "tips": "경과 사진 있으면 신뢰도 높음, 회복 과정 상세히",
    },
    {
        "platform_type": "cafe",
        "name": "직장인수다방",
        "cafe_character": "chat",
        "board_type": "free",
        "length_range": "300_800",
        "required_elements": ["제목", "본문"],
        "subtitle_style": "number",
        "paragraph_style": "short",
        "photo_mention": "none",
        "question_inducement": "",
        "info_request": "",
        "reply_style": "simple",
        "ad_restriction": "normal",
        "hospital_name_disclosure": "allowed",
        "price_disclosure": "range_only",
        "photo_required": "optional",
        "title_prefix": "none",
        "hashtag_count": "none",
        "required_keywords": ["휴가", "회복", "일상복귀"],
        "forbidden_keywords": ["광고", "최고", "무조건"],
        "target_reader": "experienced",
        "url": "",
        "tips": "회복 기간, 멍/붓기 지속 기간 구체적으로, 직장 복귀 타이밍 중요",
    },
    {
        "platform_type": "naver_blog",
        "name": "네이버 블로그 (개인)",
        "cafe_character": "info_share",
        "board_type": "review",
        "length_range": "1500_3000",
        "required_elements": ["제목", "본문", "사진설명", "해시태그"],
        "subtitle_style": "square",
        "paragraph_style": "medium",
        "photo_mention": "full",
        "question_inducement": "",
        "info_request": "궁금하신 점 댓글로 남겨주세요",
        "reply_style": "kind_detailed",
        "ad_restriction": "loose",
        "hospital_name_disclosure": "allowed",
        "price_disclosure": "specific",
        "photo_required": "required",
        "title_prefix": "review",
        "hashtag_count": "10_15",
        "required_keywords": ["시술명", "병원명", "지역명", "후기"],
        "forbidden_keywords": [],
        "target_reader": "beginner",
        "url": "",
        "tips": "SEO 키워드 자연스럽게 포함, 중간중간 소제목 활용",
    },
    {
        "platform_type": "qna",
        "name": "지식인 답변용",
        "cafe_character": "qna",
        "board_type": "question",
        "length_range": "300_800",
        "required_elements": ["본문"],
        "subtitle_style": "none",
        "paragraph_style": "short",
        "photo_mention": "none",
        "question_inducement": "",
        "info_request": "",
        "reply_style": "kind_detailed",
        "ad_restriction": "strict",
        "hospital_name_disclosure": "initial_only",
        "price_disclosure": "range_only",
        "photo_required": "optional",
        "title_prefix": "none",
        "hashtag_count": "none",
        "required_keywords": [],
        "forbidden_keywords": ["광고", "협찬", "홍보"],
        "target_reader": "beginner",
        "url": "",
        "tips": "질문에 대한 답변 형식으로, 경험 기반 조언",
    },
]


# =====================================================
# 컨텐츠 유형 프리셋 (공통 4개 + 타입별 세부 항목)
# =====================================================

CONTENT_TYPE_PRESETS = [
    {
        "value": "recommend_request",
        "label": "1. 추천받기",
        "description": "시술/병원 추천 요청 글",
        "order": 1,
        # 공통 4개
        "content_purpose": "recommend_request",
        "core_message": "어디가 좋을까요?",
        "emotion_tone": "worry",
        "cta_type": "comment",
        # 타입별 세부 설정
        "recommend_settings": {
            "current_concern": "기미가 점점 진해져서",
            "procedure_experience": "first",
            "budget_range": "50만원 이내",
            "preferred_region": "강남쪽",
            "urgency": "천천히",
            "question_type": "시술추천",
            "specific_question": "피코 vs 레이저 뭐가 나을까요?",
            "worry_points": ["통증", "다운타임", "효과"],
            "wanted_info": ["경험담", "가격정보", "추천병원"],
        },
        # 기존 호환
        "structure": [
            "현재 상태/고민 (30%): 어떤 고민이 있는지",
            "시도해본 것 (20%): 지금까지 해본 것들",
            "질문 (30%): 구체적인 질문",
            "조건 (20%): 예산, 지역 등 조건",
        ],
        "required_sections": ["현재 고민", "구체적 질문", "조건"],
        "common_expressions": ["혹시 해보신 분 계세요?", "추천 부탁드려요", "경험 공유해주세요"],
        "opening_patterns": ["고민이 있어서 글 올려요", "추천 부탁드립니다", "조언 구합니다"],
        "closing_patterns": ["댓글 부탁드려요", "경험담 공유해주세요", "감사합니다"],
        "forbidden_elements": ["광고성 멘트", "특정 병원 홍보"],
        "recommended_elements": ["구체적 상황 설명", "예산 범위"],
        "tone": "궁금함, 걱정, 기대",
        "emotion_flow": ["고민", "질문", "기대"],
        "min_length": 200,
        "max_length": 600,
        "image_required": False,
        "tips": "구체적인 상황 설명 필수, 조건 명시하면 더 정확한 추천 받음",
    },
    {
        "value": "research",
        "label": "2. 발품/손품",
        "description": "병원 검색/비교 과정 공유",
        "order": 2,
        "content_purpose": "info",
        "core_message": "여러 곳 알아본 결과 공유해요",
        "emotion_tone": "nervous",
        "cta_type": "comment",
        "research_settings": {
            "search_method": "카페",
            "compared_clinics": "3군데",
            "comparison_criteria": ["가격", "후기", "원장경력", "위치"],
            "search_period": "일주일",
            "clinic_features": "A병원: 저렴, B병원: 유명, C병원: 친절",
            "price_comparison": "범위",
            "review_summary": "대체로 만족",
            "decision_status": "좁혀가는중",
            "leaning_toward": "B병원으로 기울어지는 중",
            "remaining_concern": "가격이 좀 부담",
        },
        "structure": [
            "검색 계기 (15%): 왜 알아보게 됐는지",
            "검색 과정 (25%): 어떻게 찾았는지",
            "비교 내용 (35%): 각 병원 특징",
            "현재 상태 (25%): 결정 상태, 고민 포인트",
        ],
        "required_sections": ["검색 방법", "병원별 특징", "비교 기준", "현재 결정 상태"],
        "common_expressions": ["발품 팔아봤어요", "손품 열심히 팔았어요", "비교해봤는데"],
        "opening_patterns": ["병원 알아보는 중이에요", "여러 곳 비교해봤어요"],
        "closing_patterns": ["아직 고민 중이에요", "이쪽으로 기울어지는 중", "결정하면 후기 올릴게요"],
        "forbidden_elements": ["광고성", "한 곳만 극찬"],
        "recommended_elements": ["객관적 비교", "장단점 균형"],
        "tone": "신중함, 분석적",
        "emotion_flow": ["탐색", "비교", "고민"],
        "min_length": 400,
        "max_length": 1000,
        "image_required": False,
        "tips": "객관적인 비교 필수, 한 곳만 좋게 쓰면 광고로 의심받음",
    },
    {
        "value": "consultation",
        "label": "3. 방문상담",
        "description": "상담 직후, 병원 비교/원장님 스타일",
        "order": 3,
        "content_purpose": "review",
        "core_message": "상담 다녀왔어요",
        "emotion_tone": "expectation",
        "cta_type": "comment",
        "consultation_settings": {
            "visit_date": "지난 주 토요일",
            "reservation_method": "온라인",
            "wait_time": "10분",
            "location_access": "역에서 5분",
            "interior_vibe": "깔끔",
            "cleanliness": "깨끗",
            "patient_count": "적당",
            "consultant": "원장직접",
            "consultation_time": "30분",
            "consultation_vibe": "친절",
            "recommended_procedure": "피코레이저 3회",
            "estimate": "50만원대",
            "push_level": "전혀없음",
            "explanation_quality": "상세",
            "booking_status": "추후예약",
            "booking_reason": "믿음이 가서",
            "hold_reason": "",
        },
        "structure": [
            "고민/배경 (15%): 현재 상태와 고민 설명",
            "탐색과정 (20%): 여러 병원 알아본 과정",
            "상담경험 (30%): 이 병원에서의 상담 경험 (핵심)",
            "원장님인상 (25%): 원장님 스타일, 느낌",
            "결정/질문 (10%): 수술 결정 또는 추가 질문",
        ],
        "required_sections": ["현재 고민/상태", "여러 병원 비교 언급", "원장님 상담 스타일 묘사", "결정 이유 또는 추가 질문"],
        "common_expressions": ["상담 받고 왔어요", "여러 곳 상담 받아봤는데", "원장님이 자세하게 설명해주셨어요"],
        "opening_patterns": ["~ 상담 받고 왔어요", "여러 곳 상담 받아봤는데", "드디어 상담 받으러 갔다 왔어요"],
        "closing_patterns": ["수술 결정했어요", "더 알아봐야겠어요", "다음에 또 상담 받으러 올 예정이에요"],
        "forbidden_elements": ["수술 결과 언급 (아직 안 했으니까)", "붓기, 회복 과정 언급", "최종 만족도"],
        "recommended_elements": ["CT 촬영", "비교 분석", "원장님 스타일"],
        "tone": "신중함, 분석적, 기대감",
        "emotion_flow": ["불안", "비교", "인상적", "결정"],
        "min_length": 500,
        "max_length": 1200,
        "image_required": False,
        "tips": "수술 전이므로 결과 언급 금지, 비교 구체적으로, 원장님 스타일 묘사 중요",
    },
    {
        "value": "procedure_day",
        "label": "4. 시술당일",
        "description": "수술 직후~2주, 생생한 경험",
        "order": 4,
        "content_purpose": "experience",
        "core_message": "시술 받고 왔어요",
        "emotion_tone": "nervous",
        "cta_type": "comment",
        "procedure_day_settings": {
            "preparation": "화장 안 하고",
            "arrival_process": "서류작성, 세안",
            "anesthesia_process": "마취크림 30분",
            "nervousness": "좀 긴장",
            "waiting_environment": "편했어요",
            "duration": "30분",
            "pain_level": 3,
            "pain_description": "따끔",
            "anesthesia_effect": "잘 들어서 괜찮음",
            "practitioner_attitude": "말 걸어줘서 편함",
            "mid_check": "거울 확인",
            "immediate_reaction": "빨개짐",
            "calming_care": "진정팩",
            "residual_pain": "바로 괜찮음",
            "can_go_home": "바로 귀가",
            "can_go_out": "마스크 쓰면",
            "precautions": ["세안금지", "음주금지", "자외선주의"],
            "prescription": "연고",
            "next_visit": "1주일 뒤 경과체크",
            "first_impression_score": 4,
            "vs_expectation": "기대만큼",
            "next_session_plan": "2주 뒤 2회차",
        },
        "structure": [
            "수술정보 (10%): 무슨 수술을 했는지",
            "당일경험 (25%): 수술 당일의 생생한 경험",
            "힘들었던점 (25%): 솔직하게 힘들었던 부분 (핵심)",
            "병원케어 (20%): 병원에서 어떻게 관리해줬는지",
            "현재상태 (20%): 지금 상태와 앞으로 기대",
        ],
        "required_sections": ["수술 종류/범위", "구체적 일차 (D+N)", "힘들었던 점 솔직하게", "병원 케어", "현재 상태"],
        "common_expressions": ["수술하고 ~일차", "솔직히 처음엔 힘들었어요", "원장님께서 케어해주셔서", "아직 붓기가 있지만"],
        "opening_patterns": ["수술하고 ~일차", "D+~ 후기", "수술 당일 후기"],
        "closing_patterns": ["경과 또 올릴게요", "붓기 빠지면 기대돼요", "회복 잘 되고 있어요"],
        "forbidden_elements": ["최종 결과 단정", "완전히 자리잡음", "과도한 고통 묘사"],
        "recommended_elements": ["솔직한 경험", "병원 케어", "회복 과정"],
        "tone": "솔직함, 생생함, 희망",
        "emotion_flow": ["긴장", "힘듦", "안도", "기대"],
        "min_length": 400,
        "max_length": 1000,
        "image_required": True,
        "tips": "솔직하게 힘들었던 점도 언급하되, 병원 케어로 해결된 부분 강조",
    },
    {
        "value": "recovery_1month",
        "label": "5. 시술 후 1개월",
        "description": "붓기 빠지고 초기 결과",
        "order": 5,
        "content_purpose": "review",
        "core_message": "한 달 경과 공유해요",
        "emotion_tone": "satisfied",
        "cta_type": "comment",
        "recovery_1month_settings": {
            "record_point": "30일",
            "daily_changes": "1일차: 붓기, 7일차: 회복, 14일차: 자리잡기 시작",
            "photo_status": "경과 사진 첨부",
            "expected_vs_actual": "예상보다 빨리",
            "actual_downtime": "3~5일",
            "work_resume": "다음날 출근",
            "makeup_possible": "3일차",
            "daily_inconvenience": "세안 조심",
            "exercise_possible": "1주일 후",
            "effect_satisfaction": "확실히 효과",
            "others_reaction": "칭찬받음",
            "vs_expectation": "기대 이상",
            "naturalness": "자연스러움",
            "next_session": "2회차 예약함",
            "additional_procedure": "미정",
            "revisit_intention": "또 갈 예정",
        },
        "structure": [
            "현재시점 (10%): 1개월이 됐다는 언급",
            "회복과정 (25%): 지난 한 달간의 회복 과정",
            "현재상태 (30%): 지금 상태 구체적으로 (핵심)",
            "주변반응 (20%): 친구, 가족 등 주변 반응",
            "기대감 (15%): 앞으로 더 좋아질 거라는 기대",
        ],
        "required_sections": ["1개월 시점 명시", "붓기 변화", "현재 상태", "주변 반응", "앞으로 기대"],
        "common_expressions": ["벌써 한 달이 됐네요", "아직 조금 남아있지만", "주변에서 예뻐졌다고", "더 자리잡으면 또 올릴게요"],
        "opening_patterns": ["벌써 한 달", "1개월 경과 후기", "한 달 지났어요"],
        "closing_patterns": ["더 자리잡으면 또 올릴게요", "2개월 후기 기대해주세요", "점점 좋아지고 있어요"],
        "forbidden_elements": ["완전히 자리잡음 (아직 1개월)", "최종 결과 단정", "100% 확신"],
        "recommended_elements": ["주변 반응", "1개월 전후 비교", "기대감"],
        "tone": "뿌듯함, 기대감, 안도",
        "emotion_flow": ["회고", "만족", "기대"],
        "min_length": 400,
        "max_length": 900,
        "image_required": True,
        "tips": "아직 초기 단계임을 명시, 주변 반응으로 객관성 확보",
    },
    {
        "value": "recovery_2month_plus",
        "label": "6. 시술 후 2개월+",
        "description": "최종 결과와 총평",
        "order": 6,
        "content_purpose": "review",
        "core_message": "최종 결과 공유해요",
        "emotion_tone": "satisfied",
        "cta_type": "inquiry",
        "recovery_2month_plus_settings": {
            "before_after_comparison": "확실히 피부 톤이 밝아졌어요",
            "goal_achievement": "90%",
            "maintenance_duration": "아직 유지",
            "additional_procedure_needed": "필요없음",
            "value_for_money": "돈값 함",
            "total_cost": "3회 총 60만원",
            "repurchase_intention": "또 할 예정",
            "price_satisfaction": "비싸도 만족",
            "recommend_target": "기미 고민인 분들께",
            "not_recommend_target": "급하신 분",
            "recommend_level": "강추",
            "revisit_intention": "당연히 또 감",
            "procedure_tip": "마취 충분히 해달라고 하세요",
            "clinic_selection_tip": "상담 여러 곳 받아보세요",
            "care_tip": "자외선 차단 필수",
            "caution": "시술 후 3일간 세안 조심",
        },
        "structure": [
            "현재시점 (10%): 2개월+ 됐다는 언급",
            "전체과정 (25%): 수술 전부터 지금까지 요약",
            "최종결과 (30%): 지금의 최종 결과 (핵심)",
            "총평 (20%): 전체적인 만족도와 평가",
            "추천 (15%): 추천과 CTA",
        ],
        "required_sections": ["2개월+ 시점 명시", "전체 과정 요약", "최종 결과", "총평", "추천 + CTA"],
        "common_expressions": ["어느덧 2개월", "확실히 자리잡았어요", "이제 티도 안 나요", "하길 정말 잘했어요"],
        "opening_patterns": ["어느덧 2개월", "드디어 최종 후기", "2개월 넘었어요"],
        "closing_patterns": ["고민하시는 분들 추천", "상담이라도 받아보세요", "정말 만족스러워요"],
        "forbidden_elements": ["불확실한 결과", "애매한 만족도", "부정적 언급"],
        "recommended_elements": ["전후 비교 사진", "강력 추천", "상담 권유"],
        "tone": "확신, 자부심, 추천",
        "emotion_flow": ["회고", "자부심", "추천"],
        "min_length": 500,
        "max_length": 1200,
        "image_required": True,
        "tips": "전후 비교 사진 필수, 강력 추천, 상담 권유로 마무리",
    },
]


def create_initial_data():
    """초기 데이터 생성"""
    from apps.data.models import Persona, CafeProfile

    # 페르소나 생성
    print("=" * 50)
    print("페르소나 생성 중...")
    print("=" * 50)
    for preset in PERSONA_PRESETS:
        persona, created = Persona.objects.update_or_create(
            name=preset['name'],
            defaults=preset
        )
        status = "생성됨" if created else "업데이트됨"
        print(f"  Persona: {persona.name} - {status}")

    # 카페 프로필 생성
    print("\n" + "=" * 50)
    print("카페 프로필 생성 중...")
    print("=" * 50)
    for preset in CAFE_PRESETS:
        cafe, created = CafeProfile.objects.update_or_create(
            name=preset['name'],
            defaults=preset
        )
        status = "생성됨" if created else "업데이트됨"
        print(f"  CafeProfile: {cafe.name} - {status}")

    print(f"\n총 {len(PERSONA_PRESETS)}개 페르소나, {len(CAFE_PRESETS)}개 카페 프로필 처리 완료")


def create_content_type_profiles():
    """컨텐츠 유형 프로파일 생성"""
    from apps.data.models import ContentTypeProfile

    print("\n" + "=" * 50)
    print("컨텐츠 유형 프로파일 생성 중...")
    print("=" * 50)

    for preset in CONTENT_TYPE_PRESETS:
        profile, created = ContentTypeProfile.objects.update_or_create(
            value=preset['value'],
            defaults=preset
        )
        status = "생성됨" if created else "업데이트됨"
        print(f"  ContentTypeProfile: {profile.label} - {status}")

    print(f"\n총 {len(CONTENT_TYPE_PRESETS)}개 컨텐츠 유형 프로파일 처리 완료")


def create_all():
    """모든 초기 데이터 생성"""
    print("\n" + "=" * 60)
    print("presetss.txt 기반 144개 항목 초기 데이터 생성")
    print("=" * 60 + "\n")

    create_initial_data()
    create_content_type_profiles()

    print("\n" + "=" * 60)
    print("완료! 총 144개 항목 설정 완료")
    print("  - 페르소나: 26개 항목 x 6개 프리셋")
    print("  - 카페 셋팅: 21개 항목 x 6개 프리셋")
    print("  - 컨텐츠 유형: 공통 4개 + 타입별 세부 항목 x 6개 프리셋")
    print("=" * 60)


if __name__ == "__main__":
    create_all()
