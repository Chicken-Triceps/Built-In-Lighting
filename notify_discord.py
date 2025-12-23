import os
import requests
from datetime import datetime, timezone, timedelta

# --- 설정 정보 ---
TOKEN = os.environ.get("PROJECT_PAT")
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# GitHub Project 정보
OWNER = "Chicken-Triceps"     # 사용자명
PROJECT_NUMBER = 4            # URL 끝에 있는 숫자 (projects/4)
START_DATE_FIELD = "Initial Date" # 필드명
END_DATE_FIELD = "End Date"

# --- GraphQL 쿼리 (수정된 부분) ---
# field { name } 대신 ... on ProjectV2FieldCommon { name } 을 사용해야 함
QUERY = """
query($owner: String!, $number: Int!) {
  user(login: $owner) {
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
                field {
                  ... on ProjectV2FieldCommon { name }
                }
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
    if not items: return

    # 한국 시간 기준 오늘 날짜
    today_str = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    message = f"## 📅 {today_str} 오늘의 일정 알림\n"
    
    for item in items:
        title = item['title']
        url = item.get('url', 'URL 없음')
        message += f"- **{title}**: {url}\n"

    requests.post(WEBHOOK_URL, json={"content": message})

def main():
    # 1. 현재 한국 시간(KST) 구하기
    kst_now = datetime.now(timezone(timedelta(hours=9))).date()
    
    # 2. GitHub API 호출
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    response = requests.post(
        "https://api.github.com/graphql",
        json={"query": QUERY, "variables": {"owner": OWNER, "number": PROJECT_NUMBER}},
        headers=headers
    )
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    data = response.json()
    
    # 🚨 에러 체크 로직
    if 'errors' in data:
        print("🚨 GitHub API 반환 에러:")
        print(data['errors'])
        return

    # 데이터 파싱
    try:
        project_items = data['data']['user']['projectV2']['items']['nodes']
    except (TypeError, KeyError) as e:
        print(f"데이터 구조 에러: {e}")
        print("받은 데이터:", data)
        return

    today_schedule = []

    # 3. 아이템 필터링
    for item in project_items:
        title = "제목 없음"
        url = ""
        
        if item.get('content'):
            title = item['content'].get('title', '제목 없음')
            url = item['content'].get('url', '')
        
        start_date = None
        end_date = None
        
        for field in item['fieldValues']['nodes']:
            if not field: continue
            
            # 여기서 필드 이름을 가져오는 방식
            field_name = field.get('field', {}).get('name')
            date_value = field.get('date')
            
            if field_name == START_DATE_FIELD:
                start_date = datetime.strptime(date_value, "%Y-%m-%d").date()
            elif field_name == END_DATE_FIELD:
                end_date = datetime.strptime(date_value, "%Y-%m-%d").date()
        
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
