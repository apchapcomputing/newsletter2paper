# Newsletter2Paper — OpenSpec

This directory follows the [OpenSpec](https://github.com/Fission-AI/OpenSpec) spec-driven
development format.

## Structure

```text
openspec/
├── specs/                  ← source of truth: current system behavior
│   ├── authentication/
│   │   └── spec.md
│   ├── articles/
│   │   └── spec.md
│   ├── issues/
│   │   └── spec.md
│   ├── pdf-generation/
│   │   └── spec.md
│   └── publications/
│       └── spec.md
├── changes/                ← proposed modifications (one folder per change)
│   └── <change-name>/
│       ├── proposal.md
│       ├── design.md
│       ├── tasks.md
│       └── specs/          ← delta specs (ADDED / MODIFIED / REMOVED)
└── config.yaml
```

## Spec Domains

| Domain | Description |
| --- | --- |
| `authentication` | User identity, sessions, guest mode, RLS |
| `articles` | RSS article fetching, time-window filtering, pagination |
| `issues` | Newsletter configuration, frequency modes, publication associations |
| `pdf-generation` | End-to-end PDF pipeline, layout selection, image removal |
| `publications` | Publication registration, discovery, search |

## Working with Changes

To propose a new feature or modification, create a change folder:

```text
openspec/changes/<change-name>/
├── proposal.md    # Why and what (intent, scope, approach)
├── design.md      # How (technical approach, architecture decisions)
├── tasks.md       # Implementation checklist
└── specs/         # Delta specs — what's changing relative to specs/
    └── <domain>/
        └── spec.md
```

Delta specs use `## ADDED Requirements`, `## MODIFIED Requirements`, and
`## REMOVED Requirements` sections. On archive, deltas are merged into the main specs.

If the OpenSpec CLI is installed (`npm install -g @fission-ai/openspec`), you can use:

```bash
openspec init        # initialise (already done)
openspec list        # list active changes
openspec view        # interactive dashboard
```

Or use the AI slash commands: `/opsx:propose "your change"` → `/opsx:apply` → `/opsx:archive`
