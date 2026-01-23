"""
리뷰 텍스트만 받아 파인튜닝용 JSONL로 변환하는 간단 스크립트
- 최소 필드: 시술명(혹은 기본값), 리뷰텍스트만 있으면 동작합니다.
- output: ft_train.jsonl 파일 생성
"""
from apps.ml.services.ft_prompt_builder import build_ft_record, make_jsonl_line
import sys
import os

# 리뷰 리스트를 파일 또는 코드에서 바로 불러오는 예시
# 리뷰만 한 줄씩 있는 텍스트 파일을 사용
input_path = sys.argv[1] if len(sys.argv) > 1 else "reviews.txt"  # 예: reviews.txt
output_path = sys.argv[2] if len(sys.argv) > 2 else "ft_train.jsonl"

if not os.path.isfile(input_path):
    print(f"리뷰 파일이 존재하지 않습니다: {input_path}")
    sys.exit(1)

# 시술명 기본값 (없으면 "리뷰 시술" 등으로 사용)
default_procedure = "리뷰 시술"

records = []

with open(input_path, encoding="utf-8") as fin:
    for line in fin:
        text = line.strip()
        if not text:
            continue
        # 최소 정보: 시술명 + 리뷰 본문
        record = build_ft_record(
            procedure=default_procedure,
            target_review_text=text
        )
        records.append(make_jsonl_line(record))

with open(output_path, "w", encoding="utf-8") as fout:
    for line in records:
        fout.write(line + "\n")

print(f"리뷰 {len(records)}건을 {output_path} 파일로 저장 완료!")
