import json

transcript_path = "/home/kevin/.gemini/antigravity-cli/brain/c233932d-7584-4a0b-83b6-86254318e98c/.system_generated/logs/transcript.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        step = json.loads(line)
        if step.get("type") == "USER_INPUT":
            print(f"Step {step.get('step_index')}: {step.get('content')}")
