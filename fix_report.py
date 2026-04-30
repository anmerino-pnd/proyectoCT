import re

with open('src/ct/reportes/run_report.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find all duplicate function definitions
new_lines = []
skip_until = None

for i, line in enumerate(lines):
    if line.strip().startswith('def get_next_window_count():'):
        # Skip this definition and everything until the next function
        print(f"Found duplicate at line {i+1}, skipping until next function")
        skip_until = None
        continue
    
    if skip_until and i >= skip_until:
        # Find the next function definition
        if line.strip().startswith('def '):
            skip_until = None
        continue
    
    new_lines.append(line)

with open('src/ct/reportes/run_report.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Fixed: {len(new_lines)} lines remaining")
