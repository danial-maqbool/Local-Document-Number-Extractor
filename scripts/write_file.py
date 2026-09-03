import sys

content = sys.stdin.read()
target_file = sys.argv[1]
with open(target_file, "w", encoding="utf-8") as f:
    f.write(content)
print(f"Wrote {len(content)} chars to {target_file}")
