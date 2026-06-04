import os

src_dir = r"d:\SW architecture\paper_ai_agent_c1\frontend\src"
files_to_check = []

for root, dirs, files in os.walk(src_dir):
    for file in files:
        if file.endswith((".js", ".jsx")):
            files_to_check.append(os.path.join(root, file))

for filepath in files_to_check:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Check for multiple export defaults
    if content.count("export default") > 1:
        print(f"!!! MULTIPLE EXPORTS found in: {filepath}")
        
    # Check if file ends with something suspicious after the last closing brace or export
    lines = content.strip().split("\n")
    if len(lines) > 5:
        last_lines = "\n".join(lines[-5:])
        # Simple heuristic: if it looks like it's repeating
        pass

print("Scan complete.")
