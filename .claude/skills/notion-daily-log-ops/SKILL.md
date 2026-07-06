---
name: notion-daily-log-ops
description: >-
  Diagnose and fix the Notion daily-log / weekly-archive automation in this repo.
  Use when a daily log page is missing, empty, or not updated ("7월 X일이 안 만들어졌다 /
  업데이트가 안 된다"), when the "오늘" 라벨이 특정 날짜에 멈춰 있을 때, when the GitHub
  Actions cron seems to have stopped, or when Notion block-copy raises
  "... should be an object" errors. Covers live-state diagnosis, safe re-run,
  and the disabled_inactivity root cause.
---

# Notion Daily Log — 운영/장애 대응 런북

이 저장소는 Notion 업무로그를 자동 생성/아카이브한다.

- `create_daily_log.py` — 매일 템플릿 페이지를 복제해 **당일 + 다음 업무일** 로그를 만들고, `상태`(select) 프로퍼티의 `오늘` 라벨을 당일로 이동. GitHub Actions `daily-log.yml` (cron `0 0 * * *` = KST 09:00).
- `archive_last_week.py` / `archive_single_page.py` — 지난주 로그 아카이브. `weekly-archive.yml` (cron `0 11 * * 5` = KST 금 20:00).
- `keepalive.yml` — schedule 자동 비활성화(아래 참조) 방지용 주간 빈 커밋.

환경변수는 `.env`(로컬) 또는 Actions Secrets: `NOTION_API_KEY`, `TEMPLATE_PAGE_ID`, `DATA_SOURCE_ID`, `ARCHIVE_PAGE_ID`.

## "특정 날짜가 업데이트/생성되지 않았다" 진단 순서

증상 예: "7.7 화요일이 업데이트되지 않음". 아래 순서로 원인을 좁힌다.

### 1. GitHub Actions가 실제로 돌았는지부터 확인 (가장 흔한 근본 원인)

```bash
gh workflow list --all          # daily-log 의 state 확인
gh run list --workflow=daily-log.yml -L 10
gh run view <run-id> --json createdAt,conclusion
```

- **state 가 `disabled_inactivity`** 이면 → **이것이 근본 원인.** GitHub는 저장소에 **60일간 커밋이 없으면 schedule 워크플로를 자동 비활성화**한다. 이 상태에서는 cron이 아예 안 돈다 (run 목록이 며칠째 멈춰 있음). 초록색 `[ok]` 이력만 보고 "정상"이라 판단하지 말 것 — 마지막 run의 `createdAt` 날짜를 반드시 확인한다.
- run 이력은 최신인데 결과가 이상하면 → 2번(silent failure)으로.

**재활성화** (github.com 에 `workflow` 스코프 인증 필요):
```bash
gh workflow enable daily-log.yml
```
이 저장소의 remote는 **github.com** 이다. `gh auth status` 가 사내 `oss.navercorp.com` 만 잡고 있으면 위 명령은 401이 난다. 이때는:
- 웹 UI: Actions 탭 → 해당 워크플로 → **Enable workflow** 버튼, 또는
- `gh auth login --hostname github.com` (workflow 스코프 포함) 후 재시도.

재활성화만으로는 60일 후 또 꺼진다. `keepalive.yml` 이 주간 빈 커밋으로 타이머를 초기화한다. keepalive 자체도 schedule이라, 최소 60일 안에 한 번은 돌아야 유지된다.

### 2. Notion 실제 상태를 read-only 로 확인

exact-title 필터는 Notion 인덱스 지연(eventual consistency)으로 방금 만든 페이지에 대해 잠깐 0건을 반환할 수 있으니, `작성일` 정렬 쿼리로 최근 항목을 함께 본다.

```python
import os, requests
from dotenv import load_dotenv
load_dotenv("/절대경로/.env")  # heredoc 실행 시 find_dotenv 가 깨지므로 경로를 명시
key=os.getenv('NOTION_API_KEY'); ds=os.getenv('DATA_SOURCE_ID')
H={"Authorization":f"Bearer {key}","Content-Type":"application/json","Notion-Version":"2022-06-28"}

# 최근 항목 + 상태 라벨 위치
q=requests.post(f"https://api.notion.com/v1/databases/{ds}/query",headers=H,
    json={"sorts":[{"property":"작성일","direction":"descending"}],"page_size":12}).json()
for p in q['results']:
    name="".join(t['plain_text'] for t in p['properties']['이름']['title'])
    st=p['properties'].get('상태',{}); stv=st.get('select') or st.get('status')
    d=(p['properties'].get('작성일',{}).get('date') or {}).get('start')
    print(name, '| 작성일',d, '| 상태', stv and stv['name'])
```

확인 포인트:
- 해당 날짜 페이지가 **존재하는지**, `archived` 여부, **블록 수(비어있지 않은지)**.
- `오늘` 라벨이 **어느 날짜에 멈춰 있는지** → 멈춘 지점이 자동화가 마지막으로 성공한 날.
- `작성일` 이 제목 날짜와 다르면(과거 버전/수동 생성 흔적) — 기존 페이지는 재실행해도 `작성일`이 교정되지 않는다(신규 생성만 반영). 필요 시 `update_page_property` 로 수동 교정.

### 3. Silent failure (블록 복사 실패를 삼키던 문제)

`execution.log` 에 `{"message":"paragraph.icon should be an object"}` 같은 400이 있으면, 템플릿 블록에 `icon: null` / `link: null` / `href: null` 같은 **null 필드를 그대로 append** 해서 Notion이 거부한 것이다.

- 해결: `clean_block_for_copy` 가 `omit_none_values` 로 null 필드를 제거한다(daily + 두 archive 스크립트 모두). 복사 실패는 이제 `BlockCopyError` 로 **raise** 되어 job이 빨갛게 실패한다(과거엔 "계속 진행"으로 삼켜 빈 페이지가 초록 성공으로 남았음). 실패 시 부분 생성 페이지는 `archive_incomplete_page` 로 보관 처리해 다음 실행을 막지 않는다.
- 회귀 방지 테스트: `test_create_daily_log.py` (6 tests). 변경 후 `python3 -m pytest test_create_daily_log.py test_archive.py -q`.

## 안전한 수동 복구 (라이브 Notion에 씀 — 사용자 확인 후)

```bash
python3 create_daily_log.py    # .env 자동 로드. 당일=오늘 라벨 이동, 다음 업무일 생성
```

동작: 당일 로그(있으면 재사용 + `오늘` 라벨 이동) → 다음 업무일 로그 생성(45개 블록 + 중첩 복사, 블록당 0.3~0.5s sleep이라 1~2분 소요). 주말은 건너뛴다. 실행 후 2번 스크립트로 결과 검증(페이지 존재, 블록 수, `오늘` 라벨 단일 위치).

## 핵심 교훈

- **초록색 run 이력 ≠ 정상.** schedule 워크플로는 조용히 `disabled_inactivity` 로 꺼지고, 코드가 에러를 삼키면 빈 페이지도 성공으로 남는다. 항상 (1) 마지막 run 날짜, (2) Notion 실제 상태, (3) `오늘` 라벨 위치를 교차 확인한다.
- **라이브 Notion 쓰기(재실행)는 outward-facing 액션** — 실행 전 사용자 확인. 조회(query/get)는 read-only라 안전.
