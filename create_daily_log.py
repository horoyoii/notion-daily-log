#!/usr/bin/env python3
"""
Notion 업무로그 자동 생성 스크립트
매일 템플릿 페이지를 복제하여 당일 날짜의 업무로그를 생성합니다.
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('execution.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NotionWorkLogCreator:
    """Notion 업무로그 생성기"""
    
    def __init__(self, api_key: str, template_page_id: str, data_source_id: str):
        self.api_key = api_key
        self.template_page_id = template_page_id
        self.data_source_id = data_source_id
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
    
    def get_korean_date_info(self, date: datetime = None) -> dict:
        """한국 날짜 정보 반환"""
        if date is None:
            # 한국 시간 기준 (UTC+9)
            date = datetime.utcnow() + timedelta(hours=9)

        weekday_names = ['월', '화', '수', '목', '금', '토', '일']
        weekday = weekday_names[date.weekday()]
        is_weekend = date.weekday() >= 5  # 5=토, 6=일

        return {
            'year': date.year,
            'month': date.month,
            'day': date.day,
            'weekday': weekday,
            'is_weekend': is_weekend,
            'formatted_title': f"{date.year}년 {date.month}월 {date.day}일 ({weekday})",
            'iso_date': date.strftime('%Y-%m-%d')
        }

    def get_next_business_day(self, date: datetime) -> datetime:
        """다음 업무일 반환 (주말 건너뛰기)"""
        next_day = date + timedelta(days=1)
        # 토요일이면 월요일로, 일요일이면 월요일로
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day
    
    def duplicate_page(self) -> str:
        """템플릿 페이지 복제 (하위 페이지 포함)"""
        logger.info(f"템플릿 페이지 복제 시작: {self.template_page_id}")
        
        url = f"{self.base_url}/pages/{self.template_page_id}/duplicate"
        
        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            
            result = response.json()
            new_page_id = result['id']
            
            logger.info(f"페이지 복제 성공: {new_page_id}")
            return new_page_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"페이지 복제 실패: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"응답 내용: {e.response.text}")
            raise
    
    def update_page_properties(self, page_id: str, date_info: dict):
        """페이지 속성 업데이트 (이름 및 작성일)"""
        logger.info(f"페이지 속성 업데이트: {page_id}")
        
        url = f"{self.base_url}/pages/{page_id}"
        
        payload = {
            "properties": {
                "이름": {
                    "title": [
                        {
                            "text": {
                                "content": date_info['formatted_title']
                            }
                        }
                    ]
                },
                "작성일": {
                    "date": {
                        "start": date_info['iso_date']
                    }
                }
            }
        }
        
        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            logger.info(f"페이지 속성 업데이트 성공: {date_info['formatted_title']}")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"페이지 속성 업데이트 실패: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"응답 내용: {e.response.text}")
            raise
    
    def check_existing_log(self, date_info: dict) -> bool:
        """해당 날짜의 로그가 이미 존재하는지 확인"""
        logger.info(f"기존 로그 확인: {date_info['formatted_title']}")
        
        url = f"{self.base_url}/databases/{self.data_source_id}/query"
        
        payload = {
            "filter": {
                "property": "이름",
                "title": {
                    "equals": date_info['formatted_title']
                }
            }
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            results = response.json().get('results', [])
            
            if results:
                logger.warning(f"이미 존재하는 로그: {date_info['formatted_title']}")
                return True
            
            return False
            
        except requests.exceptions.RequestException as e:
            logger.error(f"기존 로그 확인 실패: {str(e)}")
            # 확인 실패시 안전하게 진행
            return False
    
    def create_work_log(self, date: datetime):
        """특정 날짜의 업무로그 생성"""
        import time

        date_info = self.get_korean_date_info(date)

        # 주말인 경우 건너뛰기
        if date_info['is_weekend']:
            logger.info(f"{date_info['formatted_title']}은(는) 주말이므로 생성을 건너뜁니다.")
            return

        logger.info(f"=== {date_info['formatted_title']} 업무로그 생성 시작 ===")

        # 기존 로그 확인
        if self.check_existing_log(date_info):
            logger.info("이미 존재하는 로그로 인해 생성을 건너뜁니다.")
            return

        # 템플릿 페이지 복제 (하위 페이지 자동 포함)
        new_page_id = self.duplicate_page()

        # 복제 완료까지 대기
        logger.info("복제 완료 대기 중... (5초)")
        time.sleep(5)

        # 페이지 속성 업데이트
        self.update_page_properties(new_page_id, date_info)

        logger.info(f"=== {date_info['formatted_title']} 업무로그 생성 완료 ===")
        logger.info(f"페이지 ID: {new_page_id}")
        logger.info(f"URL: https://www.notion.so/{new_page_id.replace('-', '')}")

    def create_daily_log(self):
        """일일 업무로그 생성 (당일 + 다음 업무일)"""
        try:
            # 한국 시간 기준 현재 날짜
            today = datetime.utcnow() + timedelta(hours=9)

            # 1. 당일 업무로그 생성
            logger.info("===== 당일 업무로그 생성 =====")
            self.create_work_log(today)

            # 2. 다음 업무일 업무로그 생성
            next_business_day = self.get_next_business_day(today)
            logger.info("\n===== 다음 업무일 업무로그 생성 =====")
            self.create_work_log(next_business_day)

            logger.info("\n===== 모든 업무로그 생성 완료 =====")

        except Exception as e:
            logger.error(f"업무로그 생성 중 오류 발생: {str(e)}")
            raise


def main():
    """메인 함수"""
    # 환경변수에서 설정 로드
    api_key = os.getenv('NOTION_API_KEY')
    template_page_id = os.getenv('TEMPLATE_PAGE_ID')
    data_source_id = os.getenv('DATA_SOURCE_ID')
    
    # 필수 환경변수 확인
    if not all([api_key, template_page_id, data_source_id]):
        logger.error("필수 환경변수가 설정되지 않았습니다.")
        logger.error("NOTION_API_KEY, TEMPLATE_PAGE_ID, DATA_SOURCE_ID를 확인하세요.")
        sys.exit(1)
    
    # 업무로그 생성기 실행
    creator = NotionWorkLogCreator(api_key, template_page_id, data_source_id)
    creator.create_daily_log()


if __name__ == "__main__":
    main()
