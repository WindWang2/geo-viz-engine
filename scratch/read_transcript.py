import json

transcript_path = "/home/kevin/.gemini/antigravity-cli/brain/c233932d-7584-4a0b-83b6-86254318e98c/.system_generated/logs/transcript.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines in transcript: {len(lines)}")

# Search for the user inputs and model responses from the last 15 steps
for i, line in enumerate(lines[-15:]):
    step = json.loads(line)
    step_idx = step.get("step_index")
    source = step.get("source")
    step_type = step.get("type")
    
    print(f"\n--- Step {step_idx} | Source: {source} | Type: {step_type} ---")
    content = step.get("content", "")
    if content:
        # Print first 300 chars and last 300 chars of content
        if len(content) > 600:
            print(content[:300] + "\n... [TRUNCATED] ...\n" + content[-300:])
        else:
            print(content)
            
    # Check if there are tool_calls
    tool_calls = step.get("tool_calls", [])
    if tool_calls:
        print(f"Tool calls: {[tc.get('name') for tc in tool_calls]}")
