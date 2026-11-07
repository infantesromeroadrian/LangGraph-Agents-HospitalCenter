"""Evaluación ciega de la puerta de urgencias: una sola ejecución por conjunto.

    python evals/run_blind_eval.py --data /ruta/al/conjunto_ciego.jsonl

Formato: JSONL con `id`, `label` ("alarm"|"benign"), `category` y `text` (como evals/data).
Para que el resultado sea una medida de generalización y no una guía de ajuste:
- Solo se imprimen y guardan agregados (nunca ids, textos ni fallos individuales).
- Cada conjunto (por SHA-256) se puede evaluar UNA vez; un segundo intento se rechaza.
- Se registra el SHA-256 de src/safety/red_flags.py: las reglas deben estar congeladas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.safety import detect_red_flags  # noqa: E402

LEDGER = ROOT / "evals" / "results" / "blind_runs.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path)
    args = parser.parse_args()

    data_hash = sha256(args.data)
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    if data_hash in ledger:
        sys.exit(
            f"Rechazado: este conjunto ya se evaluó el {ledger[data_hash]['date']}. No se repite."
        )

    rows = [json.loads(x) for x in args.data.read_text(encoding="utf-8").splitlines() if x.strip()]
    per_cat: dict[str, list[int]] = {}
    alarm_n = alarm_hit = benign_n = benign_fp = 0
    for row in rows:
        flagged = bool(detect_red_flags(row["text"]))
        if row["label"] == "alarm":
            alarm_n += 1
            alarm_hit += flagged
            bucket = per_cat.setdefault(row.get("category", "?"), [0, 0])
            bucket[0] += 1
            bucket[1] += flagged
        else:
            benign_n += 1
            benign_fp += flagged

    result = {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data_sha256": data_hash,
        "red_flags_sha256": sha256(ROOT / "src" / "safety" / "red_flags.py"),
        "n_alarm": alarm_n,
        "n_benign": benign_n,
        "escalation_recall": round(alarm_hit / alarm_n, 4) if alarm_n else None,
        "false_alarm_rate": round(benign_fp / benign_n, 4) if benign_n else None,
        "recall_by_category": {
            c: {"n": n, "recall": round(h / n, 4)} for c, (n, h) in sorted(per_cat.items())
        },
    }
    ledger[data_hash] = result
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
