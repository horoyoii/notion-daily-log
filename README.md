# Notion 업무로그 자동 생성 시스템

매일 자동으로 Notion 업무로그를 생성하는 GitHub Actions 기반 자동화 시스템입니다.

## 기능

### 일일 업무로그 생성
- 📅 매일 오전 9시(한국시간) 자동 실행
- 📋 템플릿 페이지 완전 복제 (콘텐츠 블록 + 중첩 블록 + 하위 페이지)
- 🔄 날짜 자동 설정 (제목 및 작성일 속성)
- ✅ 중복 생성 방지
- 📝 실행 로그 자동 저장
- 🔁 재귀적 복사 (하위 페이지의 하위 페이지도 모두 복사)
- 📍 블록 순서 완벽 유지 (child_page도 원본 위치에 생성)

### 주간 자동 아카이브
- 🗂️ 매주 월요일 오전 9시 자동 실행
- 📦 지난주 업무로그 자동 아카이브 (월~일, 7일간)
- 📂 아카이브 페이지로 자동 이동
- 🔍 주말 페이지 자동 스킵 (생성되지 않은 경우)

## 구조

```
notion-daily-log/
├── .github/
│   └── workflows/
│       ├── daily-log.yml        # 일일 업무로그 생성 워크플로우
│       └── weekly-archive.yml   # 주간 아카이브 워크플로우
├── create_daily_log.py          # 업무로그 생성 스크립트
├── archive_last_week.py         # 아카이브 스크립트
├── requirements.txt             # Python 의존성
├── .gitignore                   # Git 제외 파일
└── README.md                    # 프로젝트 설명
```

## 설정 방법

### 1. Notion API 키 발급

1. [Notion Integrations](https://www.notion.so/my-integrations) 페이지 접속
2. "New integration" 클릭
3. Integration 이름 입력 (예: "업무로그 자동화")
4. "Submit" 클릭
5. "Internal Integration Token" 복사 (나중에 사용)

### 2. Notion 페이지 연결

1. Notion에서 "업무 로그" 페이지로 이동
2. 우측 상단 "..." 메뉴 클릭
3. "Connections" → "Connect to" 선택
4. 생성한 Integration 선택

### 3. GitHub Repository 생성

```bash
# 1. 로컬에 클론
git clone <your-repo-url>
cd <your-repo>

# 2. 파일 복사
cp -r notion-daily-log-automation/* .

# 3. Git 설정
git add .
git commit -m "Initial commit: Notion 업무로그 자동화 시스템"
git push origin main
```

### 4. GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions → New repository secret

다음 4개의 Secret을 추가하세요:

| Secret 이름 | 값 | 설명 |
|------------|-------|------|
| `NOTION_API_KEY` | `secret_xxx...` | Notion Integration Token |
| `TEMPLATE_PAGE_ID` | `2b15aae782eb8096b097c8ba0c29d2fd` | 템플릿 페이지 ID |
| `DATA_SOURCE_ID` | `2a15aae782eb806ba764d88dc76d15e2` | 데이터베이스 ID |
| `ARCHIVE_PAGE_ID` | `1cb5aae782eb807c81cef3bd6e2345ee` | 아카이브 페이지 ID |

> **참고**: 페이지 ID들은 이미 설정되어 있습니다.

## 로컬 테스트

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
# .env 파일 생성 후 아래 내용 입력
cat > .env << EOF
NOTION_API_KEY=secret_xxx...
TEMPLATE_PAGE_ID=2b15aae782eb8096b097c8ba0c29d2fd
DATA_SOURCE_ID=2a15aae782eb806ba764d88dc76d15e2
ARCHIVE_PAGE_ID=1cb5aae782eb807c81cef3bd6e2345ee
EOF

# 3. 업무로그 생성 테스트
python create_daily_log.py

# 4. 아카이브 테스트 (실제 이동 전 확인)
python test_archive.py

# 5. 아카이브 실행
python archive_last_week.py
```

## 실행 시간 변경

### 일일 업무로그 생성 시간

`.github/workflows/daily-log.yml` 파일에서 cron 표현식을 수정하세요:

```yaml
schedule:
  # 매일 한국시간 오전 9시 (UTC 0시)
  - cron: '0 0 * * *'
```

### 주간 아카이브 시간

`.github/workflows/weekly-archive.yml` 파일에서 cron 표현식을 수정하세요:

```yaml
schedule:
  # 매주 월요일 한국시간 오전 9시 (UTC 0시)
  - cron: '0 0 * * 1'  # 1 = Monday
```

**cron 시간 계산 예시:**
- 오전 8시 (KST) = UTC 23시 전날 → `'0 23 * * *'`
- 오전 10시 (KST) = UTC 1시 → `'0 1 * * *'`
- 오후 2시 (KST) = UTC 5시 → `'0 5 * * *'`

## 수동 실행

### 일일 업무로그 생성
GitHub Repository → Actions → "Daily Notion Work Log" → "Run workflow"

### 주간 아카이브
GitHub Repository → Actions → "Weekly Archive" → "Run workflow"

## 로그 확인

실행 후 Actions 탭에서 실행 결과 및 로그를 확인할 수 있습니다.

## 작동 원리

### 일일 업무로그 생성

1. **스케줄 트리거**: 매일 지정된 시간에 GitHub Actions가 자동 실행
2. **중복 확인**: 동일한 날짜의 로그가 이미 존재하면 생성 건너뜀
3. **템플릿 완전 복제**:
   - 데이터베이스에 새 페이지 생성 (제목 및 작성일 자동 설정)
   - 템플릿 페이지의 모든 콘텐츠 블록을 **순서대로** 복사
   - 중첩된 블록들을 재귀적으로 복사
   - child_page를 원본과 동일한 위치에 생성
   - 모든 하위 페이지를 재귀적으로 복사 (하위의 하위 페이지도 포함)
4. **완료**: 생성된 페이지 URL을 로그에 출력

### 주간 자동 아카이브

1. **스케줄 트리거**: 매주 월요일 지정된 시간에 GitHub Actions가 자동 실행
2. **지난주 날짜 계산**: 현재 주의 월요일 기준 7일 전부터 1일 전까지 (월~일)
3. **페이지 검색**: 데이터베이스에서 해당 날짜의 페이지들 조회
4. **아카이브 이동**: 찾은 페이지들을 아카이브 페이지 하위로 이동
5. **결과 로그**: 성공/실패 건수를 로그에 출력

## 문제 해결

### 페이지가 생성되지 않는 경우

1. GitHub Secrets가 올바르게 설정되었는지 확인
2. Notion Integration이 "업무 로그" 페이지에 연결되었는지 확인
3. Actions 탭에서 실행 로그 확인

### 콘텐츠가 복사되지 않는 경우

- Notion Integration이 템플릿 페이지와 모든 하위 페이지에 접근 권한이 있는지 확인하세요.
- Actions 탭에서 로그를 확인하여 어느 단계에서 실패했는지 파악하세요.
- API 속도 제한이 걸렸을 수 있습니다. 잠시 후 다시 시도하세요.

### 시간이 맞지 않는 경우

- GitHub Actions는 UTC 기준으로 실행됩니다.
- 한국시간(KST)은 UTC+9입니다.
- 스크립트 내부에서 한국시간으로 자동 변환됩니다.

## 라이선스

MIT License

## 기여

이슈 및 Pull Request를 환영합니다!
