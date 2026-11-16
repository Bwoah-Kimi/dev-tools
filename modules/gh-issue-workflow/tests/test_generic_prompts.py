from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


def test_prompts_do_not_contain_product_or_model_locks():
    files = list((MODULE / "skills").rglob("*.md"))
    files += list((MODULE / "agents").rglob("*"))
    text = "\n".join(path.read_text(encoding="utf-8") for path in files if path.is_file())
    for forbidden in ("Zhen", "zhen", "LLVM/MLIR 21", "uv run --extra dev", "fable", "gpt-5.6-sol"):
        assert forbidden not in text


def test_work_queue_documents_policy_branches_and_merge_guard():
    text = (MODULE / "skills" / "gh-work-queue" / "SKILL.md").read_text(encoding="utf-8")
    for required in ("spec_policy", "openspec", "optional", "none", "project-context.md", "--admin", "opt-in"):
        assert required in text
