# ADR-0001: Record architecture decisions in ADRs

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: governance, documentation

## Context and problem statement

As the codebase grows, the team (and future contributors) needs to understand **why** a particular technology, pattern, or trade-off was chosen — not just **what** was built. Without a decision log:

- New contributors re-litigate old decisions
- Implicit knowledge leaves with team members
- "Why isn't this using X?" questions repeat
- The reasoning behind trade-offs is lost

## Decision drivers

- Long-term maintainability over short-term velocity
- Onboarding new contributors
- Auditable trail of design choices
- Lightweight process that doesn't slow development

## Considered options

1. **No decision log** — implicit tribal knowledge
2. **Wiki / Notion pages** — easy to write, but loses context, hard to version-control
3. **Git-tracked ADRs (MADR format)** — version-controlled, PR-reviewable, lives next to code

## Decision outcome

**Chosen option 3: MADR-format ADRs in `docs/adr/`, tracked in git, version-controlled alongside the code they describe.**

Each ADR:

- Is a small markdown file (~50–200 lines)
- Captures **Context**, **Decision drivers**, **Considered options**, **Decision outcome**, **Consequences**
- Is proposed in the same PR as the change it documents
- Goes through code review
- Status transitions: Proposed → Accepted → (Deprecated | Superseded)

The template lives at [`docs/adr/template.md`](template.md).

### Consequences

**Positive**

- Decision rationale is preserved with the code
- PR review naturally extends to design decisions
- Searchable via grep / GitHub code search
- Forces the author to think through alternatives

**Negative**

- Slight upfront cost per non-trivial decision
- Risk of "ADR sprawl" if every micro-decision is recorded
- Requires discipline to keep current

### Confirmation

- Every PR that introduces a new dependency, new AWS service, breaking API change, or significant refactor includes an ADR
- The `docs/adr/` directory grows steadily (target: 1–2 per month in steady state)

## Pros and cons of the options

| Option | Discoverability | Reviewability | Cost | Discipline needed |
|---|---|---|---|---|
| 1. No log | ❌ Lost | ❌ None | None | High (always forgetting) |
| 2. Wiki | ⚠️ Drift | ⚠️ Decoupled | Low | Medium |
| 3. MADR in git | ✅ Searchable | ✅ PR review | Low | Medium |

## References

- [MADR — Markdown Any Decision Records](https://adr.github.io/madr/)
- [Documenting Architecture Decisions (Michael Nygard)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
