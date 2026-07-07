import json

# To format the reply payload since reply_to_pr_comments requires a string containing JSON.
payload = [
    {
        "comment_id": "4899455748",
        "reply": "알겠습니다. 이 작업은 오래된(stale) 봇 PR 정리 작업의 일환으로 폐기되었음을 확인했습니다. 지침에 따라 현재 작업은 중단합니다."
    }
]

print(json.dumps(payload, ensure_ascii=False))
