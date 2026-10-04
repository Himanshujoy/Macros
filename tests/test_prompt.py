"""The writer's instructions and the checks must agree, or a careful writer would still be refused."""
from pathlib import Path

from macro import analysis

PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "analysis.md").read_text(encoding="utf-8")


def test_the_prompt_names_every_field_the_checks_know():
    for field in ("snapshot_id", "model", "written_at", *analysis.SECTIONS):
        assert f"`{field}`" in PROMPT, field
    for name in analysis.OUTLOOK_REQUIRED + analysis.OUTLOOK_OPTIONAL:
        assert f"`outlook.{name}`" in PROMPT, name


def test_the_prompt_states_the_word_limits_and_the_refused_characters():
    assert f"{analysis.MIN_WORDS} to {analysis.MAX_WORDS} words" in PROMPT
    for mark in analysis.MARKUP:
        assert mark in PROMPT, mark


def test_the_prompt_tells_the_writer_to_stay_inside_the_facts():
    assert "Use only the numbers in the facts file" in PROMPT
    assert "Plain text only" in PROMPT
    assert "work/facts.json" in PROMPT and "work/analysis.json" in PROMPT
