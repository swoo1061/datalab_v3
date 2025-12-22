"""
Notion MD Export 파일 파서

Notion에서 export된 병원 가이드 MD 파일을 구조화된 데이터로 파싱합니다.
"""
import re
import json
from pathlib import Path
from typing import Dict, List, Optional


def parse_clinic_markdown(filepath: str) -> Dict:
    """
    Notion MD export 파일을 구조화된 데이터로 파싱
    
    Args:
        filepath: MD 파일 경로
        
    Returns:
        파싱된 병원 데이터 딕셔너리
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return parse_clinic_content(content)


def parse_clinic_content(content: str) -> Dict:
    """
    MD 컨텐츠를 파싱
    
    Args:
        content: MD 파일 내용
        
    Returns:
        파싱된 병원 데이터 딕셔너리
    """
    result = {
        "basic_info": {},
        "doctors": [],
        "consultants": [],
        "price_list": [],
        "post_care": {},
        "process": "",
        "aftercare": {},
        "allowed_hospitals": {},
        "blocked_hospitals": [],
        "features": {},
        "raw_data": {}
    }
    
    # 병원 가이드 섹션 추출
    guide_match = re.search(r'\*\*병원 가이드\*\*(.*?)(?=\*\*커뮤니티|\*\*쪽지|$)', content, re.DOTALL)
    if guide_match:
        guide_section = guide_match.group(1)
        _parse_guide_section(guide_section, result)
    
    # 수술 후 주의사항 섹션 추출
    _parse_post_care_section(content, result)
    
    # 수가표 섹션 추출
    _parse_price_section(content, result)
    
    # 의료진 상세 파싱
    if result["basic_info"].get("doctors_raw"):
        result["doctors"] = _parse_doctors(result["basic_info"]["doctors_raw"])
        
        # 주력수술 정보 병합
        if result["basic_info"].get("specialties_raw"):
            _merge_doctor_specialties(result["doctors"], result["basic_info"]["specialties_raw"])
    
    # 상담실장 상세 파싱
    if result["basic_info"].get("consultants_raw"):
        result["consultants"] = _parse_consultants(result["basic_info"]["consultants_raw"])
    
    # 언급 가능 병원 파싱
    if result["basic_info"].get("allowed_hospitals_raw"):
        result["allowed_hospitals"] = _parse_allowed_hospitals(result["basic_info"]["allowed_hospitals_raw"])
    
    # 사후관리 상세 파싱
    if result["basic_info"].get("aftercare_raw"):
        result["aftercare"] = _parse_aftercare(result["basic_info"]["aftercare_raw"])
    
    # raw 데이터 저장
    result["raw_data"] = dict(result["basic_info"])
    
    return result


def _parse_guide_section(guide_section: str, result: Dict):
    """병원 가이드 테이블 파싱"""
    
    # 테이블 행 파싱 - | key | value | 형식
    table_rows = re.findall(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', guide_section)
    
    for key, value in table_rows:
        key = key.strip()
        value = value.strip()
        
        if key == '---' or not key:
            continue
            
        # 기본 정보 매핑
        if '위치' in key or '업체정보' in key:
            result["basic_info"]["location"] = value
        elif '운영시간' in key:
            result["basic_info"]["hours"] = value
        elif '의료진' in key and '소개' in key:
            result["basic_info"]["doctors_raw"] = value
        elif '주력수술' in key:
            result["basic_info"]["specialties_raw"] = value
        elif '상담시간' in key:
            result["basic_info"]["consultation_time"] = value
        elif '상담실장' in key:
            result["basic_info"]["consultants_raw"] = value
        elif '상담과정' in key:
            result["process"] = value
        elif '사후관리' in key:
            result["basic_info"]["aftercare_raw"] = value
        elif '가능' in key and '병원' in key:
            result["basic_info"]["allowed_hospitals_raw"] = value
        elif '불가' in key and '병원' in key:
            result["blocked_hospitals"] = [h.strip() for h in value.split(',') if h.strip()]
        elif 'CCTV' in key:
            result["features"]["cctv"] = value
        elif '마취' in key:
            result["features"]["anesthesia"] = value
        elif '실명제' in key:
            result["features"]["real_name"] = value == 'O' or 'O' in value
        elif '내원치료' in key:
            result["basic_info"]["follow_up"] = value
        elif '주차' in key or '발렛' in key:
            result["basic_info"]["parking"] = value


def _parse_post_care_section(content: str, result: Dict):
    """수술 후 주의사항 파싱"""
    
    # 각 수술 타입별 파싱
    for surgery_type in ['코', '눈', '지방흡입']:
        # 더 넓은 패턴으로 검색
        pattern = rf'\|\s*{surgery_type}\s*\|\s*(.*?)(?=\|\s*(?:코|눈|지방흡입)\s*\||$|\*\*쪽지|\*\*수가표)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            care_text = match.group(1).strip()
            # 테이블 구분자 제거
            care_text = re.sub(r'\|\s*$', '', care_text)
            care_text = care_text.strip()
            if care_text:
                result["post_care"][surgery_type] = care_text


def _parse_price_section(content: str, result: Dict):
    """수가표 섹션 파싱"""
    
    price_match = re.search(r'\*\*수가표\*\*\s*(.*?)(?=!\[|</aside>|$)', content, re.DOTALL)
    if not price_match:
        return
        
    price_text = price_match.group(1).strip()
    
    # 각 원장별 파싱
    for line in price_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # 한상철(H)- 첫코 - 400 ~ 500 형식
        doctor_match = re.match(r'([가-힣]+)\(([A-Z])\)-?\s*(.+)', line)
        if doctor_match:
            doctor_name = doctor_match.group(1)
            doctor_code = f"Dr.{doctor_match.group(2)}"
            procedures_str = doctor_match.group(3)
            
            # 시술-가격 쌍 추출 (/ 로 구분)
            for proc_pair in procedures_str.split('/'):
                proc_match = re.match(r'\s*([가-힣+\s\(\)]+)\s*-\s*(.+)', proc_pair.strip())
                if proc_match:
                    procedure = proc_match.group(1).strip()
                    price = proc_match.group(2).strip()
                    
                    result["price_list"].append({
                        "doctor_name": doctor_name,
                        "doctor_code": doctor_code,
                        "procedure": procedure,
                        "price": price,
                        "price_display": f"{price}만원" if not '만원' in price and not '원' in price else price
                    })


def _parse_doctors(raw_text: str) -> List[Dict]:
    """의료진 정보 파싱"""
    doctors = []
    
    # Dr.H(한상철원장님) 패턴
    dr_pattern = r'Dr\.([A-Z])\(([^)]+)\)\s*([^D]*?)(?=Dr\.|유상수|$)'
    for match in re.finditer(dr_pattern, raw_text, re.DOTALL):
        code = f"Dr.{match.group(1)}"
        name = match.group(2).replace('원장님', '').strip()
        style = match.group(3).strip()
        
        # 줄바꿈 정리
        style = re.sub(r'\s+', ' ', style).strip()
        
        doctors.append({
            "code": code,
            "name": name,
            "style": style,
            "specialties": []
        })
    
    # 유상수원장님 같은 패턴 (Dr. 없는 경우)
    if '유상수' in raw_text and not any(d['name'] == '유상수' for d in doctors):
        doctors.append({
            "code": "Dr.Y",
            "name": "유상수",
            "style": "눈재수술 전문",
            "specialties": ["눈재수술"]
        })
    
    return doctors


def _merge_doctor_specialties(doctors: List[Dict], specialties_raw: str):
    """의료진에 주력수술 정보 병합"""
    
    for line in specialties_raw.split('\n'):
        line = line.strip()
        
        # 한상철원장님(Dr.H) - 첫코, 코재수술 형식
        match = re.match(r'([가-힣]+)(?:원장님)?\s*\(?(Dr\.?[A-Z])?\)?\s*-\s*(.+)', line)
        if match:
            name = match.group(1)
            specialties_str = match.group(3)
            
            # 해당 의사 찾기
            for doc in doctors:
                if doc['name'] == name:
                    # / 또는 , 로 구분된 시술 목록
                    specs = re.split(r'[/,]', specialties_str)
                    doc['specialties'] = [s.strip() for s in specs if s.strip()]
                    break


def _parse_consultants(raw_text: str) -> List[Dict]:
    """상담실장 정보 파싱"""
    consultants = []
    
    # 김소희 29세- 친근한 말투 패턴
    cons_pattern = r'([가-힣]{2,4})\s*(\d{2})세-?\s*([^\n]+)'
    for match in re.finditer(cons_pattern, raw_text):
        name = match.group(1).strip()
        age = int(match.group(2))
        style = match.group(3).strip()
        
        # 다음 사람 이름이 포함되어 있으면 제거
        style = re.split(r'[가-힣]{2,4}\s*\d{2}세', style)[0].strip()
        
        consultants.append({
            "name": name,
            "age": age,
            "style": style
        })
    
    return consultants


def _parse_allowed_hospitals(raw_text: str) -> Dict[str, List[str]]:
    """언급 가능 병원 파싱"""
    allowed = {}
    
    for line in raw_text.split('\n'):
        line = line.strip()
        
        # 이마거상 - 바탕, 아이디 형식
        match = re.match(r'([가-힣]+)\s*-\s*(.+)', line)
        if match:
            category = match.group(1)
            hospitals = [h.strip() for h in match.group(2).split(',') if h.strip()]
            allowed[category] = hospitals
    
    return allowed


def _parse_aftercare(raw_text: str) -> Dict[str, str]:
    """사후관리 정보 파싱"""
    aftercare = {}
    
    for line in raw_text.split('\n'):
        line = line.strip()
        
        # 코성형 > 프락셀레이저 형식
        match = re.match(r'([가-힣]+)\s*>\s*(.+)', line)
        if match:
            surgery = match.group(1)
            care = match.group(2).strip()
            aftercare[surgery] = care
    
    return aftercare


def extract_clinic_name_from_file(filepath: str) -> str:
    """파일명에서 병원명 추출 시도"""
    filename = Path(filepath).stem
    
    # Study_223286f326ff... 형식에서 앞부분만
    if filename.startswith('Study_'):
        # 파일 내용에서 병원명 찾기
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # "윈느성형외과" 같은 병원명 패턴 검색
        hospital_match = re.search(r'([가-힣]+(?:성형외과|의원|병원|피부과|클리닉))', content)
        if hospital_match:
            return hospital_match.group(1)
    
    return filename


# ========================================
# Django 모델 연동 함수
# ========================================

def import_clinic_from_md(filepath: str, clinic_name: Optional[str] = None):
    """
    MD 파일을 파싱하여 ClinicGuide 모델로 저장
    
    Args:
        filepath: MD 파일 경로
        clinic_name: 병원명 (없으면 파일에서 추출)
    
    Returns:
        생성된 ClinicGuide 인스턴스
    """
    from apps.data.models import ClinicGuide
    
    # 파싱
    data = parse_clinic_markdown(filepath)
    
    # 병원명
    name = clinic_name or extract_clinic_name_from_file(filepath)
    
    # 저장
    clinic, created = ClinicGuide.objects.update_or_create(
        name=name,
        defaults={
            'file_path': filepath,
            'location': data["basic_info"].get("location", ""),
            'hours': data["basic_info"].get("hours", ""),
            'parking': data["basic_info"].get("parking", ""),
            'doctors': data["doctors"],
            'consultants': data["consultants"],
            'price_list': data["price_list"],
            'process': data["process"],
            'aftercare': data["aftercare"],
            'post_care': data["post_care"],
            'features': data["features"],
            'allowed_hospitals': data["allowed_hospitals"],
            'blocked_hospitals': data["blocked_hospitals"],
            'raw_data': data["raw_data"],
        }
    )
    
    return clinic


if __name__ == "__main__":
    # 테스트
    import sys
    
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        result = parse_clinic_markdown(filepath)
        print(json.dumps(result, ensure_ascii=False, indent=2))
