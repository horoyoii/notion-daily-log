#!/usr/bin/env python3
"""
블록 타입 분석 스크립트
템플릿 페이지의 모든 블록을 분석하여 어떤 타입들이 있는지 확인합니다.
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('NOTION_API_KEY')
template_page_id = os.getenv('TEMPLATE_PAGE_ID')

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 블록 가져오기
url = f"https://api.notion.com/v1/blocks/{template_page_id}/children"
response = requests.get(url, headers=headers)
response.raise_for_status()

data = response.json()
blocks = data.get('results', [])

print(f"총 블록 수: {len(blocks)}\n")
print("=" * 80)

for i, block in enumerate(blocks):
    block_type = block.get('type')
    block_id = block.get('id')
    has_children = block.get('has_children', False)

    print(f"블록 #{i}: {block_type}")
    print(f"  ID: {block_id}")
    print(f"  Has Children: {has_children}")

    # 블록 타입별 내용 확인
    type_data = block.get(block_type, {})

    # rich_text가 있는 경우
    if 'rich_text' in type_data:
        text_content = type_data.get('rich_text', [])
        if text_content:
            text = text_content[0].get('plain_text', '')
            print(f"  Text: {text[:50]}...")

    # 기타 주요 속성들
    for key in type_data.keys():
        if key not in ['rich_text']:
            value = type_data[key]
            if isinstance(value, (str, int, bool)):
                print(f"  {key}: {value}")

    print()

# 31번째 블록 상세 분석
if len(blocks) > 31:
    print("=" * 80)
    print("31번째 블록 상세 정보:")
    print("=" * 80)
    print(json.dumps(blocks[31], indent=2, ensure_ascii=False))
