# ADR-0009: Polyrepo architecture (one repo per project), not a monorepo

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: governance, repository-structure

## Context and problem statement

The portfolio consists of 15 projects (14 industry-specific agents + 1 meta "DataCurator" foundation). The question: should they share a single Git repository (monorepo) or be split into separate repositories (polyrepo)?

## Decision drivers

- **Independent deploy lifecycles** — DataCurator updates shouldn't trigger FinSight CI
- **Permission isolation** — different stakeholders may have different access
- **Public discoverability** — recruiters find one project, see the portfolio
- **CI cost** — monorepos can have expensive CI on every change
- **Tooling simplicity** — each project has its own tools, workflows

## Considered options

### Option 1: Monorepo (e.g., `cloud-ai-architect/portfolio` with 15 subdirs)

- ✅ Single source of truth
- ✅ Atomic cross-project changes
- ❌ All CI runs on every change (waste)
- ❌ Permission model is one big "everything"
- ❌ Recruiter lands on a "kitchen sink" repo, not a focused project
- ❌ Repo size grows unbounded

### Option 2: Polyrepo (one repo per project) (chosen)

- ✅ **Independent CI/CD** per project
- ✅ **Independent version releases**
- ✅ **Focused, recruiter-friendly** repo per project
- ✅ **Permission isolation** — restrict DataCurator deploys separately
- ✅ **Smaller, faster clones**
- ✅ **Clear "what does this project do"** in the README
- ⚠️ Shared code (e.g., data_curator library) needs separate versioning
- ⚠️ Cross-project changes require coordinated PRs

## Decision outcome

**Chosen option 2: Polyrepo, one repo per project.**

Naming convention:

```text
cloud-ai-architect/
├── datacurator-meta              # This repo (Project 15)
├── retailpulse-cx-agent          # Project 13
├── medassist-clinical-copilot    # Project 1
├── finsight-equity-research      # Project 2
├── codeforge-swe-team            # Project 3
├── learnpath-edu-tutor           # Project 4
├── insureflow-claims             # Project 5
├── telecomops-network            # Project 6
├── cybersentinel-threat          # Project 7
├── govserve-citizen              # Project 8
├── mediahub-content              # Project 9
├── legallens-contract            # Project 10
├── agrisense-farm                # Project 11
├── supplynet-logistics           # Project 12
└── gridsense-energy              # Project 14
```

Shared code (e.g., a `data_curator_client` library for downstream projects to query the DataCurator KB) is published as a separate `cloud-ai-architect/data-curator-client` package and versioned with `semver`.

### Consequences

**Positive**

- Each repo's README leads with what that project does — clear story
- CI runs only what's needed
- Recruiters see focused, deep work per project
- Permission isolation for security-sensitive projects
- Each repo can use a slightly different stack if needed (though we standardize)

**Negative**

- Shared library versioning overhead
- Cross-project changes need coordination (mitigated by the client package)
- Slightly more work to set up GitHub org structure (one-time)

### Confirmation

- Each of the 15 projects has its own repo
- Shared `data-curator-client` published with `semver` tags
- All repos follow the same standards (CI, ADRs, docs structure) — this is the consistency that makes the portfolio feel coherent

## Pros and cons of the options

| Option | CI cost | Discoverability | Permissions | Cross-cutting changes |
| --- | --- | --- | --- | --- |
| Monorepo | High (waste) | Mixed | Coarse | Easy |
| **Polyrepo** | **Low (per project)** | **Focused** | **Fine** | **Coordinated** |

## References

- [Google's monorepo approach (large-scale)](https://research.google/pubs/large-scale-monorepo-development-at-google/)
- [Polyrepo vs monorepo tradeoffs](https://blog.nrwl.io/monorepo-vs-polyrepo-at-nrwl-3a5b8e2bd62a)
