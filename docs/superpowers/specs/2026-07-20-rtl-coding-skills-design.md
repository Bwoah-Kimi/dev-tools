# Reusable RTL Coding Skills Design

## Objective

Create a reusable, cross-project RTL plugin in the existing
`pku-pacific-lab-team/rtl-coding-skills` repository and manage that repository
from `dev-tools` as `modules/rtl-coding-skills` Git submodule. The plugin must
provide first-class, native support for both Claude Code and Codex while
maintaining one copy of its skill content.

The plugin will expose two coordinated skills:

- `rtl-coding` for synthesizable Verilog/SystemVerilog authoring, refactoring,
  explanation, review, and static lint;
- `rtl-verification` for SystemVerilog testbench work and Verilator-based
  simulation.

Verilator is a shared plugin runtime, not a third user-visible skill.

## Existing State

- The remote repository is
  `git@github.com:pku-pacific-lab-team/rtl-coding-skills.git`; its `main`
  branch currently contains only a minimal README.
- `modules/rtl-coding-skills` already exists as an uncommitted nested Git
  working directory with the correct remote but an unborn local `master`
  branch. Implementation must preserve the path and connect it to remote
  `main` safely rather than overwriting unknown user content.
- The two source skills currently installed under `/root/.codex/skills` are
  `rtl-systemverilog-style` and `verilator-testbench-flow`.
- The current `modules/eda-server` working tree is at `d62837b` and demonstrates
  the required dual-native plugin layout. The root `dev-tools` repository still
  pins an older EDA Server commit, so that user-owned submodule pointer change
  must not be staged with this work.

## Non-Goals

- Do not support macOS, Windows-native, or Linux architectures other than
  x86_64 in the first bundled runtime release. WSL2 is supported as Linux.
- Do not introduce an MCP server, lifecycle hooks, background processes, or
  automatic network downloads.
- Do not force one repository layout, Makefile, filelist, simulator entry
  point, naming scheme, or formatting style onto an established project.
- Do not silently replace a project-configured Verilator after its command
  fails.
- Do not push either repository without explicit user confirmation.

## Repository Layout

The remote repository root is also the plugin root:

```text
rtl-coding-skills/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .agents/plugins/
│   └── marketplace.json
├── .codex-plugin/
│   └── plugin.json
├── skills/
│   ├── rtl-coding/
│   │   ├── SKILL.md
│   │   └── agents/openai.yaml
│   └── rtl-verification/
│       ├── SKILL.md
│       └── agents/openai.yaml
├── references/
│   ├── rtl-style.md
│   └── verilator-runtime.md
├── scripts/
│   ├── run-verilator
│   └── build-verilator-runtime
├── tools/verilator/linux-x86_64/
│   ├── manifest.json
│   ├── bin/verilator
│   └── share/verilator/
├── third_party/verilator/
│   ├── LICENSE.LGPL-3.0
│   ├── LICENSE.Artistic-2.0
│   └── NOTICE
├── tests/
├── README.md
├── LICENSE
└── THIRD_PARTY_NOTICES.md
```

The plugin and both marketplaces use the identifier `rtl-coding-skills`.
Plugin versioning starts at `0.1.0`.

## Dual-Platform Packaging

Follow the current `eda-server` pattern exactly:

| Platform | Marketplace | Plugin manifest | Skill source |
|---|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `.claude-plugin/plugin.json` | `./skills/` |
| Codex | `.agents/plugins/marketplace.json` | `.codex-plugin/plugin.json` | `./skills/` |

Both manifests point to the same `skills/` tree and describe the same plugin.
The Codex manifest additionally supplies native interface metadata. No skill
instructions are duplicated between platform-specific packages.

The README documents remote installation and update commands modeled after
`eda-server`:

```bash
claude plugin marketplace add pku-pacific-lab-team/rtl-coding-skills
claude plugin install rtl-coding-skills@rtl-coding-skills

codex plugin marketplace add pku-pacific-lab-team/rtl-coding-skills
codex plugin add rtl-coding-skills@rtl-coding-skills
```

The documented minimum Codex CLI version is 0.142.0 because the repository-root
plugin layout depends on support introduced at that version.

## `rtl-coding` Skill

### Trigger Scope

Use for writing, modifying, refactoring, explaining, or reviewing synthesizable
Verilog/SystemVerilog RTL, and for static RTL lint or diagnosis of latches,
widths, reset behavior, FSMs, and pipeline timing.

### Project Discovery and Precedence

Before applying style rules, inspect the target project for:

1. durable instructions such as `AGENTS.md` and `CLAUDE.md`;
2. established RTL source organization and representative modules;
3. lint, formatting, filelist, and build configuration;
4. existing clock, reset, port, state, instance, and array conventions.

Explicit project conventions override plugin defaults. When the project has no
clear convention, load `references/rtl-style.md` and use the preserved house
style from the predecessor skill.

### Fallback RTL Style

The fallback retains the predecessor skill's substantive rules:

- prefer `logic` for synthesizable signals;
- use `clk_i`, active-low `rst_ni`, `_i`/`_o` ports, and `_d`/`_q` state;
- prefer packed arrays when interfaces and tooling allow them;
- use `always_ff` with nonblocking assignments and `always_comb` with blocking
  assignments and complete defaults;
- keep combinational-only signals free of unnecessary `_d`/`_q` pairs;
- use `typedef enum logic` FSMs with illegal-state handling;
- use named port connections and `i_` instance prefixes;
- keep arithmetic width-safe with explicit casts where intent is ambiguous;
- declare temporary signals in the module declaration section;
- preserve local formatting and group nontrivial datapath, control, interface,
  and pipeline stages clearly.

Reviews prioritize functional hazards before style issues. Verification uses a
project lint target when one exists; otherwise it may load the shared Verilator
runtime reference and call `scripts/run-verilator`.

## `rtl-verification` Skill

### Trigger Scope

Use for creating, updating, reviewing, or running SystemVerilog testbenches
with Verilator, including directed tests, randomized coverage, handshake and
backpressure checks, exact latency checks, throughput tests, reset recovery,
DPI-C golden models, and offline expected vectors.

### Layout Discovery

Discover and preserve existing testbench directories, simulator scripts,
Makefiles, filelists, DPI sources, include paths, and output locations. Never
assume `hardware_design/tb`, `hardware_design/sim`, or any other predecessor
project path. For a project with no established structure, use `tb/` and
`sim/` relative to the detected RTL project root.

### Testbench Guidance

Retain the predecessor skill's generalizable rules:

- write self-checking testbenches rather than waveform-only smoke tests;
- use an explicit timescale, a `localparam time` clock period, and a small
  post-edge sampling delay;
- progress from directed smoke tests through edge cases, reset recovery,
  latency, throughput, and randomized coverage;
- test consecutive requests for pipelined units and backpressure for
  valid/ready interfaces;
- verify post-reset operation, not only reset values;
- allow behavioral inspection of DUT internals when it materially improves
  control-state confidence;
- use SystemVerilog, DPI-C, or offline vectors for golden behavior according to
  complexity;
- produce concise, self-checking pass/fail summaries;
- reuse project logging helpers, including ANSI formatting, without assuming a
  fixed include path.

The normal bring-up order is lint, build, minimal run, edge/reset tests,
latency/throughput tests, and broader coverage.

### Skill Coordination

- RTL authoring or lint-only work uses `rtl-coding`.
- Testbench or simulation work uses `rtl-verification`.
- End-to-end DUT implementation and verification uses both.
- If verification requires changing DUT RTL, `rtl-verification` directs the
  agent to also apply `rtl-coding`.

## Shared Verilator Runtime

### Version and Platform

Bundle Verilator 5.050, the current upstream stable tag at design time. Build
it from the official upstream source in a pinned Linux x86_64 environment.
Do not copy the developer machine's existing Verilator 5.026 installation.

The bundle contains the Perl front end, release `verilator_bin`, required
runtime/include files, and configuration data. It excludes debug binaries,
manual pages, and files not required for lint/build/run. Expected size is
approximately 16–20 MB, so regular Git storage is sufficient.

The bundle still depends on host Perl. Build and run operations also require
`make` and a C++ compiler. These dependencies are checked, not installed.

### Tool Resolution

Use this strict precedence:

1. Run a project's existing Makefile, script, or task-runner entry point
   directly when it exists.
2. When the shared wrapper is used, honor a project-explicit Verilator path or
   `VERILATOR` environment variable.
3. Use a PATH Verilator when the project permits the environment toolchain.
4. Use bundled Verilator 5.050 only when no project or system tool is selected.
5. If a project entry point was selected and fails, report that failure; do not
   silently retry with the bundled version.

### Wrapper Contract

`scripts/run-verilator`:

- passes Verilator arguments and exit status through unchanged;
- resolves its plugin root independently of installation location;
- supports `--self-check` and `--print-selection` diagnostics;
- validates Linux x86_64 before choosing the bundle;
- sets `VERILATOR_ROOT` only for the bundled runtime;
- checks Perl for front-end use and additionally checks `make` and a C++
  compiler for build/run modes;
- performs no network access, installation, background work, or mutation of
  the target project's toolchain;
- gives an actionable unsupported-platform or missing-dependency error.

`references/verilator-runtime.md` tells either skill when to use the wrapper,
how selection works, and how to diagnose failures. The reference is loaded
only when a task actually needs Verilator.

### Provenance and Licensing

`tools/verilator/linux-x86_64/manifest.json` records the exact upstream tag,
source URL, architecture, build environment/ABI baseline, and file checksums.
Build timestamps do not affect reproducible content hashes.

The repository's own content uses Apache-2.0. Verilator retains its upstream
`LGPL-3.0-only OR Artistic-2.0` notices and license materials under
`third_party/verilator`, with a top-level third-party notice. This design is a
technical packaging choice, not legal advice; organizational policy may still
require review before public distribution.

## Validation Strategy

### Skill Evaluation-Driven Development

Before writing each skill, run fresh agents on representative tasks without
the skill and retain the observed failures. Scenarios cover:

- respecting an existing project's RTL style instead of forcing fallback
  naming;
- applying safe fallback rules in a project with no conventions;
- finding functional RTL hazards during review;
- preserving an existing nonstandard testbench layout;
- creating a new testbench layout without `hardware_design` assumptions;
- implementing and verifying a small DUT end to end.

After implementation, repeat the scenarios with the appropriate skill or both
skills loaded. Use isolated fixtures and minimal task-local context so the
evaluation cannot succeed from leaked intended answers.

### Static Validation

Automated checks cover:

- valid `SKILL.md` frontmatter and skill naming;
- `agents/openai.yaml` consistency;
- valid Claude and Codex manifests and marketplaces;
- equality of the three release-version fields;
- `bash -n`, `shellcheck`, and executable modes for shell scripts;
- absence of TODO placeholders, `hardware_design`, `therm_top.sv`, and
  developer-machine absolute paths from runtime instructions and artifacts;
- Verilator provenance, licensing, and checksums.

### Runtime Tests

Tests must prove:

- bundled `verilator --version` reports 5.050;
- valid RTL lint succeeds and deliberately invalid RTL lint fails;
- a minimal self-checking testbench builds and runs;
- an explicit project Verilator overrides PATH and bundled tools;
- a permitted PATH Verilator overrides the bundle;
- missing dependencies and unsupported bundled platforms fail clearly;
- installed files contain no dependency on the build machine's paths.

## Versioning and Maintenance

Any release-affecting change under `skills/`, `references/`, `scripts/`, or
`tools/` increments and synchronizes:

1. `.claude-plugin/marketplace.json` `metadata.version`;
2. `.claude-plugin/plugin.json` `version`;
3. `.codex-plugin/plugin.json` `version`.

README-only changes need no version increment. Development evaluation reads
skills directly from the clone. Published evaluation uses the remote
marketplace, updates/reinstalls the plugin, and starts a new session.

## `dev-tools` Integration

After the module repository contains committed implementation:

1. register `modules/rtl-coding-skills` in `.gitmodules` using the SSH remote;
2. add its pinned Git commit as a submodule entry;
3. update `docs/submodules.md` only with root-repository maintenance details;
4. stage neither the user-updated `modules/eda-server` pointer nor unrelated
   worktree state;
5. validate the submodule from a clean clone path.

Remote pushes remain a separate explicit user decision.
