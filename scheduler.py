import os, requests, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_KEY']
GH_PAT = os.environ['GH_PAT']

REPO = 'usunknown2025-droid/youtube-shorts-bot'


def get_due_shorts():
    now = datetime.now(timezone.utc).isoformat()
    url = f"{SUPABASE_URL}/rest/v1/pending_shorts?upload_status=eq.scheduled&scheduled_for=lte.{now}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}'
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        print('Error fetching due shorts:', r.text)
        return []


def trigger_upload(row):
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/upload.yml/dispatches"
    headers = {
        'Authorization': f'Bearer {GH_PAT}',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json'
    }
    data = {
        "ref": "main",
        "inputs": {
            "row_id": str(row['id']),
            "chat_id": str(row['chat_id']),
            "custom_title": "",
            "custom_description": "",
            "custom_tags": ""
        }
    }
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 204:
        print(f"Triggered upload for row {row['id']}")
        return True
    else:
        print(f"Failed to trigger upload for row {row['id']}: {r.status_code} {r.text}")
        return False


def mark_queued(row_id):
    url = f"{SUPABASE_URL}/rest/v1/pending_shorts?id=eq.{row_id}"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    data = {'upload_status': 'queued'}
    r = requests.patch(url, headers=headers, json=data)
    if r.status_code in [200, 204]:
        print(f"Marked row {row_id} as queued")
    else:
        print(f"Failed to mark queued for {row_id}: {r.text}")


def main():
    due = get_due_shorts()
    print(f"Found {len(due)} due shorts")
    for row in due:
        if trigger_upload(row):
            mark_queued(row['id'])
            time.sleep(2)


if __name__ == '__main__':
    main()
