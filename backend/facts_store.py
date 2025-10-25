# facts_store.py
import json, threading, time
from pathlib import Path

FACTS_PATH = Path("facts_gpt5.json")
_LOCK = threading.Lock()

def load_facts() -> list[str]:
    if not FACTS_PATH.exists():
        return []
    # tolerate BOM just in case
    with _LOCK, FACTS_PATH.open("r", encoding="utf-8-sig") as f:
        payload = json.load(f)
    facts = payload if isinstance(payload, list) else payload.get("facts", [])
    return [str(x).strip() for x in facts]

def save_facts(facts, path: Path | str = FACTS_PATH):
    # you said you don’t want to generate — so you probably won’t call this.
    # still leaving it correct & atomic in case you ever update manually.
    path = Path(path)
    payload = {"facts": [str(x).strip() for x in facts], "updated_at": int(time.time())}
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp.replace(path)
