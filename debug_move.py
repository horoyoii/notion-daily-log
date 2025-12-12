#!/usr/bin/env python3
"""
페이지 이동 디버깅
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('NOTION_API_KEY')
database_id = os.getenv('DATA_SOURCE_ID')
archive_page_id = "1cb5aae782eb807c81cef3bd6e2345ee"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# 1. 11월 10일 페이지 찾기
print("=" * 80)
print("1. 페이지 검색")
print("=" * 80)

url = f"https://api.notion.com/v1/databases/{database_id}/query"
payload = {
    "filter": {
        "property": "이름",
        "title": {
            "equals": "2025년 11월 10일 (월)"
        }
    }
}

response = requests.post(url, headers=headers, json=payload)
results = response.json().get('results', [])

if not results:
    print("페이지를 찾을 수 없습니다.")
    exit(1)

page = results[0]
page_id = page['id']

print(f"페이지 ID: {page_id}")
print(f"\n현재 parent:")
print(f"  Type: {page['parent']['type']}")
print(f"  Database ID: {page['parent'].get('database_id')}")

# 2. 아카이브 페이지 정보 확인
print("\n" + "=" * 80)
print("2. 아카이브 페이지 정보")
print("=" * 80)

url = f"https://api.notion.com/v1/pages/{archive_page_id}"
response = requests.get(url, headers=headers)
archive_page = response.json()

print(f"Archive Page ID: {archive_page['id']}")
print(f"Archive Parent Type: {archive_page['parent']['type']}")

# 3. 페이지 이동 시도
print("\n" + "=" * 80)
print("3. 페이지 이동 시도")
print("=" * 80)

url = f"https://api.notion.com/v1/pages/{page_id}"
payload = {
    "parent": {
        "page_id": archive_page_id
    }
}

print(f"Request Payload:")
print(f"  {payload}")

response = requests.patch(url, headers=headers, json=payload)

print(f"\nResponse Status: {response.status_code}")
print(f"Response Body:")
print(response.text)

if response.status_code == 200:
    result = response.json()
    print("\n✅ 이동 성공!")
    print(f"새 parent: {result['parent']}")
else:
    print("\n❌ 이동 실패!")
