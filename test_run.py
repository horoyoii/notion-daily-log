#!/usr/bin/env python3
"""
로컬 테스트 실행 (자동 진행)
확인 없이 바로 실행합니다.
"""

import os
from dotenv import load_dotenv

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

print("=" * 60)
print("🚀 Notion 업무로그 자동 생성 테스트")
print("=" * 60)
print(f"✅ API Key: {os.getenv('NOTION_API_KEY')[:20]}...")
print(f"✅ Template: {os.getenv('TEMPLATE_PAGE_ID')}")
print(f"✅ Database: {os.getenv('DATA_SOURCE_ID')}")
print("=" * 60)
print()

# 메인 함수 실행
from create_daily_log import main

try:
    main()
    print()
    print("=" * 60)
    print("✅ 테스트 완료!")
    print("=" * 60)
except Exception as e:
    print()
    print("=" * 60)
    print(f"❌ 테스트 실패: {str(e)}")
    print("=" * 60)
    import traceback
    traceback.print_exc()
    exit(1)
