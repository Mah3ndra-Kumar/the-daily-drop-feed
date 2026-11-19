"""Generates today's quote for every category and writes feed/v1/today.json.

Runs once a day in GitHub Actions (00:05 IST). The TokenHarbor key comes from the
TOKENHARBOR_API_KEY secret and is never written to the repo.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEED = ROOT / "feed" / "v1"
HISTORY = FEED / "history"
API = (os.environ.get("TOKENHARBOR_BASE_URL") or "https://tokenharbor.ai/v1") + "/chat/completions"
MODELS = [m.strip() for m in (
    os.environ.get("TOKENHARBOR_MODELS") or "deepseek-v4.1-flash:free,mimo-v2.6-flash:free,th-rudder").split(",") if m.strip()]
KEY = os.environ.get("TOKENHARBOR_API_KEY", "")
LAUNCH = dt.date(2026, 11, 20)          # issue No. 1
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
MAX_WORDS = 24

SYSTEM = (
    "You write the single line that appears on someone's phone wallpaper for one day. "
    "It must be original, specific and quietly strong. No hashtags, no emoji, no exclamation marks, "
    "no quotation marks inside the text, no hype words. Return only JSON."
)


def today_ist() -> dt.date:
    return dt.datetime.now(IST).date()


def issue_no(day: dt.date) -> int:
    return max(1, (day - LAUNCH).days + 1)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def ask(model: str, messages: list) -> str:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": 0.9,
        "max_tokens": 1200,
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
        "User-Agent": "the-daily-drop-feed/1.0",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read().decode())
    return data["choices"][0]["message"]["content"] or ""


def parse(raw: str) -> dict:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S)
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        raise ValueError("no JSON in reply")
    obj = json.loads(m.group(0))
    text = " ".join(str(obj.get("text", "")).split()).strip().strip('"“”')
    hl = " ".join(str(obj.get("highlight", "")).split()).strip().strip('"“”.,')
    credit = " ".join(str(obj.get("credit", "")).split()).strip().rstrip(".")
    if not text:
        raise ValueError("empty text")
    if len(text.split()) > MAX_WORDS:
        raise ValueError(f"too long: {len(text.split())} words")
    if "!" in text:
        raise ValueError("exclamation mark")
    if hl and hl.lower() not in text.lower():
        hl = ""
    if not hl:  # fall back to the last three words
        hl = " ".join(text.rstrip(".").split()[-3:])
    return {"text": text, "highlight": hl, "credit": credit}


def generate(cat: dict, recent: list) -> dict:
    avoid = "\n".join(f"- {t}" for t in recent[-60:]) or "- (none yet)"
    user = (
        f"Category: {cat['name']}\nBrief: {cat['brief']}\n\n"
        f"Rules:\n- 8 to {MAX_WORDS - 4} words, one or two short sentences.\n"
        "- highlight: 2 to 4 consecutive words copied exactly from text, the part that should stand out.\n"
        "- credit: empty string unless the brief asks for one.\n"
        "- Must not repeat or closely resemble any of these recent lines:\n"
        f"{avoid}\n\n"
        'Reply with only: {"text": "...", "highlight": "...", "credit": "..."}'
    )
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    last_err = None
    for attempt in range(6):
        model = MODELS[attempt % len(MODELS)]
        try:
            out = parse(ask(model, msgs))
            if out["text"].lower() in (t.lower() for t in recent):
                raise ValueError("duplicate")
            out["model"] = model
            return out
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError, json.JSONDecodeError) as e:
            last_err = e
            print(f"  {cat['id']} attempt {attempt + 1} with {model} failed: {e}", file=sys.stderr)
            time.sleep(3 + attempt * 3)
    raise RuntimeError(f"{cat['id']}: gave up ({last_err})")


def main() -> int:
    if not KEY:
        print("TOKENHARBOR_API_KEY is not set", file=sys.stderr)
        return 1
    cats = load_json(ROOT / "categories.json", [])
    day = today_ist()
    today = load_json(FEED / "today.json", {})
    entries = dict(today.get("categories", {}))
    failures = 0
    for cat in cats:
        hist_path = HISTORY / f"{cat['id']}.json"
        hist = load_json(hist_path, [])
        if hist and hist[-1].get("date") == day.isoformat():
            entries[cat["id"]] = hist[-1]
            print(f"{cat['id']}: already done today")
            continue
        try:
            q = generate(cat, [h["text"] for h in hist])
        except RuntimeError as e:
            failures += 1
            print(e, file=sys.stderr)
            continue  # keep yesterday's entry for this category
        entry = {"date": day.isoformat(), "no": issue_no(day), **q}
        hist.append(entry)
        hist_path.write_text(json.dumps(hist[-500:], ensure_ascii=False, indent=1), encoding="utf-8")
        entries[cat["id"]] = entry
        print(f"{cat['id']}: {entry['text']}")

    out = {
        "version": 1,
        "date": day.isoformat(),
        "no": issue_no(day),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "categories": entries,
        "list": [{"id": c["id"], "name": c["name"], "blurb": c["blurb"]} for c in cats],
    }
    (FEED / "today.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failures == len(cats) else 0


if __name__ == "__main__":
    sys.exit(main())
