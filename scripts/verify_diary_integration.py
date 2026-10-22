"""Bounded live Gemini smoke test through collection, handlers and the real extractor.

Run from the repo root: python -X utf8 -m scripts.verify_diary_integration OUTPUT_DIR.
Only Telegram and Sheets are fakes. No production user records are read or written.
Credit status is checked separately with read_openrouter_limits.mjs before running.
Each response is persisted immediately. A provider failure stops the run, including 402.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

from src.config.settings import get_settings
from src.services.llm.client import LLMClient
from src.services.llm.prompts.habits import HABIT_EXTRACTION_SYSTEM_PROMPT
from tests.test_diary_integration import CASES, add, collect, confirm, make_context, start


class RecordingClient(LLMClient):
    def with_structured_output(self, schema, *, max_tokens=None, timeout=None):
        chain = super().with_structured_output(schema, max_tokens=max_tokens, timeout=timeout)
        owner = self
        class RecordedChain:
            async def ainvoke(self, messages):
                owner.trace = {"max_tokens": max_tokens, "timeout_seconds": timeout,
                               "message_count": len(messages)}
                begun = time.monotonic()
                try:
                    result = await chain.ainvoke(messages)
                    raw = result["raw"]
                    owner.trace.update(
                        content=raw.content,
                        metadata=raw.response_metadata,
                        usage=raw.usage_metadata,
                        parsing_error=type(result["parsing_error"]).__name__
                        if result.get("parsing_error") else None,
                    )
                    return result
                except Exception as exc:
                    owner.trace["error_type"] = type(exc).__name__
                    owner.trace["http_status"] = getattr(exc, "status_code", None)
                    raise
                finally:
                    owner.trace["latency_seconds"] = round(time.monotonic() - begun, 3)
        return RecordedChain()


async def main(output, case_ids=None):
    output.mkdir(parents=True, exist_ok=False)
    settings = get_settings()
    if settings.llm_model != "google/gemini-3.8-flash":
        raise RuntimeError("This evaluation must use the approved configured Gemini model")
    (output / "run.json").write_text(json.dumps({
        "model": settings.llm_model,
        "prompt_sha256": hashlib.sha256(HABIT_EXTRACTION_SYSTEM_PROMPT.encode()).hexdigest(),
        "base_max_tokens": settings.llm_max_tokens,
        "temperature": settings.llm_temperature,
        "timeout_seconds": settings.llm_timeout_seconds,
        "real_services": ["OpenRouter", "Gemini"],
        "fake_services": ["Telegram", "Sheets", "Firestore"],
        "scope": "synthetic fixtures only; no production writes",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    client = RecordingClient()
    review = []
    holdout = json.loads(Path("docs/evals/2026-10-22/holdout/fixtures.json").read_text(encoding="utf-8"))
    cases = {**CASES, **{case["id"]: case for case in holdout["cases"]}}
    case_ids = case_ids or ["morning_and_ratings", "explicit_corrections", "sensitive_and_uncertain",
                           "ambiguous_time", "long_diary"]
    # At most twelve requests. Every scenario starts with its own session/history.
    for case_id in case_ids:
        deps, context = make_context()
        deps._llm_client = client
        await start(context)
        previous_diary = None
        for index, turn in enumerate(cases[case_id]["turns"]):
            await collect(context, turn["text"])
            session = await deps.session_repo().get(1)
            pending = session.pending_entry
            record = {
                "case_id": case_id, "turn": index + 1, "input": turn["text"],
                "pending": pending, "trace": client.trace,
                "processing_failed": session.temp_data.get("entry_processing_failed"),
                "field_mismatches": {key: {"expected": expected, "actual": pending.get(key)}
                                     for key, expected in turn["expected"].items()
                                     if pending.get(key) != expected},
                "unchanged_check": pending["diary"] == previous_diary if turn.get("unchanged")
                                   else None,
            }
            with (output / "responses.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            print(json.dumps({"case": case_id, "turn": index + 1,
                              "failed": record["processing_failed"],
                              "field_mismatches": len(record["field_mismatches"]) }), flush=True)
            review.append(f"## {case_id}, turn {index + 1}\n\n{pending['diary']}\n")
            (output / "texts.md").write_text("\n".join(review), encoding="utf-8")
            if record["processing_failed"]:
                (output / "blocker.json").write_text(json.dumps(client.trace, ensure_ascii=False,
                                                               default=str, indent=2), encoding="utf-8")
                return 1
            previous_diary = pending["diary"]
            if index < len(cases[case_id]["turns"]) - 1:
                await add(context)
        await confirm(context)
        saved = deps.sheets_client().appended[0][2]
        assert saved.diary == previous_diary
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(Path(sys.argv[1]), sys.argv[2:])))
