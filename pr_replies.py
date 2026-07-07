import json

replies = [
    {
        "comment_id": "4899450427",
        "reply": "Understood. Acknowledging that this work is now obsolete and stopping work on this task."
    }
]

with open("replies.json", "w", encoding="utf-8") as f:
    json.dump(replies, f)
