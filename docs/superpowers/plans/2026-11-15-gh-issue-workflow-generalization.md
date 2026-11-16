# GitHub Issue Workflow Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repository-local, configurable `gh-issue-workflow` module that preserves plan/bundle/sync/queue behavior without depending on `sw`, mandatory OpenSpec, or product-specific build agents.

**Architecture:** Import the existing skills and shared Python helpers into `modules/gh-issue-workflow`, establish an offline baseline, then add a shared configuration/runtime layer around the existing bundle and GitHub protocol. Keep generic engine code separate from repository profiles; add an agent-led init skill, read-only doctor, and manifest-based install/update lifecycle.

**Tech Stack:** Python 3.12+, pytest, PyYAML, Bash, GitHub CLI (`gh`), GitHub REST/GraphQL APIs, Markdown agent definitions.

**Design:** `docs/superpowers/specs/2026-11-15-gh-issue-workflow-generalization-design.md`

**Migration source:** `D:\Playground\sw\.agents\skills` and tool-native agents. The source is read only during migration tasks. Installed module code must never reference or read that checkout.

**Execution rules:**

- Work from `D:\dev-tools` unless a command explicitly names another directory.
- Use `python`, not a WindowsApps stub. Verify with `python --version` before Task 1.
- Do not modify `D:\Playground\sw`.
- Do not run live GitHub mutations. All `gh` mutations in tests use mocks.
- Commit only the files named by each task. Do not push without explicit user approval.
- Run `python -m pytest modules/gh-issue-workflow/tests -q` after every task and `python -m unittest discover -s tests -v` before the final commit.

---

## File Responsibility Map

- `modules/gh-issue-workflow/skills/_shared/workflow_config.py`: repository-root discovery, config defaults/loading, path resolution.
- `modules/gh-issue-workflow/skills/_shared/spec_policy.py`: three specification modes and spec-path validation.
- `modules/gh-issue-workflow/skills/_shared/approval.py`: approved-bundle hashing and tamper/staleness checks.
- `modules/gh-issue-workflow/skills/_shared/gh_context.py`: current-repository resolution and repository-scoped cache.
- `modules/gh-issue-workflow/skills/_shared/issue_bundle.py`: bundle parsing and optional `spec_impact` support.
- `modules/gh-issue-workflow/skills/_shared/issue_form.py`: configurable field mapping and policy-aware rendering.
- `modules/gh-issue-workflow/skills/_shared/work_queue_model.py`: configurable work issue type and queue/PR behavior.
- `modules/gh-issue-workflow/skills/gh-workflow-init/`: agent-led repository onboarding and profile helpers.
- `modules/gh-issue-workflow/install/gh_issue_workflow.py`: install/doctor/update filesystem lifecycle.
- `modules/gh-issue-workflow/install/install_gh_issue_workflow.sh`: cross-platform Bash entry point.
- `modules/gh-issue-workflow/templates/`: generic config, project-context, Issue, and PR templates.
- `modules/gh-issue-workflow/tests/`: offline unit, installer, and two-profile acceptance tests.

### Task 1: Import the Source and Establish a Structural Baseline

**Files:**
- Create: `modules/gh-issue-workflow/tests/test_structure.py`
- Create: `modules/gh-issue-workflow/requirements-dev.txt`
- Create: `modules/gh-issue-workflow/skills/`
- Create: `modules/gh-issue-workflow/agents/`
- Create: `modules/gh-issue-workflow/templates/`

- [ ] **Step 1: Write the failing structure test**

```python
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


def test_source_layout_is_complete():
    for skill in ("gh-plan-to-issues", "gh-sync-issues", "gh-work-queue"):
        assert (MODULE / "skills" / skill / "SKILL.md").is_file()
    assert (MODULE / "skills" / "_shared" / "issue_bundle.py").is_file()
    assert (MODULE / "agents" / "claude" / "gh-implementer.md").is_file()
    assert (MODULE / "agents" / "codex" / "gh-implementer.toml").is_file()
    assert (MODULE / "templates" / "parent_issue.yml").is_file()
```

- [ ] **Step 2: Verify that the test fails**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_structure.py -q`
Expected: FAIL because `modules/gh-issue-workflow/skills` does not exist.

- [ ] **Step 3: Import the source without changing `sw`**

```bash
mkdir -p modules/gh-issue-workflow/{skills,agents/claude,agents/codex,templates,tests}
cp -R D:/Playground/sw/.agents/skills/_shared modules/gh-issue-workflow/skills/
cp -R D:/Playground/sw/.agents/skills/gh-plan-to-issues modules/gh-issue-workflow/skills/
cp -R D:/Playground/sw/.agents/skills/gh-sync-issues modules/gh-issue-workflow/skills/
cp -R D:/Playground/sw/.agents/skills/gh-work-queue modules/gh-issue-workflow/skills/
cp D:/Playground/sw/.claude/agents/gh-*.md modules/gh-issue-workflow/agents/claude/
cp D:/Playground/sw/.codex/agents/gh-*.toml modules/gh-issue-workflow/agents/codex/
cp D:/Playground/sw/.github/ISSUE_TEMPLATE/parent_issue.yml modules/gh-issue-workflow/templates/
cp D:/Playground/sw/.github/ISSUE_TEMPLATE/sub_issue.yml modules/gh-issue-workflow/templates/
cp D:/Playground/sw/.github/pull_request_template.md modules/gh-issue-workflow/templates/
cp D:/Playground/sw/.agents/skills/_tests/*.py modules/gh-issue-workflow/tests/
```

Create `requirements-dev.txt`:

```text
pytest>=8,<10
PyYAML>=6,<7
```

Install the test dependencies:

```bash
python -m pip install -r modules/gh-issue-workflow/requirements-dev.txt
```

- [ ] **Step 4: Verify the structural baseline**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_structure.py -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow
git commit -m "Import GitHub Issue workflow skills"
```

### Task 2: Make the Original Offline Suite Independent of `sw`

**Files:**
- Create: `modules/gh-issue-workflow/tests/conftest.py`
- Modify: `modules/gh-issue-workflow/tests/test_issue_bundle.py:9-15`
- Modify: `modules/gh-issue-workflow/tests/test_work_queue_cli.py:8-13`
- Modify: `modules/gh-issue-workflow/tests/test_work_queue_model.py:6-9`
- Modify: `modules/gh-issue-workflow/tests/test_plan_archive.py`

- [ ] **Step 1: Run the imported tests to capture the expected failure**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: collection errors because tests resolve `.codex/skills` relative to `dev-tools`, not the target module.

- [ ] **Step 2: Add one canonical test import path**

Create `conftest.py`:

```python
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
SHARED = MODULE / "skills" / "_shared"
sys.path.insert(0, str(SHARED))
```

In each imported test, replace its `ROOT`/`.codex` setup with:

```python
MODULE = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE
```

Set `VALIDATOR` in `test_issue_bundle.py` to:

```python
VALIDATOR = MODULE / "skills" / "gh-plan-to-issues" / "scripts" / "gh_validate_bundle.py"
```

In `test_issue_bundle.py`, replace `ROOT / ".github/ISSUE_TEMPLATE/sub_issue.yml"` with `MODULE / "templates" / "sub_issue.yml"`. Replace every remaining `ROOT` fixture path with the equivalent path under `MODULE`; retain all test behavior and assertions.

- [ ] **Step 3: Verify all 17 original tests pass without `sw`**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: `18 passed` (17 imported tests plus the structure test).

Run: `python -c "from pathlib import Path; assert not Path('D:/Playground/sw/.agents/skills/_shared/issue_bundle.py').samefile('modules/gh-issue-workflow/skills/_shared/issue_bundle.py')"`
Expected: exit 0, proving the module is a distinct file.

- [ ] **Step 4: Commit**

```bash
git add modules/gh-issue-workflow/tests
git commit -m "Make Issue workflow tests standalone"
```

### Task 3: Add Repository-Root Discovery and Typed Configuration

**Files:**
- Create: `modules/gh-issue-workflow/skills/_shared/workflow_config.py`
- Create: `modules/gh-issue-workflow/templates/config.json`
- Create: `modules/gh-issue-workflow/tests/test_workflow_config.py`

- [ ] **Step 1: Write failing config tests**

```python
import json
import subprocess
from pathlib import Path

import pytest
from workflow_config import ConfigError, discover_repo_root, load_config


def init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    return path


def test_config_loads_repository_profile(tmp_path):
    repo = init_repo(tmp_path)
    profile = repo / ".agents" / "gh-issue-workflow"
    profile.mkdir(parents=True)
    (profile / "config.json").write_text(json.dumps({
        "version": 1,
        "spec_policy": {"mode": "none", "roots": []},
        "issue_types": {"parent": "Initiative", "work": "Work Item"},
        "paths": {"cache": "artifacts/github-cache"}
    }), encoding="utf-8")
    config = load_config(repo)
    assert config.parent_issue_type == "Initiative"
    assert config.work_issue_type == "Work Item"
    assert config.spec_mode == "none"
    assert config.output_path("cache") == repo / "artifacts" / "github-cache"


def test_discovery_works_from_a_subdirectory(tmp_path):
    repo = init_repo(tmp_path)
    nested = repo / "src" / "nested"
    nested.mkdir(parents=True)
    assert discover_repo_root(nested) == repo.resolve()


def test_unknown_spec_mode_fails(tmp_path):
    repo = init_repo(tmp_path)
    with pytest.raises(ConfigError, match="spec_policy.mode"):
        load_config(repo, overrides={"spec_policy": {"mode": "automatic"}})
```

- [ ] **Step 2: Verify the tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_workflow_config.py -q`
Expected: FAIL with `ModuleNotFoundError: workflow_config`.

- [ ] **Step 3: Implement config loading and safe path resolution**

Create `templates/config.json`:

```json
{
  "version": 1,
  "issue_types": {"parent": "Feature", "work": "Task"},
  "templates": {
    "parent": ".github/ISSUE_TEMPLATE/parent_issue.yml",
    "work": ".github/ISSUE_TEMPLATE/sub_issue.yml",
    "pr": ".github/pull_request_template.md"
  },
  "fields": {
    "parent": {
      "objective": "objective",
      "scope": "scope",
      "assumptions": "assumptions",
      "atom_registry": "atom_registry",
      "coverage_matrix": "coverage_matrix"
    },
    "work": {
      "intent_and_contract": "intent_and_contract",
      "owned_atoms": "owned_atoms",
      "spec_impact": "spec_impact",
      "implementation_plan": "implementation_plan",
      "file_and_interface_scope": "file_and_interface_scope",
      "acceptance_checks": "acceptance_checks",
      "assumptions_defaults": "assumptions_defaults",
      "references": "references",
      "handoff_contract": "handoff_contract",
      "dependencies": "dependencies"
    }
  },
  "spec_policy": {"mode": "none", "roots": []},
  "validation": {"setup": [], "commands": []},
  "agents": {
    "preflight": "gh-preflight",
    "bundle_reviewer": "gh-bundle-reviewer",
    "environment": "gh-validation-runner",
    "implementer": "gh-implementer",
    "spec_reviewer": "gh-spec-reviewer",
    "code_reviewer": "gh-code-reviewer",
    "merge_closer": "gh-merge-closer"
  },
  "paths": {
    "plan": "out/gh-plan-to-issues",
    "queue": "out/gh-work-queue",
    "cache": "out/gh-skills"
  },
  "pr_policy": {"close_keyword": "Fixes", "merge": "opt-in", "allow_admin": false}
}
```

Implement `workflow_config.py` with this public interface and exact root/path behavior:

```python
from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    pass


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "issue_types": {"parent": "Feature", "work": "Task"},
    "templates": {
        "parent": ".github/ISSUE_TEMPLATE/parent_issue.yml",
        "work": ".github/ISSUE_TEMPLATE/sub_issue.yml",
        "pr": ".github/pull_request_template.md",
    },
    "spec_policy": {"mode": "none", "roots": []},
    "paths": {
        "plan": "out/gh-plan-to-issues",
        "queue": "out/gh-work-queue",
        "cache": "out/gh-skills",
    },
}


def discover_repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise ConfigError(f"Not inside a Git repository: {start}: {result.stderr.strip()}")
    return Path(result.stdout.strip()).resolve()


def _merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@dataclass(frozen=True)
class WorkflowConfig:
    repo_root: Path
    data: dict[str, Any]

    @property
    def parent_issue_type(self) -> str:
        return str(self.data["issue_types"]["parent"])

    @property
    def work_issue_type(self) -> str:
        return str(self.data["issue_types"]["work"])

    @property
    def spec_mode(self) -> str:
        return str(self.data["spec_policy"]["mode"])

    def output_path(self, name: str) -> Path:
        value = Path(self.data["paths"][name])
        path = value if value.is_absolute() else self.repo_root / value
        resolved = path.resolve()
        if resolved != self.repo_root and self.repo_root not in resolved.parents:
            raise ConfigError(f"Output path escapes repository: {value}")
        return resolved


def load_config(repo_root: Path, overrides: dict[str, Any] | None = None) -> WorkflowConfig:
    root = discover_repo_root(repo_root)
    path = root / ".agents" / "gh-issue-workflow" / "config.json"
    profile: dict[str, Any] = {}
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ConfigError(f"Config must be a JSON object: {path}")
        profile = payload
    merged = _merge(DEFAULT_CONFIG, profile)
    if overrides:
        merged = _merge(merged, overrides)
    if merged["spec_policy"]["mode"] not in {"openspec", "optional", "none"}:
        raise ConfigError("spec_policy.mode must be openspec, optional, or none")
    return WorkflowConfig(repo_root=root, data=merged)
```

Add the full field, validation, agent, template, and PR defaults from `templates/config.json` to `DEFAULT_CONFIG` before running the tests. Add a test that serializes `DEFAULT_CONFIG` and compares it with `templates/config.json`, preventing drift.

- [ ] **Step 4: Run config and original tests**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills/_shared/workflow_config.py modules/gh-issue-workflow/templates/config.json modules/gh-issue-workflow/tests/test_workflow_config.py
git commit -m "Add repository workflow configuration"
```

### Task 4: Implement the Three Specification Policies

**Files:**
- Create: `modules/gh-issue-workflow/skills/_shared/spec_policy.py`
- Modify: `modules/gh-issue-workflow/skills/_shared/issue_bundle.py`
- Modify: `modules/gh-issue-workflow/skills/gh-plan-to-issues/scripts/gh_validate_bundle.py`
- Create: `modules/gh-issue-workflow/tests/test_spec_policy.py`

- [ ] **Step 1: Add failing three-mode tests**

```python
import json
from pathlib import Path

import pytest
from issue_bundle import IssueBundleError, load_issue_bundle
from spec_policy import validate_spec_path


def bundle_without_impact(tmp_path: Path) -> Path:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({
        "parent": {
            "title": "Plan", "objective": "Ship", "scope": [],
            "assumptions": [], "atom_registry": ["A1: Behavior"]
        },
        "items": [{
            "id": "S1", "title": "Task", "intent_and_contract": "Preserve behavior",
            "owned_atoms": ["A1: Behavior"], "implementation_plan": "Implement and test",
            "file_and_interface_scope": "src/module.py",
            "acceptance_checks": ["[A1] Behavior passes"]
        }]
    }), encoding="utf-8")
    return path


def test_none_policy_allows_missing_spec_impact(tmp_path):
    _, items, _ = load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="none")
    assert items[0].spec_impact is None


def test_openspec_policy_still_requires_spec_impact(tmp_path):
    with pytest.raises(IssueBundleError, match="spec_impact"):
        load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="openspec")


def test_spec_path_rules():
    assert validate_spec_path("openspec/specs/cli/spec.md", "openspec", []) is None
    assert validate_spec_path("docs/design/cli.md", "optional", ["docs"]) is None
    assert validate_spec_path("docs/design/cli.md", "optional", []) is None
    assert validate_spec_path("../outside.md", "optional", []) is not None
    assert validate_spec_path("docs/design/cli.md", "openspec", []) is not None
```

- [ ] **Step 2: Verify policy tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_spec_policy.py -q`
Expected: FAIL because `spec_policy` and `spec_mode` do not exist.

- [ ] **Step 3: Implement policy validation and optional parsing**

Create `spec_policy.py`:

```python
from pathlib import PurePosixPath


def _relative_parts(value: str) -> tuple[str, ...] | None:
    path = PurePosixPath(value)
    if "\\" in value or path.is_absolute() or ".." in path.parts:
        return None
    return path.parts


def validate_spec_path(value: str, mode: str, roots: list[str]) -> str | None:
    parts = _relative_parts(value)
    if parts is None:
        return f"Spec path must be repository-relative and may not contain '..': {value}"
    if mode == "none":
        return None
    if mode == "openspec":
        if len(parts) >= 4 and parts[:2] == ("openspec", "specs") and parts[-1] == "spec.md":
            return None
        return f"Expected openspec/specs/**/spec.md: {value}"
    if roots and not any(value == root or value.startswith(root.rstrip("/") + "/") for root in roots):
        return f"Spec path is outside configured roots {roots}: {value}"
    return None
```

Change `WorkItem.spec_impact` to `SpecImpact | None`. Add `spec_mode: str = "openspec"` to `load_issue_bundle`. When the field is absent and mode is `none`, assign `None`; otherwise retain `_parse_spec_impact`. Reject a missing field in `openspec` and `optional` modes.

Add `--spec-mode {openspec,optional,none}` and repeatable `--spec-root` to `gh_validate_bundle.py`. Replace `_is_canonical_spec_path` calls with `validate_spec_path`. Skip the entire spec block when `item.spec_impact is None`; render `0 expected spec paths` for that item.

- [ ] **Step 4: Run the complete suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass, including unchanged original OpenSpec tests because the default remains `openspec`.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/tests/test_spec_policy.py
git commit -m "Add configurable specification policies"
```

### Task 5: Make Issue Forms and Rendering Configurable

**Files:**
- Modify: `modules/gh-issue-workflow/skills/_shared/issue_form.py`
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/scripts/gh_sync_issues.py`
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/scripts/gh_sync_plan.py`
- Create: `modules/gh-issue-workflow/tests/test_configured_forms.py`

- [ ] **Step 1: Add failing renderer tests**

```python
import json
from pathlib import Path

import yaml
from issue_form import mapped_field_ids, render_sub_issue_body
from issue_bundle import load_issue_bundle
from test_spec_policy import bundle_without_impact


def test_none_policy_omits_spec_field(tmp_path):
    _, items, _ = load_issue_bundle(bundle_without_impact(tmp_path), spec_mode="none")
    form_path = tmp_path / "form.yml"
    form_path.write_text(yaml.safe_dump({
        "name": "Work", "description": "Work item", "body": [{
            "type": "textarea", "id": "intent_and_contract",
            "attributes": {"label": "Intent"}
        }]
    }), encoding="utf-8")
    body = render_sub_issue_body(
        form_path=form_path, change_id="run-S1", item=items[0], dependencies_text=""
    )
    assert "Expected Spec Impact" not in body


def test_field_mapping_uses_repository_ids():
    mapping = {"work": {"intent_and_contract": "contract", "spec_impact": "specs"}}
    assert mapped_field_ids(mapping, "work", "openspec") == {
        "contract", "specs"
    }


def test_none_policy_removes_spec_from_required_ids():
    mapping = {"work": {"intent_and_contract": "contract", "spec_impact": "specs"}}
    assert mapped_field_ids(mapping, "work", "none") == {"contract"}
```

- [ ] **Step 2: Verify renderer tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_configured_forms.py -q`
Expected: FAIL because the helper and policy-aware rendering are absent.

- [ ] **Step 3: Implement field mapping and optional rendering**

Add this public helper to `issue_form.py`:

```python
def mapped_field_ids(mapping: dict, role: str, spec_mode: str) -> set[str]:
    fields = dict(mapping.get(role, {}))
    if spec_mode == "none":
        fields.pop("spec_impact", None)
    return {value for value in fields.values() if isinstance(value, str) and value}


def mapped_field_id(mapping: dict, role: str, logical_name: str) -> str:
    value = mapping.get(role, {}).get(logical_name, logical_name)
    if not isinstance(value, str) or not value:
        raise IssueFormError(f"Invalid {role}.{logical_name} field mapping: {value!r}")
    return value
```

Allow `render_sub_issue_body` to accept the existing `form` object or a `form_path`, resolving the path when supplied. When `item.spec_impact is None`, omit that section entirely. Use `mapped_field_id` for field lookup rather than assuming configured YAML IDs equal logical bundle keys.

In both sync scripts, replace fixed required-ID sets with `mapped_field_ids(config.data["fields"], role, config.spec_mode)`. Pass `config.parent_issue_type` to parent issue-type resolution and `config.work_issue_type` to child issue-type resolution. Resolve form paths from `WorkflowConfig.repo_root` and configured template paths.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/tests/test_configured_forms.py
git commit -m "Configure Issue forms and rendering"
```

### Task 6: Isolate Repository Context and Support GitHub Enterprise URLs

**Files:**
- Modify: `modules/gh-issue-workflow/skills/_shared/gh_context.py`
- Modify: `modules/gh-issue-workflow/skills/_shared/gh_issues.py`
- Create: `modules/gh-issue-workflow/tests/test_github_context.py`

- [ ] **Step 1: Add failing context and URL tests**

```python
import json
from pathlib import Path

import pytest
from gh_context import resolve_context
from gh_issues import GitHubIssueError, extract_issue_url


def test_cache_cannot_override_current_repo(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "repo": "old/project", "repo_owner": "old", "repo_name": "project",
        "host": "github.com", "repo_root": str(tmp_path / "old")
    }), encoding="utf-8")
    monkeypatch.setattr("gh_context._repo_view", lambda repo: {
        "nameWithOwner": "new/current", "name": "current",
        "owner": {"login": "new"}, "url": "https://github.com/new/current"
    })
    context = resolve_context(repo_root=tmp_path, context_path=cache)
    assert context.repo == "new/current"


def test_dry_resolution_does_not_write_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("gh_context._repo_view", lambda repo: {
        "nameWithOwner": "o/r", "name": "r", "owner": "o",
        "url": "https://git.example.com/o/r"
    })
    cache = tmp_path / "cache.json"
    context = resolve_context(repo_root=tmp_path, context_path=cache, write_cache=False)
    assert context.host == "git.example.com"
    assert not cache.exists()


def test_enterprise_issue_url():
    output = "Created https://git.example.com/acme/tools/issues/42\n"
    assert extract_issue_url(output, "git.example.com") == output.strip()
    with pytest.raises(GitHubIssueError):
        extract_issue_url(output, "other.example.com")
```

- [ ] **Step 2: Verify the tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_github_context.py -q`
Expected: FAIL on unexpected parameters and missing public parser.

- [ ] **Step 3: Implement scoped context and host-aware parsing**

Extend `GhContext` with `host: str` and `repo_root: str`. Request `url` in `_repo_view`; derive `host` with `urllib.parse.urlsplit(payload["url"]).hostname`, rejecting an empty host.

Add `repo_root: Path`, `context_path: Path`, and `write_cache: bool = True` to `resolve_context`. Always call `_repo_view` when no explicit repo is supplied. Use cache only when its `repo` and resolved `repo_root` match the fresh result. Write cache only when `write_cache` is true.

Replace the private fixed-host parser with:

```python
import re


def extract_issue_url(output: str, github_host: str) -> str:
    match = re.search(
        rf"https://{re.escape(github_host)}/[^\s]+/issues/\d+", output
    )
    if match is None:
        raise GitHubIssueError(
            f"Could not parse issue URL for host {github_host} from output:\n{output}"
        )
    return match.group(0)
```

Pass `context.host` into `GitHubIssueClient` and retain `github.com` only as the constructor default for backward-compatible unit tests.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills/_shared/gh_context.py modules/gh-issue-workflow/skills/_shared/gh_issues.py modules/gh-issue-workflow/tests/test_github_context.py
git commit -m "Isolate GitHub repository context"
```

### Task 7: Make Dry-Run Free of Persistent Side Effects

**Files:**
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/scripts/gh_sync_plan.py`
- Modify: `modules/gh-issue-workflow/skills/gh-work-queue/scripts/review_package.sh`
- Create: `modules/gh-issue-workflow/tests/test_dry_run.py`
- Create: `modules/gh-issue-workflow/tests/fixtures/gh`

- [ ] **Step 1: Add a failing filesystem snapshot test**

```python
import json
import subprocess
import sys
from pathlib import Path
from test_spec_policy import bundle_without_impact

SYNC = Path(__file__).resolve().parents[1] / "skills" / "gh-sync-issues" / "scripts" / "gh_sync_plan.py"


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in root.rglob("*") if path.is_file()
    }


def test_dry_run_does_not_create_archive_or_state(tmp_path):
    bundle = bundle_without_impact(tmp_path)
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    before = snapshot(tmp_path)
    result = subprocess.run([
        sys.executable, str(SYNC), "--plan", str(plan), "--bundle", str(bundle),
        "--repo", "o/r", "--spec-mode", "none", "--dry-run"
    ], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert snapshot(tmp_path) == before
```

Mock network access in this test by prepending a fixture `gh` executable that handles only `repo view` and read-only issue-type/template queries. Record every invocation in a file outside the repository snapshot; assert no recorded argument list contains `create`, `edit`, `delete`, `merge`, `POST`, `PATCH`, or `DELETE`.

- [ ] **Step 2: Verify the side-effect test fails**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_dry_run.py -q`
Expected: FAIL because `out/` and context/archive files appear and `--spec-mode` is unknown.

- [ ] **Step 3: Separate preparation from persistence**

Add `--spec-mode`, `--spec-root`, `--config`, and `--output-root` arguments. Load `WorkflowConfig` before preparing a run.

Change `_prepare_run(args)` to `_prepare_run(args, *, persist: bool)`. In dry mode:

- call `resolve_context(repo_root=config.repo_root, context_path=context_path, write_cache=False)`;
- load and hash the input bundle in memory;
- use `args.bundle` for parsing/rendering;
- do not call `archive_file` or `write_json`;
- do not add `archived_path` or other archive metadata to the payload;
- compute run/output identifiers without creating their parent directories.

Call `_prepare_run(args, persist=not args.dry_run)` from `main`. Keep formal run archiving and state writes unchanged.

Update `review_package.sh` to accept a required fourth `OUTPUT_ROOT` argument and create the review diff only below that directory:

```bash
output_root=$4
dir="${output_root}/review/${issue}"
mkdir -p "$dir"
```

Pass `WorkflowConfig.output_path("queue")` from the skill rather than relying on the caller's current directory.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass; the dry-run snapshot remains identical.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/tests/test_dry_run.py
git commit -m "Remove dry-run persistent side effects"
```

### Task 8: Enforce Approved-Bundle Integrity Before Sync

**Files:**
- Create: `modules/gh-issue-workflow/skills/_shared/approval.py`
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/scripts/gh_sync_plan.py`
- Modify: `modules/gh-issue-workflow/skills/gh-plan-to-issues/SKILL.md`
- Create: `modules/gh-issue-workflow/tests/test_approval.py`

- [ ] **Step 1: Add failing approval tests**

```python
import pytest
from approval import ApprovalError, load_approved_bundle, write_approval


def test_approval_round_trip(tmp_path):
    bundle = {"parent": {"title": "P"}, "items": []}
    path = write_approval(tmp_path / "approved.json", bundle, "none")
    assert load_approved_bundle(path, bundle, "none") == bundle


def test_tampered_bundle_is_rejected(tmp_path):
    original = {"parent": {"title": "P"}, "items": []}
    path = write_approval(tmp_path / "approved.json", original, "none")
    changed = {"parent": {"title": "Changed"}, "items": []}
    with pytest.raises(ApprovalError, match="hash"):
        load_approved_bundle(path, changed, "none")


def test_policy_change_is_rejected(tmp_path):
    bundle = {"parent": {"title": "P"}, "items": []}
    path = write_approval(tmp_path / "approved.json", bundle, "none")
    with pytest.raises(ApprovalError, match="policy"):
        load_approved_bundle(path, bundle, "openspec")
```

- [ ] **Step 2: Verify approval tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_approval.py -q`
Expected: FAIL with `ModuleNotFoundError: approval`.

- [ ] **Step 3: Implement approval metadata and preflight verification**

Create `approval.py`:

```python
import json
from pathlib import Path
from issue_bundle import bundle_sha256


class ApprovalError(RuntimeError):
    pass


def write_approval(path: Path, bundle: dict, spec_mode: str) -> Path:
    payload = {
        "version": 1,
        "bundle_sha256": bundle_sha256(bundle),
        "spec_policy": spec_mode,
        "bundle": bundle,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_approved_bundle(path: Path, current_bundle: dict, spec_mode: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("spec_policy") != spec_mode:
        raise ApprovalError("Approved specification policy does not match current policy")
    if payload.get("bundle_sha256") != bundle_sha256(current_bundle):
        raise ApprovalError("Approved bundle hash does not match current bundle")
    if payload.get("bundle") != current_bundle:
        raise ApprovalError("Approved bundle content does not match current bundle")
    return current_bundle
```

Add `--approved-bundle` to `gh_sync_plan.py`; it is required unless `--dry-run` is present. In `main`, load and verify approval before `_prepare_run` so stale approval cannot trigger cache, archive, or remote writes.

Update the plan skill's approval step to call a small CLI exposed by `approval.py`:

```bash
python3 .agents/skills/_shared/approval.py write \
  --bundle /path/to/bundle.json \
  --approved-bundle /path/to/review/approved-bundle.json \
  --spec-mode openspec
```

Implement `write` and `verify` argparse subcommands using the functions above.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/tests/test_approval.py
git commit -m "Verify approved bundles before synchronization"
```

### Task 9: Verify Configured Sync and Dependency Reconciliation with Mock GitHub

**Files:**
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/scripts/gh_sync_issues.py`
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/scripts/gh_sync_plan.py`
- Create: `modules/gh-issue-workflow/tests/test_sync_reconciliation.py`
- Modify: `modules/gh-issue-workflow/tests/fixtures/gh`

- [ ] **Step 1: Add failing mock sync tests**

Use a bundle with two work items where `S2.dependencies == ["S1"]`. Configure parent type `Initiative` and work type `Work Item`. The fake `gh` must return deterministic IDs/numbers for create/list operations and record all mutations.

```python
def test_sync_uses_configured_types_and_native_dependencies(sync_env):
    result = run_sync(sync_env, approved=True)
    assert result.returncode == 0, result.stderr
    calls = read_gh_calls(sync_env)
    assert any(call["issue_type"] == "Initiative" for call in calls if call["op"] == "create-parent")
    children = [call for call in calls if call["op"] == "create-work"]
    assert {call["issue_type"] for call in children} == {"Work Item"}
    blocked = [call for call in calls if call["op"] == "blocked-by"]
    assert [(call["item"], call["blocker"]) for call in blocked] == [("S2", "S1")]


def test_second_sync_resumes_without_duplicate_issues(sync_env):
    first = run_sync(sync_env, approved=True)
    assert first.returncode == 0, first.stderr
    second = run_sync(sync_env, approved=True)
    assert second.returncode == 0, second.stderr
    creates = [call for call in read_gh_calls(sync_env) if call["op"].startswith("create-")]
    assert len(creates) == 3
```

Implement the `sync_env` fixture in the test file: create a temporary Git repo, generic config, templates, plan, approved bundle, and fake `gh` log. Return a `SimpleNamespace` containing `repo`, `plan`, `bundle`, `approved`, `environment`, and `gh_log`. The fixture must not use `sw` paths. Use these exact helpers:

```python
SYNC = Path(__file__).resolve().parents[1] / "skills" / "gh-sync-issues" / "scripts" / "gh_sync_plan.py"


def run_sync(env, approved: bool):
    args = [
        sys.executable, str(SYNC), "--repo", "o/r",
        "--plan", str(env.plan), "--bundle", str(env.bundle),
        "--config", str(env.repo / ".agents/gh-issue-workflow/config.json"),
    ]
    if approved:
        args.extend(["--approved-bundle", str(env.approved)])
    else:
        args.append("--dry-run")
    return subprocess.run(
        args, cwd=env.repo, env=env.environment,
        text=True, capture_output=True, check=False,
    )


def read_gh_calls(env) -> list[dict]:
    if not env.gh_log.exists():
        return []
    return [json.loads(line) for line in env.gh_log.read_text(encoding="utf-8").splitlines()]
```

- [ ] **Step 2: Verify the tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_sync_reconciliation.py -q`
Expected: FAIL because configured type/field arguments are not wired through sync.

- [ ] **Step 3: Complete sync config injection**

Pass a `WorkflowConfig` object through `gh_sync_plan.py` and `sync_bundle` rather than reading process-global constants. Use configured parent/work types, mapped form IDs, output roots, and spec mode. Keep `CHANGE_ID`, run IDs, native sub-issue reconciliation, blocked-by reconciliation, supersession, and resume logic unchanged.

Before any `gh` mutation, call the approval verifier and local preflight. On error, print `ERROR: <repository>: <operation>: <reason>` to stderr and return nonzero without writing a success state.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass; the second sync adds no create calls.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/tests
git commit -m "Generalize Issue synchronization"
```

### Task 10: Generalize Queue Membership and PR Rendering

**Files:**
- Modify: `modules/gh-issue-workflow/skills/_shared/work_queue_model.py`
- Modify: `modules/gh-issue-workflow/skills/gh-work-queue/scripts/gh_work_queue.py`
- Modify: `modules/gh-issue-workflow/templates/pull_request_template.md`
- Create: `modules/gh-issue-workflow/tests/test_configured_queue.py`

- [ ] **Step 1: Add failing queue tests**

```python
from work_queue_model import QueueIssue, list_open_task_issues, render_pr_body
from test_work_queue_model import _issue


def test_queue_uses_configured_work_type(monkeypatch):
    def raw_issue(number: int, type_name: str) -> dict:
        return {
            "id": f"id-{number}", "number": number, "title": f"t-{number}",
            "url": f"https://github.com/o/r/issues/{number}", "body": "", "state": "OPEN",
            "issueType": {"name": type_name}, "blockedBy": {"nodes": []},
            "closedByPullRequestsReferences": {"nodes": []},
        }

    monkeypatch.setattr("work_queue_model.run_graphql", lambda **kwargs: {
        "repository": {"issues": {
            "nodes": [raw_issue(1, "Task"), raw_issue(2, "Work Item")],
            "pageInfo": {"hasNextPage": False},
        }}
    })
    issues = list_open_task_issues(owner="o", name="r", work_issue_type="Work Item")
    assert [issue.issue_number for issue in issues] == [2]


def test_pr_template_uses_configured_close_keyword(tmp_path):
    template = tmp_path / "pr.md"
    template.write_text("{{CLOSE_KEYWORD}} #{{ISSUE_NUMBER}}\n{{TESTS_RUN}}\n", encoding="utf-8")
    body = render_pr_body(
        template_path=template, issue=_issue(number=42, blocked_by=[]),
        specs_changed="(none; documentation only)", tests_run="- `pytest`",
        close_keyword="Resolves"
    )
    assert body.startswith("Resolves #42\n")
```

Add a queue CLI test that configures `Work Item` and asserts `show` accepts that type while rejecting another type with a nonzero exit.

- [ ] **Step 2: Verify queue tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_configured_queue.py -q`
Expected: FAIL on the new parameters and close-keyword placeholder.

- [ ] **Step 3: Implement configured queue behavior**

Add `work_issue_type: str = "Task"` to `list_open_task_issues`; compare `issue.issue_type` to that value. Add `expected_issue_type: str = "Task"` to queue `show` validation.

Extend `render_pr_body` with:

```python
def render_pr_body(
    *, template_path, issue, specs_changed, tests_run,
    close_keyword: str = "Fixes",
) -> str:
    if not template_path.exists():
        return ""
    template = template_path.read_text(encoding="utf-8")
    return (
        template.replace("{{CLOSE_KEYWORD}}", close_keyword)
        .replace("{{ISSUE_NUMBER}}", str(issue.issue_number))
        .replace("{{SPECS_CHANGED}}", specs_changed or "(none; see issue rationale)")
        .replace("{{TESTS_RUN}}", tests_run or "(not run)")
    )
```

Load `WorkflowConfig` in queue CLI common setup, passing configured type, PR template, close keyword, and queue output path. Change the first line of `templates/pull_request_template.md` to `{{CLOSE_KEYWORD}} #{{ISSUE_NUMBER}}` so the configured keyword is actually used. Keep merge opt-in and reject any configuration where `pr_policy.allow_admin` is true.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/tests/test_configured_queue.py
git commit -m "Configure work queue and PR rendering"
```

### Task 11: Generalize Skill Prompts and Native Agent Definitions

**Files:**
- Modify: `modules/gh-issue-workflow/skills/gh-plan-to-issues/SKILL.md`
- Modify: `modules/gh-issue-workflow/skills/gh-sync-issues/SKILL.md`
- Modify: `modules/gh-issue-workflow/skills/gh-work-queue/SKILL.md`
- Modify: `modules/gh-issue-workflow/agents/claude/gh-*.md`
- Modify: `modules/gh-issue-workflow/agents/codex/gh-*.toml`
- Create: `modules/gh-issue-workflow/tests/test_generic_prompts.py`

- [ ] **Step 1: Add failing decoupling tests**

```python
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
```

- [ ] **Step 2: Verify prompt tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_generic_prompts.py -q`
Expected: FAIL on imported product/model references and missing policy branches.

- [ ] **Step 3: Rewrite workflow instructions around configuration**

In all three skills, instruct agents to read these files before planning or execution:

```text
.agents/gh-issue-workflow/config.json
.agents/gh-issue-workflow/project-context.md
```

Replace fixed output directories with the configured paths. Replace fixed `Feature`/`Task` wording with configured parent/work types.

In `gh-work-queue/SKILL.md`, replace the build/spec execution rules with these exact policy rules:

```markdown
### Repository policy execution

- Read `config.json` and `project-context.md`; their configured validation commands and cited normative documents are the repository contract.
- For `spec_policy: openspec`, read current canonical specs, reconcile intentional behavior after implementation and tests, then run `openspec validate --all --strict --no-interactive`.
- For `spec_policy: optional`, reconcile each cited specification document. Run OpenSpec validation only for actual OpenSpec impacts; otherwise validate the cited documents using the configured commands.
- For `spec_policy: none`, do not require `spec_impact` and record `spec review: skipped by repository policy`. Do not claim a spec review occurred.
- Run every command in `validation.setup` once per session, then run every command in `validation.commands` after implementation. Preserve logs below the configured queue path.
- Merge remains opt-in. Never use `--admin`, bypass required checks, or merge with unresolved non-outdated review threads.
```

Remove fixed model keys from Codex TOML and Claude Markdown agents; retain role names, tool constraints, output contracts, and escalation rules. Remove all product build instructions from environment/validation agents and replace them with configured command execution and log reporting.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills modules/gh-issue-workflow/agents modules/gh-issue-workflow/tests/test_generic_prompts.py
git commit -m "Remove product-specific workflow assumptions"
```

### Task 12: Implement Manifest-Based Install and Update

**Files:**
- Create: `modules/gh-issue-workflow/install/gh_issue_workflow.py`
- Create: `modules/gh-issue-workflow/install/install_gh_issue_workflow.sh`
- Create: `modules/gh-issue-workflow/tests/test_installer.py`

- [ ] **Step 1: Add failing installer tests**

```python
import json
import subprocess
import sys
from pathlib import Path

INSTALLER = Path(__file__).resolve().parents[1] / "install" / "gh_issue_workflow.py"


def run_install(repo: Path, action: str = "install", *extra: str):
    return subprocess.run([
        sys.executable, str(INSTALLER), action, "--repo", str(repo), *extra
    ], text=True, capture_output=True, check=False)


def test_install_and_update_preserve_profile(tmp_path):
    repo = make_git_repo(tmp_path)
    assert run_install(repo).returncode == 0
    profile = repo / ".agents" / "gh-issue-workflow" / "config.json"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text('{"version": 1, "custom": true}\n', encoding="utf-8")
    managed = repo / ".agents" / "skills" / "_shared" / "issue_bundle.py"
    managed.write_text("# locally changed\n", encoding="utf-8")
    result = run_install(repo, "update")
    assert result.returncode != 0
    assert "managed file changed" in result.stderr
    assert profile.read_text(encoding="utf-8") == '{"version": 1, "custom": true}\n'


def test_dry_run_writes_nothing(tmp_path):
    repo = make_git_repo(tmp_path)
    before = set(repo.rglob("*"))
    result = run_install(repo, "install", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert set(repo.rglob("*")) == before
```

Define `make_git_repo` in the test file using `subprocess.run(["git", "init", str(path)], check=True)`. Add a non-Git refusal test. Test link failure by importing `make_compatibility_link` directly, monkeypatching its platform link helper to raise `OSError`, and asserting the actionable `RuntimeError`; do not attempt to monkeypatch a subprocess.

- [ ] **Step 2: Verify installer tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_installer.py -q`
Expected: FAIL because the installer does not exist.

- [ ] **Step 3: Implement the installer**

Use these exact ownership rules in `gh_issue_workflow.py`:

```python
MANAGED_SKILLS = (
    "gh-plan-to-issues", "gh-sync-issues", "gh-work-queue", "_shared",
)
MANIFEST = ".agents/gh-issue-workflow/managed-files.json"


def file_sha256(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_managed(module: Path, repo: Path, dry_run: bool) -> dict[str, str]:
    import shutil
    hashes: dict[str, str] = {}
    for name in MANAGED_SKILLS:
        source = module / "skills" / name
        target = repo / ".agents" / "skills" / name
        if not dry_run:
            shutil.copytree(source, target, dirs_exist_ok=True)
        for path in source.rglob("*"):
            if path.is_file():
                relative = path.relative_to(module / "skills")
                hashes[str(Path(".agents/skills") / relative)] = file_sha256(path)
    return hashes
```

Before update, load the previous manifest and compare each recorded hash with the installed file. If a managed file changed locally, abort with `managed file changed: <path>`. Preserve `.agents/gh-issue-workflow/config.json`, `project-context.md`, and all `.github` files.

Write the new manifest only after all managed copies and links succeed. Implement `make_compatibility_link(repo, host, dry_run)` with `link.symlink_to(Path(os.path.relpath(target, link.parent)), target_is_directory=True)` on POSIX and `cmd /c mklink /J <link> <target>` on Windows. If either `.claude/skills` or `.codex/skills` cannot be linked, raise `RuntimeError` with instructions to enable symlink/junction support; do not fall back to copies.

Create the Bash entry point:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${MODULE_ROOT}/../.." && pwd)"
source "${REPO_ROOT}/shared/install_common.sh"
PYTHON_BIN="$(find_python)"
exec "${PYTHON_BIN}" "${SCRIPT_DIR}/gh_issue_workflow.py" "$@"
```

- [ ] **Step 4: Run installer and full module tests**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass, including idempotent install, dry-run, local-edit refusal, and non-Git refusal.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/install modules/gh-issue-workflow/tests/test_installer.py
git commit -m "Add repository workflow installer"
```

### Task 13: Add Agent-Led Initialization and Repository Profiles

**Files:**
- Create: `modules/gh-issue-workflow/skills/gh-workflow-init/SKILL.md`
- Create: `modules/gh-issue-workflow/skills/gh-workflow-init/scripts/gh_workflow_profile.py`
- Create: `modules/gh-issue-workflow/templates/project-context.md`
- Create: `modules/gh-issue-workflow/tests/test_init_profile.py`

- [ ] **Step 1: Add failing profile tests**

```python
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "gh-workflow-init" / "scripts"))
from gh_workflow_profile import ProfileError, write_profile
from test_installer import make_git_repo


def test_profile_contains_explicit_policy_and_references(tmp_path):
    repo = make_git_repo(tmp_path)
    (repo / "AGENTS.md").write_text("# Rules\nRun project tests.\n", encoding="utf-8")
    write_profile(repo, {
        "issue_types": {"parent": "Initiative", "work": "Work Item"},
        "spec_policy": {"mode": "none", "roots": []},
        "validation": {"setup": [], "commands": ["python -m pytest"]},
        "required_documents": ["AGENTS.md"],
    }, confirmed=True)
    config = json.loads((repo / ".agents/gh-issue-workflow/config.json").read_text())
    assert config["issue_types"]["work"] == "Work Item"
    context = (repo / ".agents/gh-issue-workflow/project-context.md").read_text()
    assert "[AGENTS.md](../../AGENTS.md)" in context


def test_existing_profile_requires_reviewed_change_set(tmp_path):
    repo = make_git_repo(tmp_path)
    profile = repo / ".agents/gh-issue-workflow/config.json"
    profile.parent.mkdir(parents=True)
    profile.write_text('{"version": 1, "custom": true}\n', encoding="utf-8")
    with pytest.raises(ProfileError, match="reviewed change set"):
        write_profile(repo, {"version": 1}, confirmed=True)
```

- [ ] **Step 2: Verify profile tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_init_profile.py -q`
Expected: FAIL because the profile helper is absent.

- [ ] **Step 3: Implement profile writing and init guidance**

Implement `write_profile(repo, answers, confirmed=False, reviewed_change_set=False)` so it:

- requires `confirmed=True` for every write;
- refuses an existing profile unless `reviewed_change_set=True`;
- deep-merges answers over generic defaults;
- validates `spec_policy.mode` and required document paths;
- writes `config.json` with stable sorted JSON formatting;
- writes `project-context.md` with clickable relative references and no copied rule bodies;
- never creates or edits GitHub templates unless their paths are included in the reviewed change set.

Create `templates/project-context.md`:

```markdown
# Repository Workflow Context

## Normative Documents

- [AGENTS.md](../../AGENTS.md)

## Required Validation

Use the commands recorded in `config.json`; preserve their logs as PR evidence.

## Repository Constraints

Record only constraints confirmed during init. Cite the source document for each constraint instead of duplicating its rule text.
```

Create `gh-workflow-init/SKILL.md` with the five stages from the design: read-only discovery, user confirmation, profile generation, template creation/adaptation, and final preview/local doctor. Require evidence paths for detections and explicit questions for uncertainty. On re-init, show a current-versus-proposed diff and require `reviewed_change_set=True` for existing profiles. Add `"gh-workflow-init"` to the installer's `MANAGED_SKILLS` tuple and add an installer assertion proving that it is present after update.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills/gh-workflow-init modules/gh-issue-workflow/install modules/gh-issue-workflow/templates/project-context.md modules/gh-issue-workflow/tests/test_init_profile.py
git commit -m "Add repository workflow initialization"
```

### Task 14: Add Read-Only Doctor Checks

**Files:**
- Create: `modules/gh-issue-workflow/skills/gh-workflow-init/scripts/gh_workflow_doctor.py`
- Modify: `modules/gh-issue-workflow/install/gh_issue_workflow.py`
- Create: `modules/gh-issue-workflow/tests/test_doctor.py`

- [ ] **Step 1: Add failing doctor tests**

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "gh-workflow-init" / "scripts"))
from gh_workflow_doctor import run_doctor
from test_installer import make_git_repo


def test_local_doctor_reports_missing_template(tmp_path):
    repo = make_git_repo(tmp_path)
    report = run_doctor(repo, github=False, gh_runner=fake_gh)
    assert report["ok"] is False
    assert any("template" in finding for finding in report["findings"])


def test_github_doctor_uses_only_read_operations(tmp_path):
    repo = make_git_repo(tmp_path)
    calls = []
    report = run_doctor(repo, github=True, gh_runner=recording_read_only_gh(calls))
    assert calls
    for args in calls:
        assert "create" not in args and "edit" not in args and "merge" not in args
        assert "POST" not in args and "PATCH" not in args and "DELETE" not in args
```

Provide `fake_gh` and `recording_read_only_gh` in the test file. Return deterministic repo/type payloads; assert that invalid auth and missing native APIs produce findings rather than exceptions.

- [ ] **Step 2: Verify doctor tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_doctor.py -q`
Expected: FAIL because doctor is absent.

- [ ] **Step 3: Implement local and GitHub doctor**

Implement `run_doctor(repo_root, github, gh_runner) -> dict` with checks for:

- config parse/version/spec mode;
- configured Issue and PR template existence and field IDs;
- required-document existence;
- output paths contained by the repository;
- `.claude/skills` and `.codex/skills` resolving to `.agents/skills`;
- configured validation commands accepted as nonempty strings and validated with `shlex.split`, without executing them.

With `github=True`, permit only `gh auth status`, `gh repo view --json name,nameWithOwner,owner,url`, and read-only `gh api` GET requests for issue types/native capability probes. Return `{"ok": bool, "findings": list[str]}` and never print a success message when findings exist.

Add the installer `doctor --repo PATH [--github]` action, calling this function and returning exit 1 when `ok` is false. Reuse the same preflight function from sync rather than maintaining a separate rule list.

- [ ] **Step 4: Run the suite**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add modules/gh-issue-workflow/skills/gh-workflow-init modules/gh-issue-workflow/install modules/gh-issue-workflow/tests/test_doctor.py
git commit -m "Add read-only workflow doctor"
```

### Task 15: Document the Module and Prove Both Repository Profiles End to End

**Files:**
- Create: `modules/gh-issue-workflow/README.md`
- Create: `modules/gh-issue-workflow/tests/test_end_to_end.py`
- Create: `modules/gh-issue-workflow/tests/fixtures/no-spec/`
- Create: `modules/gh-issue-workflow/tests/fixtures/with-openspec/`
- Modify: `README.md`

- [ ] **Step 1: Add the failing two-profile acceptance test**

```python
import subprocess
import sys
from pathlib import Path


def test_no_spec_repository_lifecycle(no_spec_repo):
    result = run_fixture_flow(no_spec_repo)
    assert result.returncode == 0, result.stderr
    assert result.profile["spec_policy"]["mode"] == "none"
    assert not (result.repo / "out").exists() or result.dry_run_files_unchanged
    assert result.queue_rows == ["#2"]
    assert result.pr_body.startswith("Resolves #2\n")


def test_openspec_repository_lifecycle(with_openspec_repo):
    result = run_fixture_flow(with_openspec_repo)
    assert result.returncode == 0, result.stderr
    assert result.profile["spec_policy"]["mode"] == "openspec"
    assert "openspec validate --all --strict --no-interactive" in result.validated_commands
    assert result.queue_rows == ["#2"]
```

Implement `run_fixture_flow` to execute install, confirmed init, local doctor, plan validation, dry-run rendering, approval, mock sync, queue readiness, and PR rendering against each temporary fixture. Copy fixture repositories to temporary directories; never mutate the checked-in fixtures or use real `gh`. Each fixture contains a `fixture_driver.py` that performs those commands with its fake `gh` and writes a JSON result to `repo.parent / "acceptance-result.json"`. Use this exact result adapter:

```python
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FlowResult:
    returncode: int
    stderr: str
    repo: Path
    profile: dict
    dry_run_files_unchanged: bool
    queue_rows: list[str]
    pr_body: str
    validated_commands: list[str]


def run_fixture_flow(repo: Path) -> FlowResult:
    completed = subprocess.run(
        [sys.executable, str(repo / "fixture_driver.py")],
        cwd=repo, text=True, capture_output=True, check=False,
    )
    result_path = repo.parent / "acceptance-result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    profile_path = repo / ".agents" / "gh-issue-workflow" / "config.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    return FlowResult(
        returncode=completed.returncode,
        stderr=completed.stderr,
        repo=repo,
        profile=profile,
        dry_run_files_unchanged=bool(payload.get("dry_run_files_unchanged", False)),
        queue_rows=list(payload.get("queue_rows", [])),
        pr_body=str(payload.get("pr_body", "")),
        validated_commands=list(payload.get("validated_commands", [])),
    )
```

- [ ] **Step 2: Verify acceptance tests fail**

Run: `python -m pytest modules/gh-issue-workflow/tests/test_end_to_end.py -q`
Expected: FAIL because fixture profiles and end-to-end wiring are absent.

- [ ] **Step 3: Add fixtures and documentation**

Create two minimal fixture repositories:

- `no-spec`: custom types `Initiative`/`Work Item`, `spec_policy: none`, `docs/design.md`, custom PR close keyword `Resolves`, and no `spec_impact` in its bundle.
- `with-openspec`: `Feature`/`Task`, `spec_policy: openspec`, `openspec/specs/cli/spec.md`, and an approved bundle referencing that spec.

Document the exact commands in `modules/gh-issue-workflow/README.md`:

```bash
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh install --repo /path/to/repo
# Invoke the gh-workflow-init skill in /path/to/repo and confirm the proposed profile.
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh doctor --repo /path/to/repo
bash modules/gh-issue-workflow/install/install_gh_issue_workflow.sh update --repo /path/to/repo
python -m pytest modules/gh-issue-workflow/tests -q
```

Document config precedence, all three spec policies, approval metadata, dry-run guarantees, link requirements, merge opt-in, update ownership rules, and live-GitHub test exclusion. Add one row for `modules/gh-issue-workflow` to the root README module table.

- [ ] **Step 4: Run complete verification**

Run: `python -m pytest modules/gh-issue-workflow/tests -q`
Expected: all tests pass, including both profile lifecycles.

Run: `python -m unittest discover -s tests -v`
Expected: the existing `dev-tools` suite passes with no regressions.

Run: `git diff --check`
Expected: no whitespace errors.

Run: `git status --short`
Expected: only Task 15 files are modified or untracked; no files under `D:\Playground\sw` were changed.

- [ ] **Step 5: Commit**

```bash
git add README.md modules/gh-issue-workflow
git commit -m "Document and verify reusable Issue workflows"
```

---

## Final Verification Checklist

- [ ] `python -m pytest modules/gh-issue-workflow/tests -q` passes.
- [ ] `python -m unittest discover -s tests -v` passes.
- [ ] `git diff --check` passes.
- [ ] `git -C D:/Playground/sw status --short` shows no migration edits.
- [ ] No generated code references `D:\Playground\sw`, `pku-lemonade/sw`, Zhen, fixed model IDs, or `uv run --extra dev`.
- [ ] Dry-run tests prove no remote mutation and no persistent local state writes.
- [ ] Both no-spec and OpenSpec fixture profiles complete install/init/doctor/plan/dry-run/mock-sync/queue/PR flows.
- [ ] No real issue, PR, merge, push, or live integration test was performed.
