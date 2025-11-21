#!/usr/bin/env python3
"""
로컬 디버깅 테스트 스크립트
상세한 디버깅 정보와 함께 스크립트를 실행합니다.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def check_environment():
    """환경 변수 확인"""
    print("=" * 60)
    print("🔍 환경 변수 확인")
    print("=" * 60)

    required_vars = ['NOTION_API_KEY', 'TEMPLATE_PAGE_ID', 'DATA_SOURCE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("❌ 다음 환경변수가 설정되지 않았습니다:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n.env 파일을 확인하세요.")
        return False

    print("✅ 모든 환경변수 확인 완료")
    print(f"   NOTION_API_KEY: {os.getenv('NOTION_API_KEY')[:20]}...")
    print(f"   TEMPLATE_PAGE_ID: {os.getenv('NOTION_API_KEY')}")
    print(f"   DATA_SOURCE_ID: {os.getenv('DATA_SOURCE_ID')}")
    print()
    return True

def test_notion_connection():
    """Notion API 연결 테스트"""
    print("=" * 60)
    print("🔌 Notion API 연결 테스트")
    print("=" * 60)

    import requests

    api_key = os.getenv('NOTION_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    try:
        # 사용자 정보 조회로 API 키 유효성 확인
        response = requests.get("https://api.notion.com/v1/users/me", headers=headers)
        response.raise_for_status()

        user_data = response.json()
        print(f"✅ API 연결 성공!")
        print(f"   Bot Name: {user_data.get('name', 'N/A')}")
        print(f"   Bot ID: {user_data.get('id', 'N/A')}")
        print()
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ API 연결 실패: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   응답 코드: {e.response.status_code}")
            print(f"   응답 내용: {e.response.text}")
        print()
        return False

def test_template_access():
    """템플릿 페이지 접근 테스트"""
    print("=" * 60)
    print("📄 템플릿 페이지 접근 테스트")
    print("=" * 60)

    import requests

    api_key = os.getenv('NOTION_API_KEY')
    template_page_id = os.getenv('TEMPLATE_PAGE_ID')

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    try:
        # 템플릿 페이지 정보 조회
        url = f"https://api.notion.com/v1/pages/{template_page_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        page_data = response.json()
        print(f"✅ 템플릿 페이지 접근 성공!")
        print(f"   Page ID: {page_data.get('id')}")
        print(f"   Created: {page_data.get('created_time')}")
        print()

        # 템플릿 페이지의 블록 수 확인
        url = f"https://api.notion.com/v1/blocks/{template_page_id}/children"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        blocks_data = response.json()
        blocks = blocks_data.get('results', [])
        child_pages = [b for b in blocks if b.get('type') == 'child_page']

        print(f"📊 템플릿 구조:")
        print(f"   총 블록 수: {len(blocks)}개")
        print(f"   하위 페이지 수: {len(child_pages)}개")

        if child_pages:
            print(f"\n   하위 페이지 목록:")
            for i, child in enumerate(child_pages, 1):
                title = child.get('child_page', {}).get('title', '제목 없음')
                print(f"   {i}. {title}")
        print()

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ 템플릿 페이지 접근 실패: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   응답 코드: {e.response.status_code}")
            print(f"   응답 내용: {e.response.text}")
        print()
        return False

def test_database_access():
    """데이터베이스 접근 테스트"""
    print("=" * 60)
    print("🗄️  데이터베이스 접근 테스트")
    print("=" * 60)

    import requests

    api_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('DATA_SOURCE_ID')

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    try:
        # 데이터베이스 정보 조회
        url = f"https://api.notion.com/v1/databases/{database_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        db_data = response.json()
        print(f"✅ 데이터베이스 접근 성공!")
        print(f"   Database ID: {db_data.get('id')}")

        # 데이터베이스 속성 확인
        properties = db_data.get('properties', {})
        print(f"\n   데이터베이스 속성:")
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get('type')
            print(f"   - {prop_name}: {prop_type}")

        # 기존 페이지 수 확인
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        response = requests.post(url, headers=headers, json={"page_size": 10})
        response.raise_for_status()

        query_data = response.json()
        results = query_data.get('results', [])
        print(f"\n   기존 페이지 수: {len(results)}개 (최근 10개)")

        if results:
            print(f"\n   최근 페이지:")
            for i, page in enumerate(results[:5], 1):
                title_prop = page.get('properties', {}).get('이름', {})
                title_array = title_prop.get('title', [])
                title = title_array[0].get('text', {}).get('content', '제목 없음') if title_array else '제목 없음'
                print(f"   {i}. {title}")
        print()

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ 데이터베이스 접근 실패: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   응답 코드: {e.response.status_code}")
            print(f"   응답 내용: {e.response.text}")
        print()
        return False

def run_main_script():
    """메인 스크립트 실행"""
    print("=" * 60)
    print("🚀 메인 스크립트 실행")
    print("=" * 60)
    print()

    from create_daily_log import main

    try:
        main()
        print()
        print("=" * 60)
        print("✅ 스크립트 실행 완료!")
        print("=" * 60)
        return True
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ 스크립트 실행 실패: {str(e)}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("🧪 Notion 업무로그 로컬 테스트 & 디버깅")
    print("=" * 60)
    print()

    # 1. 환경 변수 확인
    if not check_environment():
        sys.exit(1)

    # 2. Notion API 연결 테스트
    if not test_notion_connection():
        sys.exit(1)

    # 3. 템플릿 페이지 접근 테스트
    if not test_template_access():
        sys.exit(1)

    # 4. 데이터베이스 접근 테스트
    if not test_database_access():
        sys.exit(1)

    # 5. 실제 스크립트 실행 여부 확인
    print("=" * 60)
    print("⚠️  주의: 실제로 페이지를 생성합니다!")
    print("=" * 60)
    response = input("\n계속하시겠습니까? (y/N): ")

    if response.lower() != 'y':
        print("\n테스트를 취소했습니다.")
        sys.exit(0)

    print()

    # 6. 메인 스크립트 실행
    run_main_script()

if __name__ == "__main__":
    main()
