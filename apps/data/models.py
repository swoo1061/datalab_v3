"""
리뷰 생성 시스템 데이터 모델
"""
from django.db import models
from django.db.models import JSONField


class Campaign(models.Model):
    """마케팅 캠페인"""
    name = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    meta = JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class Persona(models.Model):
    """작성자 페르소나 설정 (26개 항목)"""

    # ===== 기본 신원 (5개) =====
    name = models.CharField(max_length=100, verbose_name="이름/닉네임")
    age_group = models.CharField(
        max_length=20,
        choices=[
            ('20_early', '20대 초반'), ('20_mid', '20대 중반'), ('20_late', '20대 후반'),
            ('30_early', '30대 초반'), ('30_mid', '30대 중반'), ('30_late', '30대 후반'),
            ('40_plus', '40대 이상')
        ],
        verbose_name="연령대"
    )
    gender = models.CharField(
        max_length=10,
        choices=[('female', '여성'), ('male', '남성')],
        verbose_name="성별"
    )
    occupation = models.CharField(
        max_length=20,
        choices=[
            ('office', '직장인'), ('student', '대학생'), ('housewife', '주부'),
            ('self_employed', '자영업'), ('freelancer', '프리랜서')
        ],
        default='office',
        verbose_name="직업/신분"
    )
    region = models.CharField(
        max_length=20,
        choices=[
            ('seoul', '서울'), ('gyeonggi', '경기'), ('incheon', '인천'),
            ('busan', '부산'), ('other', '기타 지방')
        ],
        default='seoul',
        verbose_name="거주 지역"
    )

    # ===== 말투 스타일 (5개) =====
    honorific_level = models.CharField(
        max_length=20,
        choices=[('formal', '존댓말'), ('informal', '반말'), ('mixed', '혼용')],
        default='formal',
        verbose_name="존칭 레벨"
    )
    exclamation_freq = models.CharField(
        max_length=20,
        choices=[('high', '높음'), ('medium', '중간'), ('low', '낮음')],
        default='medium',
        verbose_name="감탄사 빈도"
    )
    emoji_usage = models.CharField(
        max_length=20,
        choices=[('many', '많음'), ('moderate', '적당히'), ('rarely', '거의없음')],
        default='moderate',
        verbose_name="이모지 사용"
    )
    sentence_ending = models.CharField(
        max_length=20,
        choices=[
            ('yo', '~요'), ('yong', '~용'), ('dang', '~당'),
            ('eum', '~음'), ('mixed', '혼용')
        ],
        default='yo',
        verbose_name="문장 종결 패턴"
    )
    sentence_length = models.CharField(
        max_length=20,
        choices=[('short', '짧은문장'), ('medium', '중간'), ('long', '긴문장')],
        default='medium',
        verbose_name="문장 길이"
    )

    # ===== 시술 경험 (5개) =====
    experience_level = models.CharField(
        max_length=20,
        choices=[
            ('first', '첫시술'), ('few', '2~3회차'),
            ('many', '5회이상'), ('regular', '단골')
        ],
        default='first',
        verbose_name="경험 레벨"
    )
    fear_level = models.CharField(
        max_length=20,
        choices=[
            ('very_scared', '매우겁많음'), ('little', '약간'),
            ('normal', '보통'), ('brave', '담대함')
        ],
        default='normal',
        verbose_name="겁쟁이 정도"
    )
    price_sensitivity = models.CharField(
        max_length=20,
        choices=[
            ('high', '높음(가성비)'), ('medium', '중간'), ('low', '낮음(퀄리티)')
        ],
        default='medium',
        verbose_name="가격 민감도"
    )
    skin_concerns = JSONField(
        default=list,
        verbose_name="피부/외모 고민",
        help_text="기미/잡티/모공/주름/탄력/턱선/코/눈",
        blank=True
    )
    skin_type = models.CharField(
        max_length=20,
        choices=[
            ('dry', '건성'), ('oily', '지성'),
            ('combination', '복합성'), ('sensitive', '민감성')
        ],
        default='combination',
        verbose_name="피부 타입"
    )

    # ===== 표현 라이브러리 (5개) =====
    intro_expression = models.CharField(
        max_length=200,
        default="솔직히 처음엔 걱정했는데",
        verbose_name="인트로 표현"
    )
    transition_expression = models.CharField(
        max_length=200,
        default="아무튼!",
        verbose_name="전환 표현"
    )
    conclusion_expression = models.CharField(
        max_length=200,
        default="결론은 대만족!",
        verbose_name="결론 표현"
    )
    recommend_expression = models.CharField(
        max_length=200,
        default="저처럼 겁많은 분들도",
        verbose_name="추천 표현"
    )
    frequent_expressions = JSONField(
        default=list,
        verbose_name="자주 쓰는 표현 1~3",
        blank=True
    )

    # ===== 신뢰 요소 (5개) =====
    own_money_emphasis = models.CharField(
        max_length=20,
        choices=[('always', '항상'), ('sometimes', '가끔'), ('never', '안함')],
        default='always',
        verbose_name="내돈내산 강조"
    )
    cons_mention_style = models.CharField(
        max_length=20,
        choices=[('weak', '약함'), ('medium', '중간'), ('strong', '강함')],
        default='medium',
        verbose_name="단점 언급 스타일"
    )
    cons_examples = JSONField(
        default=list,
        verbose_name="단점 예시 풀",
        help_text="주차불편/대기김/가격높음/위치애매",
        blank=True
    )
    comparison_mention = models.BooleanField(
        default=True,
        verbose_name="비교 언급 여부"
    )
    choice_reason = JSONField(
        default=list,
        verbose_name="선택 이유 표현",
        help_text="후기/지인추천/가격/원장경력/위치",
        blank=True
    )

    # ===== 메타 =====
    description = models.TextField(verbose_name="설정 설명", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "페르소나"
        verbose_name_plural = "페르소나 목록"

    def __str__(self):
        return f"{self.name} ({self.get_age_group_display()} {self.get_gender_display()})"


class CafeProfile(models.Model):
    """업로드 대상 카페/플랫폼 설정 (21개 항목)"""

    # ===== 플랫폼 정보 (4개) =====
    platform_type = models.CharField(
        max_length=30,
        choices=[
            ('naver_blog', '네이버블로그'), ('cafe', '카페'),
            ('comment', '댓글'), ('app_review', '앱리뷰'), ('jisin', '지식인')
        ],
        default='cafe',
        verbose_name="플랫폼 타입"
    )
    name = models.CharField(max_length=100, verbose_name="카페/플랫폼명")
    cafe_character = models.CharField(
        max_length=30,
        choices=[
            ('info_share', '정보공유형'), ('chat', '수다형'),
            ('expert', '전문가형'), ('qna', 'Q&A형')
        ],
        default='info_share',
        verbose_name="카페 성격"
    )
    board_type = models.CharField(
        max_length=30,
        choices=[
            ('review', '후기게시판'), ('free', '자유게시판'), ('question', '질문게시판')
        ],
        default='review',
        verbose_name="게시판 지정"
    )

    # ===== 글 형식 (5개) =====
    length_range = models.CharField(
        max_length=30,
        choices=[
            ('100_300', '100~300'), ('300_800', '300~800'), ('800_1500', '800~1500'),
            ('1500_3000', '1500~3000'), ('3000_plus', '3000+')
        ],
        default='800_1500',
        verbose_name="글자수 범위"
    )
    required_elements = JSONField(
        default=list,
        verbose_name="필수 포함 요소",
        help_text="제목/본문/사진설명/해시태그/별점",
        blank=True
    )
    subtitle_style = models.CharField(
        max_length=20,
        choices=[
            ('square', '■'), ('arrow', '▶'), ('circle', '●'),
            ('number', '숫자'), ('none', '없음')
        ],
        default='square',
        verbose_name="소제목 스타일"
    )
    paragraph_style = models.CharField(
        max_length=20,
        choices=[('short', '짧은(2~3줄)'), ('medium', '중간'), ('long', '긴 문단')],
        default='medium',
        verbose_name="문단 구분"
    )
    photo_mention = models.CharField(
        max_length=30,
        choices=[
            ('full', '사진 첨부'), ('partial', '부분만'), ('none', '언급안함')
        ],
        default='full',
        verbose_name="사진 언급 방식"
    )

    # ===== 상호작용 (3개) =====
    question_inducement = models.CharField(
        max_length=100,
        default="",
        verbose_name="질문 유도",
        help_text="혹시 해보신 분? / 없음",
        blank=True
    )
    info_request = models.CharField(
        max_length=100,
        default="",
        verbose_name="정보 요청",
        help_text="궁금한 거 댓글로 / 없음",
        blank=True
    )
    reply_style = models.CharField(
        max_length=20,
        choices=[
            ('kind_detailed', '친절상세'), ('simple', '간단명료'), ('lazy', '귀찮은척')
        ],
        default='kind_detailed',
        verbose_name="답변 스타일"
    )

    # ===== 카페 규칙 (4개) =====
    ad_restriction = models.CharField(
        max_length=20,
        choices=[('strict', '엄격'), ('normal', '보통'), ('loose', '느슨')],
        default='strict',
        verbose_name="광고 금지 강도"
    )
    hospital_name_disclosure = models.CharField(
        max_length=20,
        choices=[('allowed', '가능'), ('initial_only', '이니셜만'), ('forbidden', '불가')],
        default='allowed',
        verbose_name="병원명 공개"
    )
    price_disclosure = models.CharField(
        max_length=20,
        choices=[('specific', '가능(구체적)'), ('range_only', '범위만'), ('forbidden', '불가')],
        default='range_only',
        verbose_name="가격 공개"
    )
    photo_required = models.CharField(
        max_length=20,
        choices=[('required', '필수'), ('recommended', '권장'), ('optional', '선택')],
        default='recommended',
        verbose_name="사진 필수 여부"
    )

    # ===== SEO/노출 (4개) =====
    title_prefix = models.CharField(
        max_length=30,
        choices=[
            ('review', '[후기]'), ('honest', '[솔직]'),
            ('own_money', '[내돈내산]'), ('none', '없음')
        ],
        default='none',
        verbose_name="제목 접두어"
    )
    hashtag_count = models.CharField(
        max_length=20,
        choices=[
            ('none', '없음'), ('under_5', '5개이하'), ('5_10', '5~10'),
            ('10_15', '10~15'), ('over_15', '15+')
        ],
        default='5_10',
        verbose_name="해시태그 개수"
    )
    required_keywords = JSONField(
        default=list,
        verbose_name="필수 키워드",
        help_text="시술명/병원명/지역명/가격/후기",
        blank=True
    )
    forbidden_keywords = JSONField(
        default=list,
        verbose_name="금지 키워드",
        help_text="협찬/광고/제공/원고료",
        blank=True
    )

    # ===== 대상 설정 (1개) =====
    target_reader = models.CharField(
        max_length=20,
        choices=[('beginner', '초보'), ('experienced', '경험자'), ('expert', '전문가')],
        default='beginner',
        verbose_name="대상 독자"
    )

    # ===== 기존 필드 (호환성) =====
    url = models.URLField(blank=True, verbose_name="카페 URL")
    tips = models.TextField(blank=True, verbose_name="작성 팁")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "카페 프로필"
        verbose_name_plural = "카페 프로필 목록"

    def __str__(self):
        return f"{self.name} ({self.get_platform_type_display()})"

    @property
    def min_length(self):
        """글자수 범위에서 최소값 추출"""
        mapping = {
            '100_300': 100, '300_800': 300, '800_1500': 800,
            '1500_3000': 1500, '3000_plus': 3000
        }
        return mapping.get(self.length_range, 800)

    @property
    def max_length(self):
        """글자수 범위에서 최대값 추출"""
        mapping = {
            '100_300': 300, '300_800': 800, '800_1500': 1500,
            '1500_3000': 3000, '3000_plus': 5000
        }
        return mapping.get(self.length_range, 1500)


class ContentTypeProfile(models.Model):
    """컨텐츠 유형 프로파일 (공통 4개 + 타입별 세부 항목)"""

    CONTENT_TYPES = [
        ('recommend_request', '추천받기'),
        ('research', '발품/손품'),
        ('consultation', '방문상담'),
        ('procedure_day', '시술당일'),
        ('recovery_1month', '시술 후 1개월'),
        ('recovery_2month_plus', '시술 후 2개월+'),
    ]

    value = models.CharField(max_length=50, unique=True, verbose_name="유형 코드")
    label = models.CharField(max_length=100, verbose_name="유형명")
    description = models.TextField(verbose_name="설명", blank=True)

    # ===== 공통 셋팅 (4개) =====
    content_purpose = models.CharField(
        max_length=30,
        choices=[
            ('info', '정보제공'), ('review', '후기공유'), ('recommend_request', '추천요청'),
            ('question', '질문'), ('experience', '경험담')
        ],
        default='review',
        verbose_name="컨텐츠 목적"
    )
    core_message = models.TextField(
        verbose_name="핵심 메시지",
        help_text="전달하고 싶은 1줄 요약",
        blank=True
    )
    emotion_tone = models.CharField(
        max_length=30,
        choices=[
            ('expectation', '기대'), ('worry', '걱정'), ('nervous', '긴장'),
            ('excited', '설렘'), ('satisfied', '만족'), ('regret', '아쉬움'),
            ('disappointed', '후회')
        ],
        default='satisfied',
        verbose_name="감정 톤"
    )
    cta_type = models.CharField(
        max_length=30,
        choices=[
            ('comment', '댓글유도'), ('share', '공유유도'),
            ('inquiry', '병원문의유도'), ('none', '없음')
        ],
        default='comment',
        verbose_name="CTA (행동유도)"
    )

    # ===== 추천받기 세부 설정 (9개) =====
    recommend_settings = JSONField(
        default=dict,
        verbose_name="추천받기 설정",
        help_text="""
        {
            "current_concern": "기미가 점점 진해져서",
            "procedure_experience": "first/experienced",
            "budget_range": "50만원 이내",
            "preferred_region": "강남쪽",
            "urgency": "이번 주 안에/천천히",
            "question_type": "병원추천/시술추천/시술비교/부작용질문",
            "specific_question": "피코 vs 레이저 뭐가 나을까요?",
            "worry_points": ["통증", "다운타임", "효과"],
            "wanted_info": ["경험담", "가격정보", "추천병원"]
        }
        """,
        blank=True
    )

    # ===== 발품/손품 세부 설정 (12개) =====
    research_settings = JSONField(
        default=dict,
        verbose_name="발품/손품 설정",
        help_text="""
        {
            "search_method": "카페/블로그/지인추천/광고/앱",
            "compared_clinics": "3군데",
            "comparison_criteria": ["가격", "후기", "원장경력", "위치", "장비"],
            "search_period": "일주일",
            "clinic_features": "A병원: 저렴, B병원: 유명",
            "price_comparison": "구체적/범위/비슷비슷",
            "review_summary": "대체로 만족/호불호 갈림",
            "decision_status": "고민중/좁혀가는중/거의결정/결정완료",
            "leaning_toward": "B병원으로 기울어지는 중",
            "remaining_concern": "가격이 좀 부담"
        }
        """,
        blank=True
    )

    # ===== 방문상담 세부 설정 (17개) =====
    consultation_settings = JSONField(
        default=dict,
        verbose_name="방문상담 설정",
        help_text="""
        {
            "visit_date": "지난 주 토요일",
            "reservation_method": "전화/온라인/앱/워크인",
            "wait_time": "10분",
            "location_access": "역에서 5분",
            "interior_vibe": "깔끔/고급/아늑",
            "cleanliness": "깨끗",
            "patient_count": "적당",
            "consultant": "원장직접/실장/상담사",
            "consultation_time": "30분",
            "consultation_vibe": "친절/상세/강압적/사무적",
            "recommended_procedure": "피코레이저 3회",
            "estimate": "50만원",
            "push_level": "전혀없음/약간/부담스러움",
            "explanation_quality": "상세",
            "booking_status": "당일예약/추후예약/보류/거절",
            "booking_reason": "믿음이 가서",
            "hold_reason": "더 알아보려고"
        }
        """,
        blank=True
    )

    # ===== 시술당일 세부 설정 (24개) =====
    procedure_day_settings = JSONField(
        default=dict,
        verbose_name="시술당일 설정",
        help_text="""
        {
            "preparation": "금식/화장 안 하고",
            "arrival_process": "서류작성/세안/사진촬영",
            "anesthesia_process": "마취크림 30분/수면마취",
            "nervousness": "엄청 떨림/좀 긴장/담담",
            "waiting_environment": "편했어요",
            "duration": "30분",
            "pain_level": 3,
            "pain_description": "따끔/뜨거움/당김/찌릿",
            "anesthesia_effect": "잘 들어서 괜찮음",
            "practitioner_attitude": "말 걸어줘서 편함",
            "mid_check": "거울 확인",
            "immediate_reaction": "빨개짐/부기/멍/멀쩡",
            "calming_care": "진정팩/쿨링/연고",
            "residual_pain": "바로 괜찮음/얼얼함 지속",
            "can_go_home": "바로 귀가",
            "can_go_out": "마스크 쓰면",
            "precautions": ["세안금지", "음주금지", "자외선주의"],
            "prescription": "연고/먹는약/재생크림",
            "next_visit": "1주일 뒤 경과체크",
            "first_impression_score": 5,
            "vs_expectation": "기대 이상/기대만큼/기대 이하",
            "next_session_plan": "2주 뒤 2회차"
        }
        """,
        blank=True
    )

    # ===== 시술 후 1개월 세부 설정 (17개) =====
    recovery_1month_settings = JSONField(
        default=dict,
        verbose_name="시술 후 1개월 설정",
        help_text="""
        {
            "record_point": "30일",
            "daily_changes": "1일차: 붓기, 7일차: 회복",
            "photo_status": "경과 사진 첨부/부분만/없음",
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
            "additional_procedure": "다른 시술도",
            "revisit_intention": "또 갈 예정"
        }
        """,
        blank=True
    )

    # ===== 시술 후 2개월+ 세부 설정 (16개) =====
    recovery_2month_plus_settings = JSONField(
        default=dict,
        verbose_name="시술 후 2개월+ 설정",
        help_text="""
        {
            "before_after_comparison": "변화 정도 구체적 서술",
            "goal_achievement": "80%",
            "maintenance_duration": "아직 유지",
            "additional_procedure_needed": "필요없음/유지 시술/보완 필요",
            "value_for_money": "돈값 함",
            "total_cost": "회차별/총액/추가비용 포함",
            "repurchase_intention": "또 할 예정",
            "price_satisfaction": "비싸도 만족",
            "recommend_target": "OO 고민인 분들께",
            "not_recommend_target": "급하신 분",
            "recommend_level": "강추/추천/보통/비추/강력비추",
            "revisit_intention": "당연히 또 감",
            "procedure_tip": "마취 충분히 해달라고",
            "clinic_selection_tip": "상담 여러 곳 받아보세요",
            "care_tip": "자외선 차단 필수",
            "caution": "OO는 피하세요"
        }
        """,
        blank=True
    )

    # ===== 기존 구조 설정 (호환성) =====
    structure = JSONField(default=list, verbose_name="글 구조", blank=True)
    required_sections = JSONField(default=list, verbose_name="필수 포함 섹션", blank=True)

    # 표현 설정
    common_expressions = JSONField(default=list, verbose_name="자주 쓰는 표현", blank=True)
    opening_patterns = JSONField(default=list, verbose_name="시작 패턴", blank=True)
    closing_patterns = JSONField(default=list, verbose_name="마무리 패턴", blank=True)

    # 금지/권장
    forbidden_elements = JSONField(default=list, verbose_name="금지 요소", blank=True)
    recommended_elements = JSONField(default=list, verbose_name="권장 요소", blank=True)

    # 톤/감정
    tone = models.CharField(max_length=200, blank=True, verbose_name="톤")
    emotion_flow = JSONField(default=list, verbose_name="감정 흐름", blank=True)

    # 글자수
    min_length = models.IntegerField(default=400, verbose_name="최소 글자수")
    max_length = models.IntegerField(default=1200, verbose_name="최대 글자수")

    # 기타
    image_required = models.BooleanField(default=False, verbose_name="이미지 필수")
    tips = models.TextField(blank=True, verbose_name="작성 팁")
    order = models.IntegerField(default=0, verbose_name="정렬 순서")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "컨텐츠 유형 프로파일"
        verbose_name_plural = "컨텐츠 유형 프로파일 목록"
        ordering = ['order', 'value']

    def __str__(self):
        return f"{self.label} ({self.value})"

    def get_type_settings(self):
        """컨텐츠 타입에 맞는 세부 설정 반환"""
        settings_map = {
            'recommend_request': self.recommend_settings,
            'research': self.research_settings,
            'consultation': self.consultation_settings,
            'procedure_day': self.procedure_day_settings,
            'recovery_1month': self.recovery_1month_settings,
            'recovery_2month_plus': self.recovery_2month_plus_settings,
        }
        return settings_map.get(self.value, {})


class ClinicGuide(models.Model):
    """병원 가이드 (MD 파일에서 파싱된 데이터)"""
    name = models.CharField(max_length=100, verbose_name="병원명")
    file_path = models.CharField(max_length=500, blank=True, verbose_name="MD 파일 경로")
    
    # 기본 정보
    location = models.TextField(blank=True, verbose_name="위치")
    hours = models.CharField(max_length=200, blank=True, verbose_name="운영시간")
    parking = models.TextField(blank=True, verbose_name="주차 정보")
    
    # 파싱된 전체 데이터 (JSON)
    doctors = JSONField(default=list, verbose_name="의료진 정보", blank=True)
    consultants = JSONField(default=list, verbose_name="상담실장 정보", blank=True)
    price_list = JSONField(default=list, verbose_name="수가표", blank=True)
    process = models.TextField(blank=True, verbose_name="상담 프로세스")
    aftercare = JSONField(default=dict, verbose_name="사후관리", blank=True)
    post_care = JSONField(default=dict, verbose_name="수술 후 주의사항", blank=True)
    features = JSONField(default=dict, verbose_name="병원 특징", blank=True)
    
    # 언급 가능/불가 병원
    allowed_hospitals = JSONField(default=dict, verbose_name="언급 가능 병원", blank=True)
    blocked_hospitals = JSONField(default=list, verbose_name="언급 불가 병원", blank=True)
    
    # 원본 데이터
    raw_data = JSONField(default=dict, verbose_name="파싱 원본 데이터", blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "병원 가이드"
        verbose_name_plural = "병원 가이드 목록"

    def __str__(self):
        return self.name

    def get_doctor_by_code(self, code):
        """코드로 의료진 찾기"""
        for doc in self.doctors:
            if doc.get('code') == code:
                return doc
        return None

    def get_doctor_by_name(self, name):
        """이름으로 의료진 찾기"""
        for doc in self.doctors:
            if doc.get('name') == name:
                return doc
        return None

    def get_price(self, doctor_code, procedure):
        """의료진+시술로 가격 찾기"""
        for price in self.price_list:
            if price.get('doctor_code') == doctor_code and price.get('procedure') == procedure:
                return price
        return None

    def get_procedures_by_doctor(self, doctor_code):
        """특정 의료진의 시술 목록"""
        return [p for p in self.price_list if p.get('doctor_code') == doctor_code]


class GeneratedReview(models.Model):
    """AI 생성 리뷰 기록"""
    clinic = models.ForeignKey(ClinicGuide, on_delete=models.SET_NULL, null=True, verbose_name="병원")
    persona = models.ForeignKey(Persona, on_delete=models.SET_NULL, null=True, verbose_name="페르소나")
    cafe = models.ForeignKey(CafeProfile, on_delete=models.SET_NULL, null=True, verbose_name="타겟 카페")
    
    doctor_code = models.CharField(max_length=20, blank=True, verbose_name="담당 원장 코드")
    doctor_name = models.CharField(max_length=50, blank=True, verbose_name="담당 원장명")
    procedure = models.CharField(max_length=100, verbose_name="시술명")
    
    # 생성 결과
    generated_text = models.TextField(verbose_name="생성된 리뷰")
    prompt_used = models.TextField(blank=True, verbose_name="사용된 프롬프트")
    
    # 상태
    status = models.CharField(
        max_length=20,
        choices=[
            ('generated', '생성됨'),
            ('edited', '수정됨'),
            ('uploaded', '업로드완료'),
            ('rejected', '반려')
        ],
        default='generated',
        verbose_name="상태"
    )
    upload_url = models.URLField(blank=True, verbose_name="업로드 URL")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "생성 리뷰"
        verbose_name_plural = "생성 리뷰 목록"
        ordering = ['-created_at']

    def __str__(self):
        clinic_name = self.clinic.name if self.clinic else '?'
        date_str = self.created_at.strftime('%Y-%m-%d') if self.created_at else ''
        return f"{clinic_name} - {self.procedure} ({date_str})"


class Review(models.Model):
    """수집된 리뷰 (기존 모델 유지)"""
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=100, blank=True)
    original_text = models.TextField()
    cleaned_text = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=10, default='ko')
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = JSONField(default=dict, blank=True)
    sentiment = models.CharField(max_length=32, blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    keywords = JSONField(default=list, blank=True)
    insights = JSONField(default=list, blank=True)

    def __str__(self):
        return f"Review {self.pk} - {self.source}"


class AccessLog(models.Model):
    """접속 로그"""
    ip_address = models.GenericIPAddressField(verbose_name="IP 주소")
    path = models.CharField(max_length=500, verbose_name="요청 경로")
    method = models.CharField(max_length=10, verbose_name="HTTP 메소드")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    referer = models.TextField(blank=True, verbose_name="Referer")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="접속 시간")

    class Meta:
        verbose_name = "접속 로그"
        verbose_name_plural = "접속 로그 목록"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.ip_address} - {self.path} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"


class ImageAsset(models.Model):
    """이미지 자산"""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.CharField(max_length=1024)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    exif = JSONField(default=dict, blank=True)
    ocr_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    tags = JSONField(default=list, blank=True)
    caption = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Image {self.pk}"


class PromptTemplate(models.Model):
    """프롬프트 템플릿"""
    MODE_CHOICES = [
        ('basic', 'Basic'),
        ('basic_plus', 'Basic Plus'),
        ('pro_header', 'Pro - 헤더'),
        ('pro_guidelines', 'Pro - 가이드라인'),
    ]

    mode = models.CharField(max_length=20, choices=MODE_CHOICES, verbose_name="모드")
    name = models.CharField(max_length=100, verbose_name="템플릿 이름")
    content = models.TextField(verbose_name="프롬프트 내용")
    description = models.TextField(blank=True, verbose_name="설명")
    is_default = models.BooleanField(default=False, verbose_name="기본 템플릿")
    is_active = models.BooleanField(default=True, verbose_name="활성화")
    version = models.PositiveIntegerField(default=1, verbose_name="버전")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "프롬프트 템플릿"
        verbose_name_plural = "프롬프트 템플릿 목록"
        ordering = ['-is_default', '-updated_at']

    def __str__(self):
        default_mark = " (기본)" if self.is_default else ""
        return f"[{self.get_mode_display()}] {self.name} v{self.version}{default_mark}"

    def save(self, *args, **kwargs):
        # 기본 템플릿 설정 시 같은 모드의 다른 템플릿 기본 해제
        if self.is_default:
            PromptTemplate.objects.filter(mode=self.mode, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class PromptTemplateVersion(models.Model):
    """프롬프트 템플릿 버전 이력"""
    template = models.ForeignKey(PromptTemplate, on_delete=models.CASCADE, related_name='versions')
    version = models.PositiveIntegerField(verbose_name="버전")
    content = models.TextField(verbose_name="프롬프트 내용")
    changed_by = models.CharField(max_length=100, blank=True, verbose_name="변경자")
    change_note = models.TextField(blank=True, verbose_name="변경 사유")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "프롬프트 버전 이력"
        verbose_name_plural = "프롬프트 버전 이력 목록"
        ordering = ['-version']
        unique_together = ['template', 'version']

    def __str__(self):
        return f"{self.template.name} v{self.version}"
