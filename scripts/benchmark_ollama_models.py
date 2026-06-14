#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from donna.glue.prompts.local_assistant import build_local_assistant_prompt
from donna.glue.tools.registry import TOOL_DEFINITIONS


SIMPLE_PROMPT = (
    "A caller says they were rear-ended and have neck pain. "
    "Reply as Donna in one concise sentence."
)
TOOL_PROMPT = "Record that the caller granted recording consent. Use the tool."
LOCAL_ASSISTANT_USER = "How is Maria Lopez doing after the accident?"
SUMMARY_PATH = REPO_ROOT / ".context" / "ollama-model-benchmark.json"


def _tool_by_name(name: str) -> dict[str, Any]:
    for item in TOOL_DEFINITIONS:
        if item.get("function", {}).get("name") == name:
            return item
    raise RuntimeError(f"Missing tool definition: {name}")


def _sentence_count(text: str) -> int:
    marks = ".!?"
    count = sum(1 for ch in text if ch in marks)
    return max(1, count) if text.strip() else 0


def _post_chat(
    client: httpx.Client,
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
) -> tuple[float, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools

    started = time.perf_counter()
    resp = client.post(f"{base_url}/api/chat", json=payload)
    elapsed = time.perf_counter() - started
    resp.raise_for_status()
    return elapsed, resp.json()


def _bench_text_case(
    client: httpx.Client,
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    runs: int,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    for _ in range(runs):
        elapsed, data = _post_chat(
            client,
            base_url=base_url,
            model=model,
            messages=messages,
        )
        content = (data.get("message", {}).get("content") or "").strip()
        samples.append(
            {
                "seconds": elapsed,
                "content": content,
                "sentence_count": _sentence_count(content),
                "char_count": len(content),
            }
        )
    return {
        "avg_seconds": statistics.fmean(sample["seconds"] for sample in samples),
        "min_seconds": min(sample["seconds"] for sample in samples),
        "max_seconds": max(sample["seconds"] for sample in samples),
        "samples": samples,
    }


def _bench_tool_case(
    client: httpx.Client,
    *,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    elapsed, data = _post_chat(
        client,
        base_url=base_url,
        model=model,
        messages=[{"role": "user", "content": TOOL_PROMPT}],
        tools=[_tool_by_name("record_consent")],
    )
    message = data.get("message", {})
    tool_calls = message.get("tool_calls") or []
    names = [
        call.get("function", {}).get("name")
        for call in tool_calls
    ]
    return {
        "seconds": elapsed,
        "ok": "record_consent" in names,
        "tool_call_names": names,
        "content": (message.get("content") or "").strip(),
        "raw_tool_calls": tool_calls,
    }


def _bench_model(
    client: httpx.Client,
    *,
    base_url: str,
    model: str,
    runs: int,
) -> dict[str, Any]:
    simple_messages = [{"role": "user", "content": SIMPLE_PROMPT}]
    local_prompt = build_local_assistant_prompt(
        firm_name="Donna Legal",
        phase="DISCLOSURE",
        context_block=(
            "CASE CONTEXT:\n"
            "- Maria Lopez reports neck pain after a rear-end collision in San Jose.\n"
            "- Ask Maria for medical evaluation status and insurance claim number."
        ),
    )
    local_messages = [
        {"role": "system", "content": local_prompt},
        {"role": "user", "content": LOCAL_ASSISTANT_USER},
    ]

    cold_seconds, cold_data = _post_chat(
        client,
        base_url=base_url,
        model=model,
        messages=simple_messages,
    )
    cold_content = (cold_data.get("message", {}).get("content") or "").strip()
    warm_simple = _bench_text_case(
        client,
        base_url=base_url,
        model=model,
        messages=simple_messages,
        runs=runs,
    )
    local_assistant = _bench_text_case(
        client,
        base_url=base_url,
        model=model,
        messages=local_messages,
        runs=runs,
    )
    tool_call = _bench_tool_case(
        client,
        base_url=base_url,
        model=model,
    )

    local_samples = local_assistant["samples"]
    local_voice_ok = all(
        sample["sentence_count"] <= 2 and sample["char_count"] <= 320
        for sample in local_samples
    )
    return {
        "model": model,
        "ok": True,
        "cold_simple": {
            "seconds": cold_seconds,
            "content": cold_content,
            "sentence_count": _sentence_count(cold_content),
            "char_count": len(cold_content),
        },
        "warm_simple": warm_simple,
        "local_assistant": local_assistant,
        "tool_call": tool_call,
        "voice_suitable": local_voice_ok,
    }


def _print_table(results: list[dict[str, Any]]) -> None:
    headers = [
        "model",
        "cold",
        "warm_avg",
        "local_avg",
        "tool",
        "voice",
        "status",
    ]
    rows: list[list[str]] = []
    for item in results:
        if not item.get("ok"):
            rows.append([item["model"], "-", "-", "-", "-", "-", item.get("error", "failed")])
            continue
        rows.append(
            [
                item["model"],
                f"{item['cold_simple']['seconds']:.2f}s",
                f"{item['warm_simple']['avg_seconds']:.2f}s",
                f"{item['local_assistant']['avg_seconds']:.2f}s",
                "OK" if item["tool_call"]["ok"] else "FAIL",
                "OK" if item["voice_suitable"] else "CHECK",
                "OK",
            ]
        )

    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows))
        for i in range(len(headers))
    ]
    print("  ".join(headers[i].ljust(widths[i]) for i in range(len(headers))))
    print("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(row))))


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Donna Ollama voice models.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=["nemotron-3-nano", "qwen2.5:14b", "qwen2.5:7b"],
        help="Ollama model tags to benchmark.",
    )
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    base_url = args.ollama_url.rstrip("/")
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=180.0) as client:
        for model in args.models:
            print(f"Benchmarking {model}...")
            try:
                results.append(
                    _bench_model(
                        client,
                        base_url=base_url,
                        model=model,
                        runs=args.runs,
                    )
                )
            except Exception as exc:
                results.append({"model": model, "ok": False, "error": str(exc)})

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "ollama_url": base_url,
        "runs": args.runs,
        "results": results,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    _print_table(results)
    print(f"\nWrote {SUMMARY_PATH}")
    return 0 if any(item.get("ok") for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
