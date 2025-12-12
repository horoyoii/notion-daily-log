#!/usr/bin/env python3
"""
지난주 업무로그 아카이브 스크립트
매주 금요일 20시(한국시간) 실행: 지난주 금요일 이전의 모든 페이지를 아카이브 페이지로 이동
하위 페이지도 재귀적으로 복제합니다.
"""

import os
import sys
import requests
import json
import re
from datetime import datetime, timedelta
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

    def get_pages_before_last_friday(self) -> list:
        """지난주 금요일 이전의 모든 페이지 조회"""
        # 한국 시간 기준 오늘
        today = datetime.utcnow() + timedelta(hours=9)

        # 지난주 금요일 계산
        days_since_friday = (today.weekday() - 4) % 7
        if days_since_friday == 0:
            # 오늘이 금요일이면 지난주 금요일은 7일 전
            last_friday = today - timedelta(days=7)
        else:
            # 오늘이 금요일이 아니면 가장 최근 금요일 찾기
            last_friday = today - timedelta(days=days_since_friday)
        
        # 지난주 금요일 이전 = last_friday - timedelta(days=1) 이전
        cutoff_date = last_friday - timedelta(days=1)
        cutoff_iso = cutoff_date.strftime('%Y-%m-%d')
        
        logger.info(f"지난주 금요일: {last_friday.strftime('%Y-%m-%d')}")
        logger.info(f"아카이브 대상: {cutoff_iso} 이전의 모든 페이지")
        
        # 데이터베이스에서 작성일이 cutoff_date 이전인 모든 페이지 조회
        url = f"{self.base_url}/databases/{self.database_id}/query"
        all_pages = []
        has_more = True
        start_cursor = None
        
        while has_more:
            payload = {
                "filter": {
                    "and": [
                        {
                            "property": "작성일",
                            "date": {
                                "before": cutoff_iso
                            }
                        }
                    ]
                }
            }
            
            if start_cursor:
                payload["start_cursor"] = start_cursor
            
            try:
                response = requests.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                results = data.get('results', [])
                
                # 페이지 제목이 날짜 형식인지 확인하여 업무로그 페이지만 필터링
                for page in results:
                    title_property = page.get('properties', {}).get('이름', {})
                    title_array = title_property.get('title', [])
                    if title_array:
                        title = title_array[0].get('text', {}).get('content', '')
                        # 날짜 형식 확인: "YYYY년 MM월 DD일 (요일)"
                        if re.match(r'\d{4}년 \d{1,2}월 \d{1,2}일 \([월화수목금토일]\)', title):
                            all_pages.append({
                                'id': page['id'],
                                'title': title,
                                'date': page.get('properties', {}).get('작성일', {}).get('date', {}).get('start')
                            })
                
                has_more = data.get('has_more', False)
                start_cursor = data.get('next_cursor')
                
            except requests.exceptions.RequestException as e:
                logger.error(f"페이지 조회 실패: {str(e)}")
                if hasattr(e, 'response') and hasattr(e.response, 'text'):
                    logger.error(f"응답 내용: {e.response.text}")
                break
        
        logger.info(f"조회된 업무로그 페이지: {len(all_pages)}개")
        return all_pages

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
            logger.error(f"❌ 블록 콘텐츠 조회 실패 ({page_id}): {e}")
            return []
    
    def get_block_children(self, block_id: str) -> Optional[list]:
        """페이지의 모든 하위 블록을 가져옵니다. (하위 호환성 유지)"""
        blocks = self.get_page_blocks(block_id)
        return blocks if blocks else None

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
            logger.error(f"❌ 새 페이지 생성 실패 ({title}): {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"   응답: {e.response.text}")
            return None

    def append_block_children(self, block_id: str, children: list) -> bool:
        """페이지에 하위 블록들을 추가합니다."""
        url = f"{self.base_url}/blocks/{block_id}/children"
        # API는 한 번에 100개의 블록만 추가할 수 있습니다.
        for i in range(0, len(children), 100):
            chunk = children[i:i + 100]
            payload = {"children": chunk}
            try:
                response = requests.patch(url, headers=self.headers, json=payload)
                response.raise_for_status()
                logger.info(f"  ➡️ 콘텐츠 블록 {i+1}-{i+len(chunk)}/{len(children)} 추가 완료")
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ 콘텐츠 추가 실패: {e}")
                if hasattr(e.response, 'text'):
                    response_text = e.response.text
                    logger.error(f"   응답: {response_text}")
                    # 오류 메시지에서 문제 블록의 인덱스를 파싱합니다.
                    try:
                        match = re.search(r"body\.children\[(\d+)\]", response_text)
                        if match:
                            problem_index = int(match.group(1))
                            problem_block = payload["children"][problem_index]
                            logger.error(f"   🚨 문제가 발생한 블록 (인덱스 {problem_index}):")
                            logger.error(json.dumps(problem_block, indent=2, ensure_ascii=False))
                    except Exception as parse_error:
                        logger.error(f"   (오류 메시지 파싱 실패: {parse_error})")
                return False
        return True

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
            logger.error(f"❌ 원본 페이지 보관 실패 ({page_title}): {e}")
            return False

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

    def _clean_block_for_append(self, block: dict) -> dict:
        """API로 블록을 다시 보낼 때 필요한 키만 포함하는 새 객체를 만듭니다. (하위 호환성 유지)"""
        cleaned = self.clean_block_for_copy(block)
        if cleaned:
            return cleaned
        
        # 기존 로직 유지
        block_type = block.get("type")
        if block_type and block.get(block_type):
            return {
                "type": block_type,
                block_type: block[block_type]
            }
        
        block_copy = block.copy()
        block_copy.pop('id', None)
        block_copy.pop('parent', None)
        block_copy.pop('created_time', None)
        block_copy.pop('last_edited_time', None)
        block_copy.pop('created_by', None)
        block_copy.pop('last_edited_by', None)
        block_copy.pop('has_children', None)
        block_copy.pop('object', None)
        return block_copy
    
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
                
                # child_page 타입의 블록만 필터링
                for block in blocks:
                    if block.get('type') == 'child_page':
                        child_pages.append(block)
                
                has_more = data.get('has_more', False)
                start_cursor = data.get('next_cursor')
            
            return child_pages
            
        except requests.exceptions.RequestException as e:
            logger.error(f"하위 페이지 조회 실패: {str(e)}")
            return []
    
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
            
            # child_page는 별도로 처리
            if block_type == 'child_page':
                child_title = block.get('child_page', {}).get('title', '제목 없음')
                logger.info(f"  하위 페이지 발견 (순서 유지): {child_title}")
                time.sleep(0.5)
                try:
                    self.copy_child_page_recursive(block['id'], target_page_id)
                except Exception as e:
                    logger.error(f"  하위 페이지 복사 실패: {str(e)}")
                continue
            
            # child_database는 스킵
            if block_type == 'child_database':
                logger.warning(f"  child_database는 현재 지원하지 않습니다: {block['id']}")
                continue
            
            # 일반 블록 복사
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
                    
                    # 자식 블록이 있는 경우 재귀적으로 복사
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
            # 1. 원본 페이지 정보 가져오기
            url = f"{self.base_url}/pages/{source_page_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            source_page = response.json()
            
            # 2. 페이지 제목 추출
            title_property = source_page.get('properties', {}).get('title', {})
            title_array = title_property.get('title', [])
            title = title_array[0].get('text', {}).get('content', '제목 없음') if title_array else '제목 없음'
            
            logger.info(f"    하위 페이지 복사 시작: {title}")
            
            # 3. 새 하위 페이지 생성
            new_page_id = self.create_page(target_parent_id, title)
            if not new_page_id:
                return
            
            time.sleep(0.5)
            
            # 4. 원본 페이지의 블록 복사
            source_blocks = self.get_page_blocks(source_page_id)
            if source_blocks:
                self.copy_blocks_to_page(new_page_id, source_blocks)
            
            time.sleep(0.5)
            
            # 5. 하위 페이지의 하위 페이지들도 재귀적으로 복사
            child_pages = self.get_child_pages(source_page_id)
            for child_page in child_pages:
                child_page_id = child_page['id']
                time.sleep(0.5)
                self.copy_child_page_recursive(child_page_id, new_page_id)
            
            logger.info(f"    하위 페이지 복사 완료: {title}")
            
        except Exception as e:
            logger.error(f"    하위 페이지 복사 실패: {str(e)}")

    def move_page(self, page_id: str, page_title: str) -> bool:
        """페이지를 읽고, 새로 만들고, 복사한 뒤 원본을 삭제합니다. (하위 페이지 재귀 복제 포함)"""
        import time
        logger.info(f"페이지 이동 시작: {page_title}")

        # 1. 원본 페이지의 콘텐츠를 가져옵니다.
        content_blocks = self.get_page_blocks(page_id)
        logger.info(f"  📚 원본 콘텐츠 {len(content_blocks)}개 블록 읽기 완료")

        # 2. '아카이브' 페이지 아래에 새 페이지를 만듭니다.
        new_page_id = self.create_page(self.archive_page_id, page_title)
        if not new_page_id:
            return False

        time.sleep(0.5)

        # 3. 새 페이지에 콘텐츠를 추가합니다. (순서 유지, 하위 페이지 포함)
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

        # 5. 원본 페이지를 삭제합니다.
        if not self.delete_page(page_id, page_title):
            logger.error(f"!! 원본 페이지({page_id}) 삭제 실패. 수동 확인이 필요합니다.")
            return False
        
        logger.info(f"✅ 이동 완료: {page_title}")
        return True

    def archive_last_week(self):
        """지난주 금요일 이전의 모든 페이지 아카이브"""
        logger.info("=" * 80)
        logger.info("지난주 금요일 이전 업무로그 아카이브 시작")
        logger.info("=" * 80)

        # 1. 지난주 금요일 이전의 모든 페이지 조회
        pages = self.get_pages_before_last_friday()

        logger.info(f"\n발견된 페이지: {len(pages)}개")

        if not pages:
            logger.info("아카이브할 페이지가 없습니다.")
            return

        # 2. 페이지 이동
        logger.info(f"\n아카이브 페이지로 이동 시작:")
        logger.info(f"대상: https://www.notion.so/{self.archive_page_id.replace('-', '')}\n")

        success_count = 0
        fail_count = 0

        # 날짜 역순으로 이동 (최신이 위로 오도록)
        pages_sorted = sorted(pages, key=lambda x: x.get('date', ''), reverse=True)
        for page in pages_sorted:
            import time
            time.sleep(1)  # API 속도 제한 방지

            if self.move_page(page['id'], page['title']):
                success_count += 1
            else:
                fail_count += 1
                logger.error(f"🔥 전체 이동 실패: {page['title']}. 다음 페이지로 계속 진행합니다.")

        # 3. 결과 요약
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
