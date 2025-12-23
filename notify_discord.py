import os
import requests
from datetime import datetime, timezone, timedelta

# --- 설정 정보 (환경변수에서 로드) ---
TOKEN = os.environ.get("PROJECT_PAT")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# GitHub Project 정보
OWNER = "Chicken-Triceps"     # 사용자명
PROJECT_NUMBER = 4            # URL 끝에 있는 숫자 (projects/4)
START_DATE_FIELD = "Initial Date" # 방금 만든 필드명과 똑같이
END_DATE_FIELD = "End Date"

# --- GraphQL 쿼리 ---
# 프로젝트의 아이템과 필드 값을 가져오는 쿼리
QUERY = """
query($owner: String!, $number: Int!) {
  user(login: $owner) { # 조직인 경우 user 대신 organization(login: $owner) 로 변경
    projectV2(number: $number) {
      items(first: 100) {
        nodes {
          content {
            ... on Issue { title url }
            ... on PullRequest { title url }
            ... on DraftIssue { title }
          }
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldDateValue {
                date
                field { name }
              }
            }
          }
        }
      }
    }
  }
}
"""

def send_discord_message(items):
    if not items:
        return # 알림할 내용이 없으면 전송 안 함 (옵션)

    # 메시지 포맷팅
    today_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    message = f"## 📅 {today_str} 오늘의 일정 알림\n"
    
    for item in items:
        title = item['title']
        url = item.get('url', 'URL 없음')
        message += f"- **{title}**: {url}\n"

    payload = {"content": message}
    requests.post(WEBHOOK_URL, json=payload)

def main():
    # 1. 현재 한국 시간(KST) 구하기
    kst_now = datetime.now(timezone(timedelta(hours=9))).date()
    
    # 2. GitHub API 호출
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # 조직(Organization) 프로젝트라면 쿼리의 'user'를 'organization'으로 바꿔야 합니다.
    # 아래 코드는 'user' 기준으로 작성되었습니다.
    query_to_run = QUERY 
    if "organization" in QUERY and "user" not in QUERY:
         pass # 이미 수정됨
    
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": query_to_run, "variables": {"owner": OWNER, "number": PROJECT_NUMBER}},
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    data = response.json()
    
    # 데이터 파싱 경로 (User 기준)
    try:
        project_items = data['data']['user']['projectV2']['items']['nodes']
    except TypeError:
        # User가 아니라 Organization일 경우 경로가 다를 수 있음, 혹은 데이터 없음
        print("데이터를 찾을 수 없습니다. Owner 타입(User/Org)을 확인하세요.")
        return

    today_schedule = []

    # 3. 아이템 필터링
    for item in project_items:
        title = "제목 없음"
        url = ""
        
        # Content(이슈/PR) 정보 가져오기
        if item.get('content'):
            title = item['content'].get('title', '제목 없음')
            url = item['content'].get('url', '')
        
        # 날짜 필드 확인
        start_date = None
        end_date = None
        
        for field in item['fieldValues']['nodes']:
            if not field: continue # 빈 필드 스킵
            field_name = field.get('field', {}).get('name')
            date_value = field.get('date')
            
            if field_name == START_DATE_FIELD:
                start_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            elif field_name == END_DATE_FIELD:
                end_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        
        # 날짜 로직: Start <= Today <= End
        # End Date가 없으면 Start Date 당일만 체크하는 로직으로 변경 가능
        if start_date:
            effective_end = end_date if end_date else start_date
            if start_date <= kst_now <= effective_end:
                today_schedule.append({"title": title, "url": url})

    # 4. 디스코드 전송
    if today_schedule:
        print(f"오늘 일정 {len(today_schedule)}개 발견. 전송 중...")
        send_discord_message(today_schedule)
    else:
        print("오늘 예정된 일정이 없습니다.")

if __name__ == "__main__":
    main()
