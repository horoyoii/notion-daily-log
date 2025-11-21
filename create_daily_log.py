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
    
    def get_page_blocks(self, page_id: str) -> list:
        """페이지의 모든 블록 가져오기"""
        logger.info(f"페이지 블록 조회: {page_id}")

        url = f"{self.base_url}/blocks/{page_id}/children"
        all_blocks = []

        try:
            has_more = True
            start_cursor = None

            while has_more:
                params = {}
                if start_cursor:
                    params['start_cursor'] = start_cursor

                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()
                all_blocks.extend(data.get('results', []))
                has_more = data.get('has_more', False)
                start_cursor = data.get('next_cursor')

            logger.info(f"블록 조회 완료: {len(all_blocks)}개")
            return all_blocks

        except requests.exceptions.RequestException as e:
            logger.error(f"블록 조회 실패: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"응답 내용: {e.response.text}")
            raise

    def create_page_in_database(self, date_info: dict) -> str:
        """데이터베이스에 새 페이지 생성"""
        logger.info(f"새 페이지 생성: {date_info['formatted_title']}")

        url = f"{self.base_url}/pages"

        payload = {
            "parent": {
                "database_id": self.data_source_id
            },
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
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()

            result = response.json()
            new_page_id = result['id']

            logger.info(f"페이지 생성 성공: {new_page_id}")
            return new_page_id

        except requests.exceptions.RequestException as e:
            logger.error(f"페이지 생성 실패: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"응답 내용: {e.response.text}")
            raise

    def clean_block_for_copy(self, block: dict) -> dict:
        """블록 데이터를 복사 가능한 형태로 정리"""
        block_type = block.get('type')
        if not block_type:
            return None

        # child_page, child_database는 별도로 처리하므로 제외
        if block_type in ['child_page', 'child_database']:
            return None

        # 복사할 수 없는 블록 타입들
        unsupported_blocks = ['link_preview', 'unsupported']
        if block_type in unsupported_blocks:
            logger.warning(f"지원하지 않는 블록 타입: {block_type}")
            return None

        # 기본 블록 구조
        cleaned_block = {
            'type': block_type,
            block_type: {}
        }

        # 블록 타입별 데이터 복사
        original_content = block.get(block_type, {})

        # 빈 블록 타입 (divider, breadcrumb, table_of_contents 등)
        empty_block_types = ['divider', 'breadcrumb', 'table_of_contents']
        if block_type in empty_block_types:
            # 빈 객체만 필요
            return cleaned_block

        # rich_text가 있는 경우 복사
        if 'rich_text' in original_content:
            cleaned_block[block_type]['rich_text'] = original_content['rich_text']

        # 다른 속성들도 복사 (read-only 필드는 제외)
        readonly_fields = ['id', 'created_time', 'last_edited_time', 'created_by', 'last_edited_by', 'has_children', 'archived', 'parent']
        for key, value in original_content.items():
            if key not in readonly_fields and key not in cleaned_block[block_type]:
                cleaned_block[block_type][key] = value

        return cleaned_block

    def copy_block_children(self, source_block_id: str, target_block_id: str):
        """블록의 자식 블록들을 재귀적으로 복사"""
        logger.info(f"자식 블록 복사: {source_block_id} -> {target_block_id}")

        # 자식 블록 가져오기
        child_blocks = self.get_page_blocks(source_block_id)

        if not child_blocks:
            return

        # 자식 블록들을 대상 블록에 추가
        self.copy_blocks_to_page(target_block_id, child_blocks)

    def copy_blocks_to_page(self, target_page_id: str, blocks: list):
        """블록들을 대상 페이지로 순서대로 복사 (일반 블록 + child_page 포함)"""
        if not blocks:
            logger.info("복사할 블록이 없습니다.")
            return

        import time
        logger.info(f"블록 복사 시작: {len(blocks)}개 (순서 유지)")

        for block in blocks:
            block_type = block.get('type')

            # child_page는 별도로 처리
            if block_type == 'child_page':
                logger.info(f"하위 페이지 발견 (순서 유지): {block.get('child_page', {}).get('title', '제목 없음')}")
                time.sleep(0.5)
                try:
                    self.copy_child_page(block['id'], target_page_id)
                except Exception as e:
                    logger.error(f"하위 페이지 복사 실패: {str(e)}")
                    # 계속 진행
                continue

            # child_database도 별도 처리 (현재는 스킵)
            if block_type == 'child_database':
                logger.warning(f"child_database는 현재 지원하지 않습니다: {block['id']}")
                continue

            # 일반 블록 복사
            cleaned_block = self.clean_block_for_copy(block)
            if not cleaned_block:
                continue

            # 단일 블록 추가
            url = f"{self.base_url}/blocks/{target_page_id}/children"
            payload = {
                "children": [cleaned_block]
            }

            try:
                response = requests.patch(url, headers=self.headers, json=payload)
                response.raise_for_status()

                result = response.json()
                created_blocks = result.get('results', [])

                if created_blocks:
                    created_block = created_blocks[0]
                    logger.info(f"블록 복사 완료: {block_type}")

                    # 자식 블록이 있는 경우 재귀적으로 복사
                    if block.get('has_children'):
                        original_block_id = block['id']
                        created_block_id = created_block['id']
                        logger.info(f"중첩 블록 복사 시작: {block_type}")

                        time.sleep(0.3)

                        try:
                            self.copy_block_children(original_block_id, created_block_id)
                        except Exception as e:
                            logger.error(f"중첩 블록 복사 실패: {str(e)}")
                            # 계속 진행

                # API 속도 제한 방지
                time.sleep(0.3)

            except requests.exceptions.RequestException as e:
                logger.error(f"블록 복사 실패 ({block_type}): {str(e)}")
                if hasattr(e.response, 'text'):
                    logger.error(f"응답 내용: {e.response.text}")
                # 계속 진행

        logger.info(f"모든 블록 복사 완료")

    def get_child_pages(self, page_id: str) -> list:
        """페이지의 모든 하위 페이지 가져오기"""
        logger.info(f"하위 페이지 조회: {page_id}")

        url = f"{self.base_url}/blocks/{page_id}/children"
        child_pages = []

        try:
            has_more = True
            start_cursor = None

            while has_more:
                params = {}
                if start_cursor:
                    params['start_cursor'] = start_cursor

                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()

                data = response.json()
                blocks = data.get('results', [])

                # child_page 타입의 블록만 필터링
                for block in blocks:
                    if block.get('type') == 'child_page':
                        child_pages.append(block)

                has_more = data.get('has_more', False)
                start_cursor = data.get('next_cursor')

            logger.info(f"하위 페이지 조회 완료: {len(child_pages)}개")
            return child_pages

        except requests.exceptions.RequestException as e:
            logger.error(f"하위 페이지 조회 실패: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"응답 내용: {e.response.text}")
            return []

    def create_child_page(self, parent_page_id: str, title: str) -> str:
        """하위 페이지 생성"""
        logger.info(f"하위 페이지 생성: {title}")

        url = f"{self.base_url}/pages"

        payload = {
            "parent": {
                "page_id": parent_page_id
            },
            "properties": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            }
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()

            result = response.json()
            new_page_id = result['id']

            logger.info(f"하위 페이지 생성 성공: {new_page_id}")
            return new_page_id

        except requests.exceptions.RequestException as e:
            logger.error(f"하위 페이지 생성 실패: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"응답 내용: {e.response.text}")
            raise

    def copy_child_page(self, source_page_id: str, target_parent_id: str):
        """하위 페이지를 재귀적으로 복사"""
        import time

        logger.info(f"하위 페이지 복사 시작: {source_page_id}")

        try:
            # 1. 원본 페이지 정보 가져오기
            url = f"{self.base_url}/pages/{source_page_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            source_page = response.json()

            # 페이지 제목 추출
            title_property = source_page.get('properties', {}).get('title', {})
            title_array = title_property.get('title', [])
            title = title_array[0].get('text', {}).get('content', '제목 없음') if title_array else '제목 없음'

            # 2. 새 하위 페이지 생성
            new_page_id = self.create_child_page(target_parent_id, title)

            # 약간의 지연
            time.sleep(0.5)

            # 3. 원본 페이지의 블록 복사
            source_blocks = self.get_page_blocks(source_page_id)
            if source_blocks:
                self.copy_blocks_to_page(new_page_id, source_blocks)

            # 약간의 지연
            time.sleep(0.5)

            # 4. 하위 페이지의 하위 페이지들도 재귀적으로 복사
            child_pages = self.get_child_pages(source_page_id)
            for child_page in child_pages:
                child_page_id = child_page['id']
                time.sleep(0.5)
                self.copy_child_page(child_page_id, new_page_id)

            logger.info(f"하위 페이지 복사 완료: {title}")

        except Exception as e:
            logger.error(f"하위 페이지 복사 실패: {str(e)}")
            # 하위 페이지 복사 실패는 치명적이지 않으므로 계속 진행

    def duplicate_page(self, date_info: dict) -> str:
        """템플릿 페이지 완전 복제 (블록 + 하위 페이지 순서 유지)"""
        import time

        logger.info(f"템플릿 페이지 복제 시작: {self.template_page_id}")

        try:
            # 1. 새 페이지 생성
            new_page_id = self.create_page_in_database(date_info)

            time.sleep(0.5)

            # 2. 템플릿 페이지의 블록 가져오기 및 순서대로 복사
            # (child_page도 블록 리스트에 포함되어 있으므로 순서대로 처리됨)
            template_blocks = self.get_page_blocks(self.template_page_id)
            if template_blocks:
                self.copy_blocks_to_page(new_page_id, template_blocks)

            logger.info(f"페이지 복제 완료: {new_page_id}")
            return new_page_id

        except Exception as e:
            logger.error(f"페이지 복제 실패: {str(e)}")
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

        # 템플릿 페이지 복제 (속성 포함하여 새 페이지 생성)
        new_page_id = self.duplicate_page(date_info)

        # 블록 복사 완료까지 대기
        logger.info("페이지 생성 완료 대기 중... (2초)")
        time.sleep(2)

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
