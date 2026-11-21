"""测试用的假 sidecar：说同一套 JSON Lines，但不连任何真实 IM。"""
import json
import sys


def emit(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


emit({"type": "ready"})
emit({
    "type": "inbound",
    "peerId": "wx-1",
    "chatId": "wx-1",
    "messageId": "m-1",
    "contextToken": "tok-1",
    "text": "帮我看看这个文件",
    "receivedAt": 1,
})

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        command = json.loads(line)
    except json.JSONDecodeError:
        continue
    if command.get("type") == "stop":
        break
    if command.get("type") == "send":
        if command.get("text") == "失败":
            emit({"type": "sent", "id": command.get("id"), "ok": False, "error": "注入失败"})
        else:
            emit({"type": "sent", "id": command.get("id"), "ok": True, "serverMessageId": "srv-1"})
