#!/usr/bin/env python3
"""
아카이브 기능 테스트
실제 실행 전 날짜 계산과 페이지 검색만 테스트
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv('NOTION_API_KEY')
database_id = os.getenv('DATA_SOURCE_ID')
archive_page_id = os.getenv('ARCHIVE_PAGE_ID', '1cb5aae782eb807c81cef3bd6e2345ee')

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

print("=" * 80)
print("📅 아카이브 기능 테스트")
print("=" * 80)

# 1. 지난주 날짜 계산
today = datetime.utcnow() + timedelta(hours=9)
print(f"\n오늘: {today.strftime('%Y년 %m월 %d일 (%a)')}")

days_since_monday = today.weekday()
last_monday = today - timedelta(days=days_since_monday + 7)

print(f"\n지난주 기간:")
print(f"  시작: {last_monday.strftime('%Y년 %m월 %d일 (월)')}")
print(f"  종료: {(last_monday + timedelta(days=6)).strftime('%Y년 %m월 %d일 (일)')}")

# 2. 지난주 날짜 목록
weekday_names = ['월', '화', '수', '목', '금', '토', '일']
last_week_dates = []

print(f"\n대상 날짜:")
for i in range(7):
    date = last_monday + timedelta(days=i)
    weekday = weekday_names[date.weekday()]
    title = f"{date.year}년 {date.month}월 {date.day}일 ({weekday})"
    last_week_dates.append((date, title))
    print(f"  {i+1}. {title}")

# 3. 페이지 검색
print(f"\n페이지 검색 중...")
found_pages = []

for date, title in last_week_dates:
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {
        "filter": {
            "property": "이름",
            "title": {
                "equals": title
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    results = response.json().get('results', [])

    if results:
        found_pages.append({
            'title': title,
            'id': results[0]['id']
        })
        print(f"  ✅ {title}")
    else:
        print(f"  ❌ {title} (없음)")

# 4. 아카이브 페이지 정보
print(f"\n아카이브 대상 페이지:")
print(f"  ID: {archive_page_id}")
print(f"  URL: https://www.notion.so/{archive_page_id.replace('-', '')}")

# 5. 요약
print(f"\n" + "=" * 80)
print(f"요약")
print("=" * 80)
print(f"검색 대상: {len(last_week_dates)}일")
print(f"발견된 페이지: {len(found_pages)}개")
print(f"이동할 페이지: {len(found_pages)}개")

if found_pages:
    print(f"\n⚠️  실제 아카이브를 실행하려면:")
    print(f"   python3 archive_last_week.py")
else:
    print(f"\n✅ 아카이브할 페이지가 없습니다.")
