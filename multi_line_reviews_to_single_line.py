# split_reviews_by_bracket.py
input_path = "reviews2.txt"
output_path = "singleline_reviews.txt"

with open(input_path, encoding="utf-8") as fin:
    text = fin.read()

import re

# "[로 시작"하는 곳마다 분리
splits = re.split(r'(?=\[)', text)

# 블록을 한 줄로 합치고, 빈 블록은 제거
reviews = [block.replace('\n', ' ').replace('\r', ' ').strip() for block in splits if block.strip()]

with open(output_path, "w", encoding="utf-8") as fout:
    for r in reviews:
        fout.write(r + "\n")

print(f"{len(reviews)}개 리뷰를 한 줄로 저장 → {output_path}")