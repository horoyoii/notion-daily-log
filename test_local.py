#!/usr/bin/env python3
"""
로컬 테스트용 스크립트
.env 파일을 로드하여 create_daily_log.py를 실행합니다.
"""

import os
from dotenv import load_dotenv
from create_daily_log import main

# .env 파일 로드
load_dotenv()

# 환경변수 확인
required_vars = ['NOTION_API_KEY', 'TEMPLATE_PAGE_ID', 'DATA_SOURCE_ID']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print("❌ 다음 환경변수가 설정되지 않았습니다:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\n.env 파일을 확인하세요.")
    exit(1)

print("✅ 환경변수 로드 완료")
print(f"   NOTION_API_KEY: {os.getenv('NOTION_API_KEY')[:20]}...")
print(f"   TEMPLATE_PAGE_ID: {os.getenv('TEMPLATE_PAGE_ID')}")
print(f"   DATA_SOURCE_ID: {os.getenv('DATA_SOURCE_ID')}")
print()

# 메인 함수 실행
if __name__ == "__main__":
    main()
