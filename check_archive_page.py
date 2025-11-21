#!/usr/bin/env python3
"""
아카이브 페이지 정보 확인
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('NOTION_API_KEY')
archive_page_id = "1cb5aae782eb807c81cef3bd6e2345ee"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 아카이브 페이지 정보 조회
url = f"https://api.notion.com/v1/pages/{archive_page_id}"
response = requests.get(url, headers=headers)
response.raise_for_status()

page_data = response.json()

print("=" * 80)
print("아카이브 페이지 정보")
print("=" * 80)
print(f"Page ID: {page_data.get('id')}")
print(f"Created: {page_data.get('created_time')}")
print(f"Parent Type: {page_data.get('parent', {}).get('type')}")

# 제목 추출
properties = page_data.get('properties', {})
for prop_name, prop_data in properties.items():
    prop_type = prop_data.get('type')
    if prop_type == 'title':
        title_array = prop_data.get('title', [])
        if title_array:
            title = title_array[0].get('text', {}).get('content', '제목 없음')
            print(f"Title: {title}")

# 하위 블록 확인
print("\n하위 블록:")
url = f"https://api.notion.com/v1/blocks/{archive_page_id}/children"
response = requests.get(url, headers=headers)
response.raise_for_status()

blocks_data = response.json()
blocks = blocks_data.get('results', [])

print(f"총 {len(blocks)}개 블록")
for i, block in enumerate(blocks[:5]):
    block_type = block.get('type')
    print(f"  {i+1}. {block_type}")

    if block_type == 'child_page':
        title = block.get('child_page', {}).get('title', '제목 없음')
        print(f"     → {title}")
