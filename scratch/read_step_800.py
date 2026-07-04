import json

transcript_path = "/home/kevin/.gemini/antigravity-cli/brain/c233932d-7584-4a0b-83b6-86254318e98c/.system_generated/logs/transcript.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    step = json.loads(line)
    step_idx = step.get("step_index")
    if 798 <= step_idx < 831:
        source = step.get("source")
        step_type = step.get("type")
        content = step.get("content", "")
        tool_calls = step.get("tool_calls", [])
        
        if source == "MODEL" and step_type == "PLANNER_RESPONSE":
            print(f"\n================ STEP {step_idx} MODEL RESPONSE ================")
            print(content)
        elif step_type == "CODE_ACTION":
            print(f"\n--- STEP {step_idx} CODE ACTION ---")
            print(content[:500])
