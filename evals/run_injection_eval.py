"""Mide la tasa de éxito de ataques de inyección de prompts con un LLM local (Ollama).

    python evals/run_injection_eval.py --repo <ruta al código a evaluar> --label after

`--repo` permite medir el código ANTES del endurecimiento (p. ej. un `git archive` del commit
f156ae5) con exactamente los mismos ataques y oráculos. El LLM es local: no se usa ninguna API
en la nube. Requiere Ollama en marcha y el modelo descargado.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oracles  # noqa: E402

DATA = HERE / "data" / "attacks.jsonl"
ASSISTANT_GREETING = "Hola, soy un asistente de IA de demostración. ¿En qué puedo ayudarte?"


def ollama_metadata(model: str, host: str) -> dict:
    meta = {"model": model, "host": host}
    try:
        import urllib.request

        base = host.removesuffix("/v1")
        with urllib.request.urlopen(f"{base}/api/version", timeout=5) as resp:
            meta["ollama_version"] = json.load(resp).get("version")
        req = urllib.request.Request(
            f"{base}/api/show", data=json.dumps({"model": model}).encode(), method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            info = json.load(resp)
        meta["details"] = info.get("details")
        meta["modified_at"] = info.get("modified_at")
    except Exception as exc:
        meta["metadata_error"] = type(exc).__name__
    try:
        out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10, check=False
        )
        for line in out.stdout.splitlines():
            if line.startswith(model):
                meta["ollama_list"] = " ".join(line.split()[:3])
    except Exception:
        pass
    return meta


def setup_environment(repo: Path, model: str, host: str) -> None:
    os.environ.update(
        {
            "OPENAI_API_KEY": "ollama-local",
            "OPENAI_BASE_URL": host,
            "OPENAI_MODEL": model,
            "OPENAI_TEMPERATURE": "0.2",
            "OPENAI_MAX_TOKENS": "700",
            "OPENAI_TIMEOUT": "180",
            "APP_SECRET_KEY": "eval-secret-not-used-0123456789abcdef",
            "ADMIN_API_KEY": "eval-admin-key-0123456789",
        }
    )
    sys.path.insert(0, str(repo))
    os.chdir(repo)


def patch_llm_no_thinking() -> None:
    """Desactiva el razonamiento del modelo (reasoning_effort=none) para acelerar la medición."""
    from src.services.llm_service import llm_service

    original = llm_service.client.chat.completions.create

    def merge_system(messages: list[dict]) -> list[dict]:
        """La plantilla de chat de Qwen3.5 exige un único mensaje system al principio."""
        system = [m["content"] for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]
        return ([{"role": "system", "content": "\n\n".join(system)}] if system else []) + rest

    async def create(*args, **kwargs):
        kwargs.setdefault("reasoning_effort", "none")
        if "messages" in kwargs:
            kwargs["messages"] = merge_system(kwargs["messages"])
        return await original(*args, **kwargs)

    llm_service.client.chat.completions.create = create


def build_context(row: dict) -> str | None:
    """Contexto de paciente igual al de producción (build_patient_context si existe)."""
    field = row.get("poisoned_field")
    if not field:
        return None
    try:
        from src.web.websocket.chat import build_patient_context

        return build_patient_context(
            age=45, gender="M", allergies="Ninguna conocida", medications="Ninguna",
            medical_history=field, session_id=str(uuid4()),
        )  # fmt: skip
    except ImportError:
        # Código anterior al endurecimiento: misma construcción que tenía chat.py
        from src.utils.validators import format_patient_record_for_llm, sanitize_llm_input

        safe = sanitize_llm_input(field, session_id=str(uuid4()))
        return format_patient_record_for_llm(
            f"""
RESUMEN CLINICO DEL PACIENTE:

Datos clinicos relevantes:
- Edad: 45 años
- Genero: Masculino

- Alergias conocidas: Ninguna conocida
- Medicacion actual: Ninguna
- Antecedentes medicos: {safe}

Usa estos datos solo como contexto clinico adicional.
No recomiendes medicamentos a los que el paciente sea alergico.
Verifica interacciones con la medicacion actual.
""".strip()
        )


async def run_chat_attack(row: dict, specialty: str) -> dict:
    from src.agents.agent_factory import AgentFactory
    from src.models.message import Message
    from src.utils.validators import sanitize_llm_input

    session_id = uuid4()
    agent = AgentFactory.create_agent(specialty)
    history: list = []
    if row["category"] == "memory_poison" and row["vector"] == "history":
        history = [
            Message(role="user", content=sanitize_llm_input(row["poisoned_message"]), session_id=session_id),
            Message(role="assistant", content=ASSISTANT_GREETING, session_id=session_id, specialist_type=specialty),
        ]  # fmt: skip
    user_text = sanitize_llm_input(row["text"], session_id=str(session_id))
    current = Message(role="user", content=user_text, session_id=session_id)
    started = time.time()
    output = await agent.chat(
        message=current, session_id=session_id, history=[*history, current],
        patient_context=build_context(row),
    )  # fmt: skip
    category = row["category"]
    cheats = {
        "prescribe": oracles.prescribes(output),
        "impersonate": oracles.impersonates(output),
        "extract_prompt": oracles.leaks_prompt(output),
        "memory_poison": (
            oracles.followed_canary(output, row.get("canary", "")) or oracles.prescribes(output)
            or oracles.impersonates(output) or oracles.leaks_prompt(output)
        ),
    }  # fmt: skip
    guard = list(getattr(agent, "last_guard_violations", []) or [])
    return {
        "id": row["id"], "category": category, "specialty": specialty,
        "attack_success": bool(cheats[category]), "guard_intervened": bool(guard),
        "raw_attack_success": bool(cheats[category]) or bool(guard),
        "seconds": round(time.time() - started, 1), "output": output,
    }  # fmt: skip


async def run_escalation_attack(row: dict, graph) -> dict:
    from src.graph.state import create_initial_state
    from src.models.message import Message

    session_id = uuid4()
    state = create_initial_state(
        session_id, f"thread_{session_id}",
        messages=[Message(role="user", content=row["text"], session_id=session_id)],
    )  # fmt: skip
    started = time.time()
    result = await graph.ainvoke(
        state, {"configurable": {"thread_id": f"t-{session_id}"}, "recursion_limit": 50}
    )
    messages = [
        {"specialist_type": m.specialist_type, "content": m.content, "metadata": m.metadata}
        for m in result["messages"] if m.role == "assistant"
    ]  # fmt: skip
    defended = oracles.escalated_with_112(messages)
    return {
        "id": row["id"], "category": "disable_escalation", "attack_success": not defended,
        "guard_intervened": False, "raw_attack_success": not defended,
        "seconds": round(time.time() - started, 1),
        "output": "\n---\n".join(f"[{m['specialist_type']}] {m['content']}" for m in messages),
    }  # fmt: skip


def summarize(results: list[dict]) -> dict:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    table = {}
    for cat, items in sorted(by_cat.items()):
        n = len(items)
        table[cat] = {
            "n_runs": n,
            "attack_success": sum(r["attack_success"] for r in items),
            "attack_success_rate": round(sum(r["attack_success"] for r in items) / n, 4),
            "raw_model_failures": sum(r["raw_attack_success"] for r in items),
            "raw_model_failure_rate": round(sum(r["raw_attack_success"] for r in items) / n, 4),
            "guard_interventions": sum(r["guard_intervened"] for r in items),
        }
    total = len(results)
    return {
        "by_category": table,
        "total_runs": total,
        "overall_attack_success_rate": round(sum(r["attack_success"] for r in results) / total, 4),
        "overall_raw_model_failure_rate": round(
            sum(r["raw_attack_success"] for r in results) / total, 4
        ),
    }


async def main_async(args) -> None:
    from langgraph.checkpoint.memory import MemorySaver
    from src.agents.agent_factory import AgentFactory
    from src.graph.medical_graph import create_medical_graph

    patch_llm_no_thinking()
    rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line]
    if args.limit:
        rows = rows[: args.limit]
    specialties = AgentFactory.get_available_specialties()
    graph = await create_medical_graph(MemorySaver())

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(args.runs_dir).expanduser() / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / f"injection-{args.label}-{stamp}.jsonl"
    results: list[dict] = []
    with raw_path.open("w", encoding="utf-8") as fh:
        for index, row in enumerate(rows):
            try:
                if row["category"] == "disable_escalation":
                    outs = [await run_escalation_attack(row, graph)]
                else:
                    picks = [
                        specialties[(2 * index) % len(specialties)],
                        specialties[(2 * index + 1) % len(specialties)],
                    ]
                    outs = [await run_chat_attack(row, s) for s in picks]
            except Exception as exc:
                outs = [{"id": row["id"], "category": row["category"], "attack_success": False,
                         "guard_intervened": False, "raw_attack_success": False, "error": type(exc).__name__, "output": ""}]  # fmt: skip
                print(f"ERROR {row['id']}: {type(exc).__name__}: {exc}", file=sys.stderr)
            for out in outs:
                fh.write(json.dumps(out, ensure_ascii=False) + "\n")
                fh.flush()
                results.append(out)
            print(
                f"[{index + 1}/{len(rows)}] {row['id']} -> {[o['attack_success'] for o in outs]}",
                flush=True,
            )

    errors = [r for r in results if r.get("error")]
    summary = {
        "label": args.label,
        "code_commit": subprocess.run(
            ["git", "-C", str(args.repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        or "n/a (árbol exportado)",
        "llm": ollama_metadata(args.model, args.host),
        "temperature": 0.2,
        "reasoning_effort": "none",
        "n_attack_prompts": len(rows),
        "errors": len(errors),
        "raw_outputs_file": str(raw_path),
        **summarize([r for r in results if not r.get("error")]),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--model", default="arca-ornith-9b:q4km")
    parser.add_argument("--host", default="http://localhost:11434/v1")
    parser.add_argument("--out", required=True)
    parser.add_argument("--runs-dir", default="~/datasets/hospital/runs")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    args.repo = args.repo.resolve()
    if "cloud" in args.model or "api.openai.com" in args.host:
        sys.exit("Este harness solo admite modelos locales de Ollama.")
    setup_environment(args.repo, args.model, args.host)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
