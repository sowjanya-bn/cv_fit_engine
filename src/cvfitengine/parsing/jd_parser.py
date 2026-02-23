from __future__ import annotations
import re
from ..core.types import JobSpec

_STOP = {
    "and","or","the","a","an","to","of","in","for","with","on","at","by","from","as",
    "is","are","be","will","you","we","our","your","this","that","it","they","their",
    "experience","skills","strong","ability","work","working","role","team"
}

def extract_keywords(text: str, max_keywords: int = 40) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9\+\#\.-]{1,}", text.lower())
    freq: dict[str,int] = {}
    for w in words:
        if w in _STOP or len(w) < 2:
            continue
        freq[w] = freq.get(w, 0) + 1
    scored = sorted(freq.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)
    return [w for w,_ in scored[:max_keywords]]

def parse_job(text: str) -> JobSpec:
    title = ""
    for line in text.splitlines():
        line = line.strip()
        if line:
            title = line[:80]
            break
    return JobSpec(raw_text=text, keywords=extract_keywords(text), title=title)
