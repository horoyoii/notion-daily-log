#!/usr/bin/env python3
"""
단일 페이지 아카이브 테스트 스크립트
사용자가 직접 페이지 ID나 제목을 지정하여 단일 페이지를 아카이브할 수 있습니다.
"""

import os
import sys
import requests
import json
import argparse
import logging
from typing import Optional
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class NotionSinglePageArchiver:
    """Notion 단일 페이지 아카이브"""

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

    def get_page_blocks(self, page_id: str) -> list:
        """페이지의 모든 블록 가져오기 (페이지네이션 처리)"""
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
            
            return all_blocks
            
        except requests.exceptions.RequestException as e:
            logger.error(f"블록 콘텐츠 조회 실패 ({page_id}): {e}")
            return []

    def get_child_pages(self, page_id: str) -> list:
        """페이지의 모든 하위 페이지 가져오기"""
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
                
                for block in blocks:
                    if block.get('type') == 'child_page':
                        child_pages.append(block)
                
                has_more = data.get('has_more', False)
                start_cursor = data.get('next_cursor')
            
            return child_pages
            
        except requests.exceptions.RequestException as e:
            logger.error(f"하위 페이지 조회 실패: {str(e)}")
            return []

    def create_page(self, parent_id: str, title: str) -> Optional[str]:
        """지정된 부모 아래에 새 페이지를 만듭니다."""
        url = f"{self.base_url}/pages"
        payload = {
            "parent": {"page_id": parent_id},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            }
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            new_page_id = response.json()['id']
            logger.info(f"  📄 새 페이지 생성 완료: {title} (ID: {new_page_id})")
            return new_page_id
        except requests.exceptions.RequestException as e:
            logger.error(f"새 페이지 생성 실패 ({title}): {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"   응답: {e.response.text}")
            return None

    def clean_block_for_copy(self, block: dict) -> dict:
        """블록 데이터를 복사 가능한 형태로 정리"""
        block_type = block.get('type')
        if not block_type:
            return None
        
        if block_type in ['child_page', 'child_database']:
            return None
        
        unsupported_blocks = ['link_preview', 'unsupported']
        if block_type in unsupported_blocks:
            logger.warning(f"지원하지 않는 블록 타입: {block_type}")
            return None
        
        cleaned_block = {
            'type': block_type,
            block_type: {}
        }
        
        original_content = block.get(block_type, {})
        
        empty_block_types = ['divider', 'breadcrumb', 'table_of_contents']
        if block_type in empty_block_types:
            return cleaned_block
        
        if 'rich_text' in original_content:
            cleaned_block[block_type]['rich_text'] = original_content['rich_text']
        
        readonly_fields = ['id', 'created_time', 'last_edited_time', 'created_by', 'last_edited_by', 'has_children', 'archived', 'parent']
        for key, value in original_content.items():
            if key not in readonly_fields and key not in cleaned_block[block_type]:
                cleaned_block[block_type][key] = value
        
        return cleaned_block

    def copy_block_children(self, source_block_id: str, target_block_id: str):
        """블록의 자식 블록들을 재귀적으로 복사"""
        child_blocks = self.get_page_blocks(source_block_id)
        if not child_blocks:
            return
        self.copy_blocks_to_page(target_block_id, child_blocks)

    def copy_blocks_to_page(self, target_page_id: str, blocks: list):
        """블록들을 대상 페이지로 순서대로 복사 (일반 블록 + child_page 포함)"""
        if not blocks:
            return
        
        import time
        logger.info(f"  블록 복사 시작: {len(blocks)}개 (순서 유지)")
        
        for block in blocks:
            block_type = block.get('type')
            
            if block_type == 'child_page':
                child_title = block.get('child_page', {}).get('title', '제목 없음')
                logger.info(f"  하위 페이지 발견 (순서 유지): {child_title}")
                time.sleep(0.5)
                try:
                    self.copy_child_page_recursive(block['id'], target_page_id)
                except Exception as e:
                    logger.error(f"  하위 페이지 복사 실패: {str(e)}")
                continue
            
            if block_type == 'child_database':
                logger.warning(f"  child_database는 현재 지원하지 않습니다: {block['id']}")
                continue
            
            cleaned_block = self.clean_block_for_copy(block)
            if not cleaned_block:
                continue
            
            url = f"{self.base_url}/blocks/{target_page_id}/children"
            payload = {"children": [cleaned_block]}
            
            try:
                response = requests.patch(url, headers=self.headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                created_blocks = result.get('results', [])
                
                if created_blocks:
                    created_block = created_blocks[0]
                    
                    if block.get('has_children'):
                        original_block_id = block['id']
                        created_block_id = created_block['id']
                        time.sleep(0.3)
                        try:
                            self.copy_block_children(original_block_id, created_block_id)
                        except Exception as e:
                            logger.error(f"  중첩 블록 복사 실패: {str(e)}")
                
                time.sleep(0.3)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"  블록 복사 실패 ({block_type}): {str(e)}")

    def copy_child_page_recursive(self, source_page_id: str, target_parent_id: str):
        """하위 페이지를 재귀적으로 복사"""
        import time
        
        try:
            url = f"{self.base_url}/pages/{source_page_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            source_page = response.json()
            
            title_property = source_page.get('properties', {}).get('title', {})
            title_array = title_property.get('title', [])
            title = title_array[0].get('text', {}).get('content', '제목 없음') if title_array else '제목 없음'
            
            logger.info(f"    하위 페이지 복사 시작: {title}")
            
            new_page_id = self.create_page(target_parent_id, title)
            if not new_page_id:
                return
            
            time.sleep(0.5)
            
            source_blocks = self.get_page_blocks(source_page_id)
            if source_blocks:
                self.copy_blocks_to_page(new_page_id, source_blocks)
            
            time.sleep(0.5)
            
            child_pages = self.get_child_pages(source_page_id)
            for child_page in child_pages:
                child_page_id = child_page['id']
                time.sleep(0.5)
                self.copy_child_page_recursive(child_page_id, new_page_id)
            
            logger.info(f"    하위 페이지 복사 완료: {title}")
            
        except Exception as e:
            logger.error(f"    하위 페이지 복사 실패: {str(e)}")

    def find_page_by_id(self, page_id: str) -> Optional[dict]:
        """페이지 ID로 페이지 찾기"""
        url = f"{self.base_url}/pages/{page_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"페이지 조회 실패: {str(e)}")
            return None

    def find_page_by_title(self, title: str) -> Optional[dict]:
        """페이지 제목으로 페이지 찾기"""
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
                return results[0]
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"페이지 검색 실패: {str(e)}")
            return None

    def get_page_title(self, page: dict) -> str:
        """페이지에서 제목 추출"""
        title_property = page.get('properties', {}).get('이름', {})
        title_array = title_property.get('title', [])
        if title_array:
            return title_array[0].get('text', {}).get('content', '제목 없음')
        return '제목 없음'

    def delete_page(self, page_id: str, page_title: str) -> bool:
        """페이지를 보관 처리하여 삭제합니다."""
        url = f"{self.base_url}/pages/{page_id}"
        payload = {"archived": True}
        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            logger.info(f"  🗑️ 원본 페이지 보관 완료: {page_title}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"원본 페이지 보관 실패 ({page_title}): {e}")
            return False

    def archive_page(self, page_id: str, page_title: str) -> bool:
        """페이지를 아카이브합니다."""
        import time
        logger.info(f"페이지 아카이브 시작: {page_title}")

        # 1. 원본 페이지의 콘텐츠 가져오기
        content_blocks = self.get_page_blocks(page_id)
        logger.info(f"  📚 원본 콘텐츠 {len(content_blocks)}개 블록 읽기 완료")

        # 2. 아카이브 페이지 아래에 새 페이지 생성
        new_page_id = self.create_page(self.archive_page_id, page_title)
        if not new_page_id:
            return False

        time.sleep(0.5)

        # 3. 콘텐츠 복사 (순서 유지, 하위 페이지 포함)
        if content_blocks:
            self.copy_blocks_to_page(new_page_id, content_blocks)
        logger.info(f"  ✅ 콘텐츠 복사 완료")

        # 4. 하위 페이지도 재귀적으로 복사
        child_pages = self.get_child_pages(page_id)
        if child_pages:
            logger.info(f"  📁 하위 페이지 {len(child_pages)}개 발견, 재귀 복제 시작")
            for child_page in child_pages:
                child_page_id = child_page['id']
                time.sleep(0.5)
                self.copy_child_page_recursive(child_page_id, new_page_id)
            logger.info(f"  ✅ 하위 페이지 복제 완료")

        # 5. 원본 페이지 삭제
        if not self.delete_page(page_id, page_title):
            logger.error(f"원본 페이지({page_id}) 삭제 실패. 수동 확인이 필요합니다.")
            return False
        
        logger.info(f"✅ 아카이브 완료: {page_title}")
        return True


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='단일 페이지 아카이브 테스트 스크립트')
    parser.add_argument('--page-id', type=str, help='아카이브할 페이지 ID')
    parser.add_argument('--page-title', type=str, help='아카이브할 페이지 제목')
    
    args = parser.parse_args()
    
    # 환경변수에서 설정 로드
    api_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('DATA_SOURCE_ID')
    archive_page_id = os.getenv('ARCHIVE_PAGE_ID', '1cb5aae782eb807c81cef3bd6e2345ee')
    
    # 명령줄 인자가 없으면 환경변수에서 가져오기
    page_id = args.page_id or os.getenv('PAGE_ID')
    page_title = args.page_title or os.getenv('PAGE_TITLE')
    
    # 필수 환경변수 확인
    if not all([api_key, database_id]):
        logger.error("필수 환경변수가 설정되지 않았습니다.")
        logger.error("NOTION_API_KEY, DATA_SOURCE_ID를 확인하세요.")
        sys.exit(1)
    
    # 페이지 ID 또는 제목 확인
    if not page_id and not page_title:
        logger.error("페이지 ID 또는 제목을 지정해주세요.")
        logger.error("사용법:")
        logger.error("  python archive_single_page.py --page-id <page_id>")
        logger.error("  python archive_single_page.py --page-title \"2026년 12월 15일 (월)\"")
        logger.error("  또는 환경변수 PAGE_ID 또는 PAGE_TITLE 설정")
        sys.exit(1)
    
    # 아카이버 생성
    archiver = NotionSinglePageArchiver(api_key, database_id, archive_page_id)
    
    # 페이지 찾기
    page = None
    page_id_to_archive = None
    page_title_to_archive = None
    
    if page_id:
        logger.info(f"페이지 ID로 검색: {page_id}")
        page = archiver.find_page_by_id(page_id)
        if page:
            page_id_to_archive = page_id
            page_title_to_archive = archiver.get_page_title(page)
        else:
            logger.error(f"페이지를 찾을 수 없습니다: {page_id}")
            sys.exit(1)
    elif page_title:
        logger.info(f"페이지 제목으로 검색: {page_title}")
        page = archiver.find_page_by_title(page_title)
        if page:
            page_id_to_archive = page['id']
            page_title_to_archive = page_title
        else:
            logger.error(f"페이지를 찾을 수 없습니다: {page_title}")
            sys.exit(1)
    
    # 아카이브 실행
    logger.info("=" * 80)
    logger.info("단일 페이지 아카이브 시작")
    logger.info("=" * 80)
    logger.info(f"페이지 ID: {page_id_to_archive}")
    logger.info(f"페이지 제목: {page_title_to_archive}")
    logger.info(f"아카이브 대상: https://www.notion.so/{archive_page_id.replace('-', '')}\n")
    
    if archiver.archive_page(page_id_to_archive, page_title_to_archive):
        logger.info("\n" + "=" * 80)
        logger.info("아카이브 성공!")
        logger.info("=" * 80)
    else:
        logger.error("\n" + "=" * 80)
        logger.error("아카이브 실패!")
        logger.error("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

