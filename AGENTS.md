# Parity Forge operating contract

## Team snapshot boundary

If `SHARE_MANIFEST.json` exists, this checkout is a selected team snapshot, not
the original research host. Read `docs/team/START_HERE_JA.md` and
`docs/team/SHARING_SCOPE_JA.md`. State/active-plan/backlog records describe the
owner's checkpoint, not authority to resume its workers, schedules or one-shot
experiments. Never recreate missing claims or infer that absent evidence means
an unused budget. Begin with the assigned member task and the documented
synthetic smoke tests; coordinate new experimental IDs and data with the owner.
Do not treat an unavailable full regression as a pass. For code changes, report
the missing integration evidence and arrange owner-side acceptance before merge.

The user's 2026-09-10 team-sharing request authorizes a separate, selected system
and research-context export (D-086), not publishing credentials, protected raw
evidence, the original Git history, or modifying the existing public game repo.

Parity Forge is a research system for discovering mechanically asymmetric
two-player abstract games worth playing. User clarification (2026-09-08): board
size and extreme rule simplicity are not hard constraints; balance, depth and
simplicity are design/evaluation goals. Mechanical asymmetry and the no-draw
condition below remain mandatory. The DSL, engine, experiments, and project
records must remain deterministic, inspectable, and reproducible. See D-064 and
docs/reviews/2026-09-08-discovery-reset-and-human-ai-loop-ja.md.

Product hard constraint (user confirmed 2026-09-05): discovery targets must
have no draw outcome. Every legal play from an admitted initial state must
terminate after finitely many moves with exactly one winner, A or B. This is
not merely zero draws in sampled or optimal play. Preserve historical draw
fixtures/results; search-budget exhaustion remains UNKNOWN, never a game result.
See docs/CHARTER.md and decision D-055. Do not resume draw-preserving candidate
research or silently choose replacement winner/tiebreak rules.

Product exclusion (user confirmed 2026-09-10, D-080): do not discover, extend,
or recommend games whose winner is determined by a player running out of legal
placements ("最後に置けなかったほうが負け", equivalently last legal placement wins).
This is a hard design exclusion, not a low evaluation score. Placement itself is
allowed; capture, connection, arrival or other substantive victory objectives
must be reviewed separately, including all-play finite, unique termination.
Do not evade the exclusion by renaming the same exhaustion mechanic as movement
or silently reversing the winner. Stop Plan38's TILE continuation; preserve old
DSLs, tests, immutable results and existing public Site/GitHub unchanged unless
separately asked to modify or withdraw them. See docs/CHARTER.md and D-080.

Game delivery preference (user confirmed 2026-09-10): current and future playable
game URLs must work without login or account creation. Use public, anonymous
access for the game Site; verify an unauthenticated request before handing off.
This does not authorize publishing private research records, secrets, or unrelated
Sites. Preserve administrative authentication and do not add a login gate to play.
See decision D-074; the earlier owner-only trial was superseded for game access.

Start every work session by reading, in order:

1. [`docs/PROJECT_STATE.md`](docs/PROJECT_STATE.md)
2. the single plan in [`docs/plans/active/`](docs/plans/active/)
3. [`docs/BACKLOG.md`](docs/BACKLOG.md)

Working rules:

- The machine-readable DSL is authoritative; prose rules are derived from it.
- Preserve frozen fixtures and immutable experiment runs.
- Separate generator, evaluator, agent, DSL, and search changes in experiments.
- Prefer the smallest reversible implementation or experiment that reduces the
  most important uncertainty.
- Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` before completing
  a code change; the project intentionally does not require installation.
- Update project state and the active plan before ending a session.
- Ask the human only for taste, purpose, permission, resources, or irreversible
  choices—not routine technical decisions.

Documentation map: [`docs/INDEX.md`](docs/INDEX.md).
