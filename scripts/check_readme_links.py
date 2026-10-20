import re
from pathlib import Path
from urllib.parse import unquote, urlparse

root = Path(__file__).resolve().parents[1]
text = (root / "README.md").read_text(encoding="utf-8-sig")
pattern = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)|(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)")
checked = []
broken = []
for match in pattern.finditer(text):
    target = match.group(1) or match.group(2)
    parsed = urlparse(target)
    if parsed.scheme or target.startswith("#"):
        continue
    path = unquote(parsed.path)
    if not path:
        continue
    checked.append(target)
    if not (root / path).exists():
        broken.append(target)
for target in broken:
    print(f"BROKEN: {target}")
print(f"Checked {len(checked)} relative README links/images; broken: {len(broken)}.")
raise SystemExit(1 if broken else 0)
