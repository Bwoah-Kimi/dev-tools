from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


def test_source_layout_is_complete():
    for skill in ("gh-plan-to-issues", "gh-sync-issues", "gh-work-queue"):
        assert (MODULE / "skills" / skill / "SKILL.md").is_file()
    assert (MODULE / "skills" / "_shared" / "issue_bundle.py").is_file()
    assert (MODULE / "agents" / "claude" / "gh-implementer.md").is_file()
    assert (MODULE / "agents" / "codex" / "gh-implementer.toml").is_file()
    assert (MODULE / "templates" / "parent_issue.yml").is_file()
