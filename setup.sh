#!/bin/bash

# Notion 업무로그 자동화 - GitHub Workflow 설정 스크립트

echo "🚀 GitHub Workflow 디렉토리 생성 중..."

# .github/workflows 디렉토리 생성
mkdir -p .github/workflows

# workflow 파일 생성
cat > .github/workflows/daily-log.yml << 'EOF'
name: Daily Notion Work Log

on:
  schedule:
    # 매일 한국시간 오전 9시 (UTC 0시)에 실행
    - cron: '0 0 * * *'
  workflow_dispatch: # 수동 실행 가능

jobs:
  create-daily-log:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install requests python-dotenv
    
    - name: Create daily work log
      env:
        NOTION_API_KEY: ${{ secrets.NOTION_API_KEY }}
        TEMPLATE_PAGE_ID: ${{ secrets.TEMPLATE_PAGE_ID }}
        DATA_SOURCE_ID: ${{ secrets.DATA_SOURCE_ID }}
      run: |
        python create_daily_log.py
    
    - name: Upload log file (if exists)
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: execution-log
        path: execution.log
        retention-days: 7
EOF

echo "✅ GitHub Workflow 파일 생성 완료!"
echo ""
echo "📁 생성된 파일:"
echo "   .github/workflows/daily-log.yml"
echo ""
echo "🎯 다음 단계:"
echo "   1. git add .github"
echo "   2. git commit -m 'Add GitHub Actions workflow'"
echo "   3. git push"
echo ""
echo "   그런 다음 GitHub Repository에서 Secrets 설정을 진행하세요!"
