#!/usr/bin/env python3
"""
지난주 업무로그 아카이브 스크립트
매주 월요일 실행: 지난주 (월~일) 모든 페이지를 아카이브 페이지로 이동
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('archive_execution.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NotionArchiver:
    """Notion 업무로그 아카이브"""

    def __init__(self, api_key: str, database_id: str, archive_page_id: str):
        self.api_key = api_key
        self.database_id = database_id
        self.archive_page_id = archive_page_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

    def get_last_week_dates(self) -> list:
        """지난주 날짜 목록 반환 (월~일)"""
        # 한국 시간 기준 오늘
        today = datetime.utcnow() + timedelta(hours=9)

        # 지난주 월요일 계산
        # 오늘이 월요일(0)이면 7일 전, 화요일(1)이면 8일 전...
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)

        # 지난주 월~일 (7일)
        last_week_dates = []
        for i in range(7):
            date = last_monday + timedelta(days=i)
            last_week_dates.append(date)

        return last_week_dates

    def get_korean_date_title(self, date: datetime) -> str:
        """한국 날짜 형식 제목 반환"""
        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
        weekday = weekday_names[date.weekday()]
        return f"{date.year}년 {date.month}월 {date.day}일 ({weekday})"

    def find_pages_by_dates(self, dates: list) -> list:
        """날짜 목록에 해당하는 페이지들 찾기"""
        logger.info(f"페이지 검색 시작: {len(dates)}일")

        found_pages = []

        for date in dates:
            title = self.get_korean_date_title(date)

            url = f"{self.base_url}/databases/{self.database_id}/query"
            payload = {
                "filter": {
                    "property": "이름",
                    "title": {
                        "equals": title
                    }
                }
            }

            try:
                response = requests.post(url, headers=self.headers, json=payload)
                response.raise_for_status()

                results = response.json().get('results', [])

                if results:
                    page = results[0]  # 첫 번째 결과만 사용
                    found_pages.append({
                        'id': page['id'],
                        'title': title,
                        'date': date
                    })
                    logger.info(f"✅ 발견: {title}")
                else:
                    logger.warning(f"⚠️  없음: {title}")

            except requests.exceptions.RequestException as e:
                logger.error(f"❌ 검색 실패 ({title}): {str(e)}")

        return found_pages

    def move_page_to_archive(self, page_id: str, page_title: str):
        """페이지를 아카이브 페이지 하위로 이동"""
        logger.info(f"페이지 이동 시작: {page_title}")

        url = f"{self.base_url}/pages/{page_id}"

        # parent를 아카이브 페이지로 변경
        payload = {
            "parent": {
                "page_id": self.archive_page_id
            }
        }

        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()

            logger.info(f"✅ 이동 완료: {page_title}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 이동 실패 ({page_title}): {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"   응답: {e.response.text}")
            return False

    def archive_last_week(self):
        """지난주 모든 페이지 아카이브"""
        logger.info("=" * 80)
        logger.info("지난주 업무로그 아카이브 시작")
        logger.info("=" * 80)

        # 1. 지난주 날짜 계산
        last_week_dates = self.get_last_week_dates()

        logger.info(f"\n아카이브 대상 기간:")
        logger.info(f"  시작: {self.get_korean_date_title(last_week_dates[0])}")
        logger.info(f"  종료: {self.get_korean_date_title(last_week_dates[-1])}")
        logger.info(f"  총 {len(last_week_dates)}일\n")

        # 2. 해당 날짜의 페이지 찾기
        pages = self.find_pages_by_dates(last_week_dates)

        logger.info(f"\n발견된 페이지: {len(pages)}개")

        if not pages:
            logger.info("아카이브할 페이지가 없습니다.")
            return

        # 3. 페이지 이동
        logger.info(f"\n아카이브 페이지로 이동 시작:")
        logger.info(f"대상: https://www.notion.so/{self.archive_page_id.replace('-', '')}\n")

        success_count = 0
        fail_count = 0

        # 날짜 역순으로 이동 (최신이 위로 오도록)
        for page in reversed(pages):
            import time
            time.sleep(0.5)  # API 속도 제한 방지

            if self.move_page_to_archive(page['id'], page['title']):
                success_count += 1
            else:
                fail_count += 1

        # 4. 결과 요약
        logger.info("\n" + "=" * 80)
        logger.info("아카이브 완료")
        logger.info("=" * 80)
        logger.info(f"성공: {success_count}개")
        logger.info(f"실패: {fail_count}개")
        logger.info(f"전체: {len(pages)}개")


def main():
    """메인 함수"""
    # 환경변수에서 설정 로드
    api_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('DATA_SOURCE_ID')
    archive_page_id = os.getenv('ARCHIVE_PAGE_ID', '1cb5aae782eb807c81cef3bd6e2345ee')

    # 필수 환경변수 확인
    if not all([api_key, database_id]):
        logger.error("필수 환경변수가 설정되지 않았습니다.")
        logger.error("NOTION_API_KEY, DATA_SOURCE_ID를 확인하세요.")
        sys.exit(1)

    # 아카이브 실행
    archiver = NotionArchiver(api_key, database_id, archive_page_id)
    archiver.archive_last_week()


if __name__ == "__main__":
    main()
