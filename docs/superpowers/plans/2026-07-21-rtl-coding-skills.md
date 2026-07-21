# Reusable RTL Coding Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish a dual-native Claude Code/Codex plugin containing reusable `rtl-coding` and `rtl-verification` skills plus a pinned Linux x86_64 Verilator 5.050 fallback runtime, then register its remotely reachable commit as a `dev-tools` submodule.

**Architecture:** Develop the module in its own isolated Git worktree, keeping the two skills sequentially evaluation-driven and sharing only root-level references and tooling. Package one skill tree behind native Claude and Codex manifests/marketplaces, resolve project/system/bundled Verilator deterministically, and keep module push, root gitlink creation, and root push as separate authorization gates.

**Tech Stack:** Markdown Agent Skills, Claude Code/Codex plugin JSON, Bash, Python 3 standard library, Docker BuildKit/OCI, Verilator 5.050, Git submodules

---

## Fixed Paths and Branches

- `DEV_ROOT=/root/dev-tools`
- `MODULE_MAIN=/root/dev-tools/modules/rtl-coding-skills`
- `MODULE_WT=/root/.config/superpowers/worktrees/rtl-coding-skills/reusable-rtl-skills`
- `MODULE_BRANCH=feat/reusable-rtl-skills`
- `ROOT_WT=/root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills`
- `ROOT_BRANCH=feat/add-rtl-coding-skills`
- Design spec: `/root/dev-tools/docs/superpowers/specs/2026-07-20-rtl-coding-skills-design.md`

Do not stage or reset `/root/dev-tools/modules/eda-server`; its checked-out commit is user-owned state that differs from the root repository pin.

## Final File Map

### Module repository

- `.claude-plugin/marketplace.json`: Claude remote marketplace.
- `.claude-plugin/plugin.json`: Claude plugin manifest, version `0.1.0`.
- `.agents/plugins/marketplace.json`: Codex remote marketplace.
- `.codex-plugin/plugin.json`: Codex plugin manifest and interface metadata.
- `skills/rtl-coding/SKILL.md`: RTL authoring/review/lint workflow.
- `skills/rtl-coding/agents/openai.yaml`: Codex UI metadata for `rtl-coding`.
- `skills/rtl-verification/SKILL.md`: Verilator testbench/simulation workflow.
- `skills/rtl-verification/agents/openai.yaml`: Codex UI metadata for `rtl-verification`.
- `references/rtl-style.md`: project-overridable fallback RTL conventions.
- `references/verilator-runtime.md`: shared runtime selection and diagnostics.
- `scripts/run-verilator`: installed runtime selector and argument pass-through.
- `scripts/provision-verilator-builder`: networked, locked builder provisioning.
- `scripts/build-verilator-runtime`: offline source verification, compilation, and bundle generation.
- `tools/verilator/build/Dockerfile`: pinned Ubuntu 20.04 builder.
- `tools/verilator/build/source-lock.json`: upstream source and reproducibility lock.
- `tools/verilator/build/builder-lock.json`: normalized OCI builder lock.
- `tools/verilator/linux-x86_64/manifest.json`: bundled-file provenance and hashes.
- `tools/verilator/linux-x86_64/bin/` and `share/verilator/`: bundled runtime.
- `third_party/verilator/`: upstream licenses and notice.
- `tests/fixtures/`: isolated RTL and testbench evaluation inputs.
- `tests/evals/`: baseline/with-skill prompts, rubrics, and concise result records.
- `tests/test_metadata.py`: manifests, version sync, forbidden paths, provenance.
- `tests/test_run_verilator.sh`: wrapper selection and quoting tests.
- `tests/test_builder_scripts.sh`: builder/source lock and CLI tests.
- `tests/test_runtime.sh`: real bundled lint/build/run/ABI tests.
- `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`: distribution documentation and licensing.

### Root repository

- `.gitmodules`: `modules/rtl-coding-skills` SSH submodule registration.
- `modules/rtl-coding-skills`: gitlink to a commit already reachable from module `origin/main`.
- `docs/submodules.md`: module maintenance note only.

## Required Skills During Execution

- **REQUIRED:** Use `superpowers:using-git-worktrees` before module edits.
- **REQUIRED:** Use `superpowers:writing-skills` and its RED/GREEN/REFACTOR workflow for each skill separately.
- **REQUIRED:** Use `skill-creator` to initialize and validate each skill.
- **REQUIRED:** Use `plugin-creator` to scaffold/validate the Codex manifest shape.
- **REQUIRED:** Use `superpowers:test-driven-development` for Bash/Python behavior.
- **REQUIRED:** Use `superpowers:verification-before-completion` before commits, pushes, and completion claims.

---

### Task 1: Bootstrap the Module and Isolated Worktree

**Files:**
- Inspect: `/root/dev-tools/.gitmodules`
- Inspect: `/root/dev-tools/modules/rtl-coding-skills/.git`
- Create: `/root/.config/superpowers/worktrees/rtl-coding-skills/reusable-rtl-skills`

- [ ] **Step 1: Re-read the design and record protected state**

Run:

```bash
sed -n '1,460p' /root/dev-tools/docs/superpowers/specs/2026-07-20-rtl-coding-skills-design.md
git -C /root/dev-tools status --short --branch
git -C /root/dev-tools diff --submodule=log -- modules/eda-server
git -C /root/dev-tools/modules/rtl-coding-skills status --short --branch
git -C /root/dev-tools/modules/rtl-coding-skills remote -v
```

Expected: root reports only the user-updated `modules/eda-server` plus the unregistered module directory; module has no commits, no files outside `.git`, and the stated SSH origin. If the module status, filesystem contents, or origin differ from that baseline, stop immediately and report the unexpected user-owned state; do not fetch, checkout, clean, delete, or create a worktree until the user resolves it.

- [ ] **Step 2: Attach the existing directory to remote `main`**

Run:

```bash
git -C /root/dev-tools/modules/rtl-coding-skills fetch origin main
git -C /root/dev-tools/modules/rtl-coding-skills checkout -B main --track origin/main
```

Expected: local `main` points to remote initial commit `935425c`; the existing README is present and no local content was overwritten.

- [ ] **Step 3: Create the isolated module worktree**

Run:

```bash
mkdir -p /root/.config/superpowers/worktrees/rtl-coding-skills
git -C /root/dev-tools/modules/rtl-coding-skills worktree add /root/.config/superpowers/worktrees/rtl-coding-skills/reusable-rtl-skills -b feat/reusable-rtl-skills main
git -C /root/.config/superpowers/worktrees/rtl-coding-skills/reusable-rtl-skills status --short --branch
```

Expected: clean `feat/reusable-rtl-skills` worktree.

- [ ] **Step 4: Check implementation prerequisites without installing them**

Run:

```bash
python3 --version
bash --version
shellcheck --version
docker version
docker buildx version
```

Expected current baseline: Python and Bash exist; `shellcheck` and Docker/Buildx are missing. Record this. Do not install system packages without a separate explicit user authorization. Tasks 2–6 and the RED/implementation portion of Task 7 can proceed without those tools, but Task 7 cannot complete without `shellcheck`, and Task 8 cannot proceed without Docker BuildKit/Buildx or complete without `shellcheck`.

---

### Task 2: Establish `rtl-coding` RED Evaluations

**Files:**
- Create: `tests/fixtures/rtl-coding-existing-style/reference_counter.sv`
- Create: `tests/fixtures/rtl-coding-existing-style/request.md`
- Create: `tests/fixtures/rtl-coding-fallback/request.md`
- Create: `tests/fixtures/rtl-coding-review/broken_fsm.sv`
- Create: `tests/evals/rtl-coding/prompts.md`
- Create: `tests/evals/rtl-coding/rubric.md`
- Create: `tests/evals/rtl-coding/baseline.md`

- [ ] **Step 1: Create three evaluation fixtures before writing the skill**

Use `apply_patch`. The existing-style fixture must establish conventions that conflict with the fallback (`clk`, `reset_n`, unsuffixed ports, `u_` instances). The fallback fixture contains only a behavioral request for a registered ready/valid skid buffer. The review fixture contains at least: incomplete combinational assignment, blocking assignment in sequential logic, ambiguous width truncation, and no illegal-state recovery.

- [ ] **Step 2: Write prompts and an objective rubric**

`prompts.md` must contain these fresh-agent tasks:

1. Extend the existing-style fixture without reformatting unrelated code.
2. Implement the no-convention skid buffer and explain chosen conventions.
3. Review `broken_fsm.sv`, ranking functional hazards before style.

`rubric.md` must score project-style discovery, safe fallback use, synthesizability, width/reset/FSM findings, and absence of predecessor-specific path assumptions.

- [ ] **Step 3: Run RED with fresh subagents and no RTL skill**

Dispatch one fresh, context-free subagent per prompt. Explicitly forbid loading the existing global `rtl-systemverilog-style` and `verilator-testbench-flow` skills. Give each agent only its copied fixture under a unique `/tmp/rtl-coding-red-*` path and the user-like task. Capture raw response/diff evidence.

Expected: at least one rubric criterion fails. If all pass, add a harder realistic variation and rerun; do not write `rtl-coding` until a real gap is observed.

- [ ] **Step 4: Record concise baseline evidence**

Write `baseline.md` with prompt, observed choice/diff, failed rubric items, and exact rationalization or omission. Do not include the intended skill answer.

- [ ] **Step 5: Commit RED artifacts**

```bash
git add tests/fixtures tests/evals/rtl-coding
git commit -m "test: add rtl-coding baseline evaluations"
```

---

### Task 3: Implement and Verify `rtl-coding`

**Files:**
- Create: `skills/rtl-coding/SKILL.md`
- Create: `skills/rtl-coding/agents/openai.yaml`
- Create: `references/rtl-style.md`
- Create: `tests/evals/rtl-coding/with-skill.md`

- [ ] **Step 1: Initialize the skill using the canonical generator**

Run from the module worktree:

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/init_skill.py rtl-coding --path skills --interface 'display_name=RTL Coding' --interface 'short_description=Write and review portable Verilog and SystemVerilog RTL' --interface 'default_prompt=Use $rtl-coding to implement or review this RTL while respecting the project conventions.'
```

Expected: generated `SKILL.md` and `agents/openai.yaml`, with no extra resource directories.

- [ ] **Step 2: Write the minimal skill that addresses RED failures**

Use `apply_patch`. Frontmatter must contain only:

```yaml
---
name: rtl-coding
description: Use when writing, modifying, refactoring, explaining, reviewing, or linting synthesizable Verilog or SystemVerilog RTL, including reset, width, latch, FSM, interface, and pipeline behavior.
---
```

The body must require project discovery first, project conventions over fallback, functional hazards before style, and conditional loading of `../../references/rtl-style.md`. For lint, it must use an existing project lint entry point when present; only when none exists may it load `../../references/verilator-runtime.md` and call `scripts/run-verilator`. It must direct simulation/testbench work to `rtl-verification` without duplicating that workflow.

- [ ] **Step 3: Move the complete fallback conventions into one reference**

Write `references/rtl-style.md` from the predecessor skill, preserving `logic`, `clk_i`/`rst_ni`, `_i`/`_o`, `_d`/`_q`, packed-array preference, `always_ff`/`always_comb` assignment rules, defaults, enum FSMs, named ports, `i_` instances, width safety, module-scope temporaries, pipeline sections, templates, and the review checklist. Remove `therm_top.sv` and repository-specific language.

- [ ] **Step 4: Validate syntax and metadata**

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/rtl-coding
rg -n 'hardware_design|therm_top\.sv|/home/' skills/rtl-coding references/rtl-style.md
```

Expected: validator succeeds; `rg` exits 1 with no matches.

- [ ] **Step 5: Run GREEN and REFACTOR evaluations**

Repeat Task 2 prompts with fresh subagents, now instructing each to use `$rtl-coding` at the module worktree skill path. Record results in `with-skill.md`. If a rubric item still fails, update only the instruction that addresses the observed gap and rerun all three cases.

Expected: all `rtl-coding` rubric items pass without forcing fallback style onto the existing-style fixture.

- [ ] **Step 6: Commit the verified first skill before starting the next**

```bash
git add skills/rtl-coding references/rtl-style.md tests/evals/rtl-coding/with-skill.md
git commit -m "feat: add reusable rtl-coding skill"
```

---

### Task 4: Establish `rtl-verification` RED Evaluations

**Files:**
- Create: `tests/fixtures/rtl-verification-existing-layout/design/pipe.sv`
- Create: `tests/fixtures/rtl-verification-existing-layout/verify/verilator/Makefile`
- Create: `tests/fixtures/rtl-verification-existing-layout/request.md`
- Create: `tests/fixtures/rtl-verification-new-project/rtl/counter.sv`
- Create: `tests/fixtures/rtl-verification-new-project/request.md`
- Create: `tests/fixtures/rtl-verification-review/weak_tb.sv`
- Create: `tests/evals/rtl-verification/prompts.md`
- Create: `tests/evals/rtl-verification/rubric.md`
- Create: `tests/evals/rtl-verification/baseline.md`

- [ ] **Step 1: Create evaluation fixtures**

The existing-layout fixture deliberately uses `design/` and `verify/verilator/`, a working custom Make target, and a filelist outside any `hardware_design` tree. The new project has `rtl/` only. `weak_tb.sv` omits post-edge delay, reset recovery, consecutive requests, and self-checking failure status.

- [ ] **Step 2: Define prompts and rubric**

Prompts cover preserving the custom flow, adding a fresh self-checking counter testbench, and reviewing the weak pipeline testbench. The rubric scores layout preservation, lint/build/run ordering, exact latency, throughput, reset recovery, golden-model choice, and concise failures.

- [ ] **Step 3: Run fresh RED agents without either RTL skill**

Use unique `/tmp/rtl-verification-red-*` copies and prohibit the existing global RTL skills. Capture at least one genuine failure before writing `rtl-verification`.

- [ ] **Step 4: Record and commit RED evidence**

```bash
git add tests/fixtures tests/evals/rtl-verification
git commit -m "test: add rtl-verification baseline evaluations"
```

---

### Task 5: Implement and Verify `rtl-verification`

**Files:**
- Create: `skills/rtl-verification/SKILL.md`
- Create: `skills/rtl-verification/agents/openai.yaml`
- Create: `tests/evals/rtl-verification/with-skill.md`
- Create: `tests/evals/end-to-end.md`

- [ ] **Step 1: Initialize the second skill only after Task 3 is verified**

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/init_skill.py rtl-verification --path skills --interface 'display_name=RTL Verification' --interface 'short_description=Build self-checking SystemVerilog tests with Verilator' --interface 'default_prompt=Use $rtl-verification to create and run a self-checking Verilator testbench for this RTL.'
```

- [ ] **Step 2: Write the skill from observed RED gaps**

Frontmatter:

```yaml
---
name: rtl-verification
description: Use when creating, updating, reviewing, or running SystemVerilog testbenches with Verilator, including lint, simulation, latency, throughput, handshake, reset, randomized stimulus, DPI-C, and golden-model checks.
---
```

The body must require layout/toolchain discovery, preserve project flows, use `tb/` and `sim/` only for a new project, apply the full staged verification guidance from the spec, load `../../references/verilator-runtime.md` only when invoking Verilator, and require `rtl-coding` if DUT RTL changes.

- [ ] **Step 3: Validate and run GREEN/REFACTOR**

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/rtl-verification
rg -n 'hardware_design|common\.svh|/home/' skills/rtl-verification
```

Repeat Task 4 with fresh agents using the new skill; write `with-skill.md` and iterate until the rubric passes.

- [ ] **Step 4: Run a coordinated end-to-end evaluation**

Give a fresh subagent a small pipelined ready/valid DUT request and both skill paths. Require DUT implementation, testbench, exact latency, consecutive traffic, backpressure, reset recovery, and a concrete verification command. Record results in `tests/evals/end-to-end.md`.

- [ ] **Step 5: Commit the verified second skill**

```bash
git add skills/rtl-verification tests/evals/rtl-verification/with-skill.md tests/evals/end-to-end.md
git commit -m "feat: add reusable rtl-verification skill"
```

---

### Task 6: Build Dual-Native Plugin Packaging with Metadata TDD

**Files:**
- Create: `tests/test_metadata.py`
- Create: `.claude-plugin/marketplace.json`
- Create: `.claude-plugin/plugin.json`
- Create: `.agents/plugins/marketplace.json`
- Create: `.codex-plugin/plugin.json`
- Modify: `README.md`
- Create: `LICENSE`

- [ ] **Step 1: Write a failing metadata test**

Use Python standard library. Assert both marketplaces/manifests exist, plugin names are `rtl-coding-skills`, Claude and Codex skill paths are `./skills/`, the three version fields equal `0.1.0`, Codex policy is `AVAILABLE`/`ON_INSTALL`, both skill directories exist, and runtime inputs contain no TODO placeholders or forbidden project/developer paths.

- [ ] **Step 2: Run RED**

```bash
python3 tests/test_metadata.py -v
```

Expected: FAIL because manifests are absent.

- [ ] **Step 3: Run the canonical Codex plugin scaffold in temporary space**

```bash
scaffold_parent=$(mktemp -d /tmp/rtl-coding-plugin-scaffold.XXXXXX)
python3 /root/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py rtl-coding-skills --path "$scaffold_parent" --with-skills
python3 /root/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py "$scaffold_parent/rtl-coding-skills"
```

Expected: scaffold validates. Use its manifest shape as the starting schema; do not copy its empty skills directory.

- [ ] **Step 4: Create all four native metadata files**

Use `apply_patch` and current `modules/eda-server` as the layout reference. Include PKU Pacific Lab author/team URLs, Apache-2.0, repository/homepage URLs, RTL/Verilog/SystemVerilog/Verilator keywords, and Codex interface metadata. Do not add hooks, MCP, apps, icons, or unsupported fields.

- [ ] **Step 5: Write distribution documentation and repository license**

Replace the two-line README with skill descriptions, Linux x86_64 runtime boundary, project-toolchain precedence, Claude/Codex install and update commands, minimum Codex 0.142.0, maintainer version-sync rules, and no-local-marketplace guidance. Copy the canonical Apache-2.0 text into `LICENSE`.

- [ ] **Step 6: Run GREEN validators**

```bash
python3 tests/test_metadata.py -v
python3 /root/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
claude plugin validate --strict .
```

Expected: all succeed.

- [ ] **Step 7: Commit packaging**

```bash
git add .claude-plugin .agents .codex-plugin README.md LICENSE tests/test_metadata.py
git commit -m "feat: package RTL skills for Claude Code and Codex"
```

---

### Task 7: Implement Verilator Selection Wrapper with TDD

**Files:**
- Create: `tests/test_run_verilator.sh`
- Create: `scripts/run-verilator`
- Create: `references/verilator-runtime.md`

- [ ] **Step 1: Write failing shell tests**

The test creates fake explicit, PATH, and bundled executables in temporary directories and stubs platform/dependency discovery through a temporary `PATH`. Cover: `VERILATOR` precedence; executable paths containing spaces; no `eval`; `auto` PATH selection; `auto` bundled fallback; `path` no-fallback failure; `bundled` PATH bypass; explicitly empty and unknown modes; non-executable explicit path; unsupported OS and unsupported architecture when the bundle is selected; missing host Perl for the bundled front end; independently missing `make` and C++ compiler for build/run arguments; `--print-selection`; `--self-check`; argument and exit-code pass-through. Assert actionable diagnostics and nonzero status for every rejected platform/dependency case.

- [ ] **Step 2: Verify RED**

```bash
bash tests/test_run_verilator.sh
```

Expected: FAIL because `scripts/run-verilator` is absent.

- [ ] **Step 3: Implement the minimal wrapper**

Use Bash arrays and quoted variables only. `VERILATOR` is a path with no embedded flags. `RTL_VERILATOR_SOURCE` defaults to `auto` and accepts only `auto`, `path`, `bundled`. Resolve the plugin root from `BASH_SOURCE[0]`. Before choosing the bundle, require `uname -s` = `Linux` and `uname -m` = `x86_64`, then require host `perl`; emit actionable errors naming the supported platform or missing dependency. Set `VERILATOR_ROOT` only for bundled selection, inspect build-related Verilator arguments before additionally requiring `make`/C++, and `exec` the chosen tool. Set the tracked executable bit with `chmod +x scripts/run-verilator`.

- [ ] **Step 4: Document conditional use**

`references/verilator-runtime.md` must tell skills to run project entry points directly, explain the exact environment contract, forbid fallback after a selected project command fails, document dependencies/platform, and provide diagnostics without duplicating wrapper internals.

- [ ] **Step 5: Run GREEN and static checks**

```bash
bash -n scripts/run-verilator tests/test_run_verilator.sh
bash tests/test_run_verilator.sh
shellcheck scripts/run-verilator tests/test_run_verilator.sh
test -x scripts/run-verilator
```

If `shellcheck` is still unavailable, stop at this step and request explicit user authorization to install it or have it provided. Do not defer the request to Task 8, skip the static check, mark Task 7 complete, or create the Task 7 commit until the check passes.

- [ ] **Step 6: Commit wrapper**

```bash
git add scripts/run-verilator references/verilator-runtime.md tests/test_run_verilator.sh
git commit -m "feat: add deterministic Verilator selector"
```

---

### Task 8: Provision the Reproducible Builder and Build Scripts

**Files:**
- Create: `tests/test_builder_scripts.sh`
- Create: `scripts/provision-verilator-builder`
- Create: `scripts/build-verilator-runtime`
- Create: `tools/verilator/build/Dockerfile`
- Create: `tools/verilator/build/source-lock.json`
- Create after provisioning: `tools/verilator/build/builder-lock.json`

- [ ] **Step 1: Resolve the known environment gate**

If Docker BuildKit/Buildx and shellcheck remain unavailable, stop and request explicit authorization to install/provide them. Do not replace the pinned OCI design with a native host build. After resolution, record exact Docker and BuildKit versions for builder diagnostics.

- [ ] **Step 2: Write RED tests for locks and CLI behavior**

Test required arguments, source SHA rejection, unknown lock fields, Dockerfile/base/snapshot pins, default refusal to rewrite `builder-lock.json`, explicit `--update-lock`, local builder digest verification, compile-time `--network=none`, and executable modes for both builder scripts.

- [ ] **Step 3: Run RED**

```bash
bash tests/test_builder_scripts.sh
```

Expected: FAIL because builder scripts and locks are absent.

- [ ] **Step 4: Implement source lock and Dockerfile**

Encode the exact tag object, peeled commit, archive URL/SHA256, epoch, Ubuntu image/index/child digests, and snapshot from the design. Dockerfile package sources must point only to the locked snapshot.

- [ ] **Step 5: Implement provisioning and offline compile scripts**

Provisioning builds/exports OCI twice with timestamp rewrite and provenance/SBOM disabled, compares config/layers, and verifies or explicitly updates `builder-lock.json`. Runtime build verifies the local OCI lock and read-only source archive, compiles with `--network=none`, `LC_ALL=C`, `TZ=UTC`, and the locked `SOURCE_DATE_EPOCH`, installs into an isolated staging prefix, removes debug/manual-only files, deterministically strips only the release binaries with the pinned builder toolchain, builds twice, and emits deterministic file metadata. Set the tracked executable bits with `chmod +x scripts/provision-verilator-builder scripts/build-verilator-runtime`.

- [ ] **Step 6: Provision and lock the builder**

Download the exact source archive separately and verify it:

```bash
curl -L --fail https://github.com/verilator/verilator/archive/848d926ebd4addacacd294dc84e35d9d4ae8078c.tar.gz -o /tmp/verilator-848d926e.tar.gz
echo '0e8e4243a98ca7d806a04b8cb19d5f0ed18a246da8f8f1725a075d5ee2e0964e  /tmp/verilator-848d926e.tar.gz' | sha256sum -c -
scripts/provision-verilator-builder --update-lock
scripts/provision-verilator-builder
```

Expected: second command verifies the committed lock without modifying it.

- [ ] **Step 7: Run GREEN/static checks and commit**

```bash
bash -n scripts/provision-verilator-builder scripts/build-verilator-runtime tests/test_builder_scripts.sh
shellcheck scripts/provision-verilator-builder scripts/build-verilator-runtime tests/test_builder_scripts.sh
bash tests/test_builder_scripts.sh
test -x scripts/provision-verilator-builder
test -x scripts/build-verilator-runtime
git add scripts/provision-verilator-builder scripts/build-verilator-runtime tools/verilator/build tests/test_builder_scripts.sh
git commit -m "build: add reproducible Verilator builder"
```

---

### Task 9: Build, License, and Test the Bundled Runtime

**Files:**
- Create: `tools/verilator/linux-x86_64/manifest.json`
- Create: `tools/verilator/linux-x86_64/bin/`
- Create: `tools/verilator/linux-x86_64/share/verilator/`
- Create: `third_party/verilator/LICENSE.LGPL-3.0`
- Create: `third_party/verilator/LICENSE.Artistic-2.0`
- Create: `third_party/verilator/NOTICE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `tests/test_runtime.sh`

- [ ] **Step 1: Write RED runtime tests before generating the bundle**

Test exact `5.050` version, valid lint success, invalid lint failure, minimal self-checking build/run, executable modes, no build-machine paths, no debug binaries, and Ubuntu 20.04 baseline smoke. Parse `manifest.json` and assert complete bytewise-sorted file/symlink coverage plus exact provenance: source tag and tag object, peeled commit, archive URL/SHA256, and `SOURCE_DATE_EPOCH`; builder Dockerfile SHA256, base image index/amd64-child digests, snapshot URL, OCI config digest, and ordered layer digests; Linux/x86_64 and glibc 2.31 ABI baseline; and the maximum required GLIBC and GLIBCXX symbol versions measured from the shipped executables. Assert those values agree with `source-lock.json`, `builder-lock.json`, and fresh `readelf --version-info` output, with no required GLIBC symbol newer than 2.31.

- [ ] **Step 2: Verify RED**

```bash
bash tests/test_runtime.sh
```

Expected: FAIL because bundle files are absent.

- [ ] **Step 3: Generate the bundle twice and compare**

```bash
scripts/build-verilator-runtime --source-archive /tmp/verilator-848d926e.tar.gz --output /tmp/verilator-runtime-a
scripts/build-verilator-runtime --source-archive /tmp/verilator-848d926e.tar.gz --output /tmp/verilator-runtime-b
diff -qr /tmp/verilator-runtime-a /tmp/verilator-runtime-b
```

Expected: no differences.

- [ ] **Step 4: Install generated output and upstream licensing**

Use `apply_patch` for text metadata/license files and a mechanical copy only for generated binary/runtime output. Populate `THIRD_PARTY_NOTICES.md` from the locked source. Do not include debug binaries, source build trees, caches, or developer paths.

- [ ] **Step 5: Run GREEN runtime tests**

```bash
bash tests/test_runtime.sh
RTL_VERILATOR_SOURCE=bundled scripts/run-verilator --version
```

Expected: all tests pass and version output contains `Verilator 5.050`.

- [ ] **Step 6: Commit runtime as its own reviewable change**

```bash
git add tools/verilator/linux-x86_64 third_party/verilator THIRD_PARTY_NOTICES.md tests/test_runtime.sh
git commit -m "feat: bundle Verilator 5.050 for Linux x86_64"
```

---

### Task 10: Run Full Module Verification and Reach the Module Push Gate

**Files:**
- Verify all module files

- [ ] **Step 1: Run the complete local verification suite fresh**

```bash
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/rtl-coding
python3 /root/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/rtl-verification
python3 /root/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
claude plugin validate --strict .
python3 tests/test_metadata.py -v
bash tests/test_run_verilator.sh
bash tests/test_builder_scripts.sh
bash tests/test_runtime.sh
shellcheck scripts/run-verilator scripts/provision-verilator-builder scripts/build-verilator-runtime tests/*.sh
test -x scripts/run-verilator
test -x scripts/provision-verilator-builder
test -x scripts/build-verilator-runtime
git diff --check
git status --short --branch
```

Expected: all validators/tests pass; worktree is clean after any final test-result commit.

- [ ] **Step 2: Verify version and release metadata**

```bash
claude plugin tag --dry-run .
git log --oneline --decorate -12
```

Expected: dry run accepts `rtl-coding-skills` version `0.1.0`; skill commits are sequential and separately tested.

- [ ] **Step 3: Merge the feature branch into module `main` locally**

From `MODULE_MAIN`, fast-forward `main` to `feat/reusable-rtl-skills` after verification. Re-run metadata and runtime smoke from `MODULE_MAIN`.

- [ ] **Step 4: Stop for explicit module push authorization**

Report the exact module commit and planned command:

```bash
git -C /root/dev-tools/modules/rtl-coding-skills push origin main
```

Do not run it without explicit user confirmation. If declined, stop with the module committed locally and do not register the root submodule.

- [ ] **Step 5: If authorized, push and prove remote reachability**

```bash
git -C /root/dev-tools/modules/rtl-coding-skills push origin main
module_commit=$(git -C /root/dev-tools/modules/rtl-coding-skills rev-parse HEAD)
git -C /root/dev-tools/modules/rtl-coding-skills ls-remote origin refs/heads/main | rg "^${module_commit}[[:space:]]"
```

Expected: exact commit is the remote `main` tip.

- [ ] **Step 6: Validate both remote plugin entry points and fresh sessions**

Ensure the isolated homes can use an existing supported CLI authentication mechanism without printing credentials; for Codex, link the current `auth.json` into the temporary home if environment/provider authentication is unavailable. Stop and report the authentication gate rather than falling back to a local plugin path. Run the remote clone, isolated installs, and new non-resumed read-only sessions in one shell so the cleanup trap covers every temporary path and authentication link:

```bash
set -euo pipefail
module_commit=$(git -C /root/dev-tools/modules/rtl-coding-skills rev-parse HEAD)
validation_root=$(mktemp -d /tmp/rtl-coding-skills-remote-validation.XXXXXX)
claude_home=$(mktemp -d /tmp/rtl-claude-home.XXXXXX)
codex_home=$(mktemp -d /tmp/rtl-codex-home.XXXXXX)
published_fixture=
cleanup_remote_validation() {
  for temporary_path in "${published_fixture:-}" "$codex_home" "$claude_home" "$validation_root"; do
    if [[ -n "$temporary_path" ]]; then
      rm -rf -- "$temporary_path"
    fi
  done
}
trap cleanup_remote_validation EXIT

git clone --depth=1 git@github.com:pku-pacific-lab-team/rtl-coding-skills.git "$validation_root/repo"
test "$(git -C "$validation_root/repo" rev-parse HEAD)" = "$module_commit"
python3 /root/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py "$validation_root/repo"
claude plugin validate --strict "$validation_root/repo"

CLAUDE_CONFIG_DIR="$claude_home" claude plugin marketplace add pku-pacific-lab-team/rtl-coding-skills
CLAUDE_CONFIG_DIR="$claude_home" claude plugin install rtl-coding-skills@rtl-coding-skills
CLAUDE_CONFIG_DIR="$claude_home" claude plugin list | rg 'rtl-coding-skills'

CODEX_HOME="$codex_home" codex plugin marketplace add pku-pacific-lab-team/rtl-coding-skills
CODEX_HOME="$codex_home" codex plugin add rtl-coding-skills@rtl-coding-skills
CODEX_HOME="$codex_home" codex plugin list | rg 'rtl-coding-skills'

current_codex_home=${CODEX_HOME:-$HOME/.codex}
if [[ -z "${OPENAI_API_KEY:-}" && -f "$current_codex_home/auth.json" ]]; then
  ln -s "$current_codex_home/auth.json" "$codex_home/auth.json"
fi
published_fixture=$(mktemp -d /tmp/rtl-published-eval.XXXXXX)
cp -a "$validation_root/repo/tests/fixtures/rtl-coding-fallback/." "$published_fixture/"

(
  cd "$published_fixture"
  CLAUDE_CONFIG_DIR="$claude_home" claude -p --no-session-persistence --permission-mode dontAsk --allowed-tools "Read,Glob,Grep" \
    "Use the installed rtl-coding skill to explain how you would handle request.md. Do not edit files. Identify the project-discovery decision before any fallback convention."
) | tee "$validation_root/claude-published-eval.txt"

CODEX_HOME="$codex_home" codex exec --ephemeral --skip-git-repo-check -s read-only -C "$published_fixture" \
  -o "$validation_root/codex-published-eval.txt" \
  "Use \$rtl-coding to explain how you would handle request.md. Do not edit files. Identify the project-discovery decision before any fallback convention."

rg -i 'project|convention|fallback' "$validation_root/claude-published-eval.txt"
rg -i 'project|convention|fallback' "$validation_root/codex-published-eval.txt"
```

Expected: clone tip equals the pushed module commit, both strict manifest validators pass, and each isolated client reports the plugin without changing normal user configuration. Both fresh-session responses show that the remotely installed `rtl-coding` skill was available, inspect project conventions before choosing the fallback, and contain no predecessor-specific path assumptions. Report concise rubric evidence alongside the earlier Task 3 results without editing the already-pushed module. The `EXIT` trap removes temporary homes, fixtures, outputs, and authentication links even on failure. Start no persistent background process.

- [ ] **Step 7: Clean the merged module feature worktree**

After remote validation succeeds:

```bash
git -C /root/dev-tools/modules/rtl-coding-skills worktree remove /root/.config/superpowers/worktrees/rtl-coding-skills/reusable-rtl-skills
git -C /root/dev-tools/modules/rtl-coding-skills branch -d feat/reusable-rtl-skills
```

Expected: module `main` remains at the verified remote commit and the temporary feature worktree/branch are gone.

---

### Task 11: Register and Verify the `dev-tools` Submodule

**Files:**
- Modify: `/root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills/.gitmodules`
- Create gitlink: `/root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills/modules/rtl-coding-skills`
- Modify: `/root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills/docs/submodules.md`

- [ ] **Step 1: Create a clean root worktree only after Task 10 remote proof**

```bash
mkdir -p /root/.config/superpowers/worktrees/dev-tools
git -C /root/dev-tools worktree add /root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills -b feat/add-rtl-coding-skills main
```

Expected: clean worktree that still pins the repository's original EDA Server commit, independent of the user's updated checkout.

- [ ] **Step 2: Add the remotely reachable module commit**

```bash
git -C /root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills submodule add git@github.com:pku-pacific-lab-team/rtl-coding-skills.git modules/rtl-coding-skills
git -C /root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills/modules/rtl-coding-skills checkout "$(git -C /root/dev-tools/modules/rtl-coding-skills rev-parse HEAD)"
```

- [ ] **Step 3: Update root-only maintenance documentation**

Use `apply_patch` to add `modules/rtl-coding-skills` to examples and show its normal fetch/checkout/pull/pin workflow. Do not duplicate the module README.

- [ ] **Step 4: Commit only root integration files**

```bash
git add .gitmodules modules/rtl-coding-skills docs/submodules.md
git diff --cached --submodule=log
git commit -m "Add rtl-coding-skills submodule"
```

Expected staged diff excludes `modules/eda-server`.

- [ ] **Step 5: Validate from a clean local clone**

```bash
git clone --no-hardlinks /root/.config/superpowers/worktrees/dev-tools/add-rtl-coding-skills /tmp/dev-tools-rtl-submodule-validation
git -C /tmp/dev-tools-rtl-submodule-validation submodule update --init modules/rtl-coding-skills
git -C /tmp/dev-tools-rtl-submodule-validation submodule status modules/rtl-coding-skills
```

Expected: submodule initializes at the exact remotely reachable module commit.

- [ ] **Step 6: Re-run root and module final checks**

Run `git diff --check`, root status, module metadata validators, both skill validators, and bundled runtime version from the clean clone.

- [ ] **Step 7: Stop for root integration choice and push authorization**

Use `superpowers:finishing-a-development-branch` to offer local merge, PR/push, keep, or discard. A local merge must preserve the user's checked-out `modules/eda-server` state. Pushing `dev-tools` remains a separate explicit authorization from the module push.
