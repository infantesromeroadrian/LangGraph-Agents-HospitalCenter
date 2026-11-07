"""Mide recall de escalada y tasa de falsas alarmas de la puerta determinista (sin LLM).

Uso:
    python evals/run_safety_eval.py --split heldout --out evals/results/heldout.json
    python evals/run_safety_eval.py --split all
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.safety import detect_red_flags  # noqa: E402

DATA = ROOT / "evals" / "data"


def load(split: str) -> list[dict]:
    names = {
        "dev": ["vignettes_dev"],
        "heldout": ["vignettes_heldout"],
        "test": ["vignettes_test"],
        "all": ["vignettes_dev", "vignettes_heldout", "vignettes_test"],
    }[split]
    rows: list[dict] = []
    for name in names:
        rows += [
            json.loads(line)
            for line in (DATA / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
    return rows


def evaluate(rows: list[dict]) -> dict:
    per_cat: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "escalated": 0})
    misses, false_alarms = [], []
    alarm_n = alarm_hit = benign_n = benign_fp = 0
    for row in rows:
        flags = detect_red_flags(row["text"])
        if row["label"] == "alarm":
            alarm_n += 1
            per_cat[row["category"]]["n"] += 1
            if flags:
                alarm_hit += 1
                per_cat[row["category"]]["escalated"] += 1
            else:
                misses.append(row["id"])
        else:
            benign_n += 1
            if flags:
                benign_fp += 1
                false_alarms.append({"id": row["id"], "flags": [f.category for f in flags]})
    return {
        "n_alarm": alarm_n,
        "n_benign": benign_n,
        "escalation_recall": round(alarm_hit / alarm_n, 4) if alarm_n else None,
        "false_alarm_rate": round(benign_fp / benign_n, 4) if benign_n else None,
        "recall_by_category": {
            c: {**v, "recall": round(v["escalated"] / v["n"], 4)}
            for c, v in sorted(per_cat.items())
        },
        "missed_ids": misses,
        "false_alarm_cases": false_alarms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "heldout", "test", "all"], default="all")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = {"split": args.split, **evaluate(load(args.split))}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
