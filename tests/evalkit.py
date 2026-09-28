"""Shared helpers for the Phase 7 evaluation (D-043): loading the question set and string-matching gold facts.

A gold fact is a group of alternatives; the group matches when any alternative is found in the answer.
  "#90"          the number 90, compared with every number in the answer as digits
                 ("ninety", "90", "Rs. 90" all count; commas are ignored, so "Rs. 1,00,000" = 100000)
  anything else  whole words/phrases, case-insensitive, after normalising dashes, quotes and grade ranges
                 ("L1 to L4", "L1–L4" and "L1-L4" all become "l1-l4")
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.answer import numbers_in  # noqa: E402  (the same number reader the backend uses)

SET_PATH = ROOT / "tests" / "eval_set.yaml"
TRAPS_PATH = ROOT / "tests" / "traps.json"
RESULTS = ROOT / "tests" / "results"


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    for a, b in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\u2011": "-", "\u2010": "-", " ": " ", " ": " "}.items():
        s = s.replace(a, b)
    s = re.sub(r"(?<=\d),(?=\d)", "", s)                                   # 1,00,000 -> 100000
    s = re.sub(r"(?<=\d) %", "%", s)                                        # "50 %" -> "50%"
    s = re.sub(r"\b(l\d)\s*(?:-|to|and)\s*(l\d)\b", r"\1-\2", s)           # grade ranges
    return re.sub(r"\s+", " ", s).strip()


def alt_matches(alt, text, nums=None):
    if alt.startswith("#"):
        want = float(alt[1:])
        nums = numbers_in(text) if nums is None else nums
        return any(_num(n) == want for n in nums)
    return re.search(r"(?<![a-z0-9])" + re.escape(norm(alt)) + r"(?![a-z0-9])", norm(text)) is not None


def _num(n):
    try:
        return float(n)
    except (TypeError, ValueError):
        return None


def facts_matched(facts, text):
    """Return a list of booleans, one per fact group."""
    nums = numbers_in(text)
    return [any(alt_matches(a, text, nums) for a in group) for group in facts or []]


def load_set():
    """Return the evaluation set with trap items filled in from traps.json."""
    data = yaml.safe_load(SET_PATH.read_text())
    traps = {t["id"]: t for t in json.loads(TRAPS_PATH.read_text())}
    for item in data["singles"]:
        if item["id"] in traps:
            t = traps[item["id"]]
            item.setdefault("q", t["question"])
            item.setdefault("route", t["expected_route"])
            item.setdefault("evidence", [{"doc": e["doc_id"], "page": e["page"], "quote": e["quote"]} for e in t["evidence"]])
            item["trap"] = True
        item["routes"] = _routes(item["route"])
    for conv in data.get("conversations") or []:
        for n, turn in enumerate(conv["turns"], 1):
            turn["id"] = f"{conv['id']}.{n}"
            turn["routes"] = _routes(turn["route"])
    for pair in data.get("paraphrases") or []:
        pair["routes"] = _routes(pair["route"])
    return data


def _routes(r):
    return r if isinstance(r, list) else [r]


def turn_items(data):
    """Conversation turns as flat items (for checks that treat them like single questions)."""
    return [t | {"cat": "conversation", "q": t["q"]} for c in data.get("conversations") or [] for t in c["turns"]]
