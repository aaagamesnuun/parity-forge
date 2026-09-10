> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Failure taxonomy

Failures are explicit, stable machine-readable codes. Multiple codes may apply.

| Code | Meaning |
|---|---|
| `INVALID_DEFINITION` | DSL structure or value violates the schema |
| `NO_LEGAL_MOVE_AT_START` | first player cannot act initially |
| `UNREACHABLE_WIN_CONDITION` | a role cannot reach its goal under a cheap sound check |
| `NON_TERMINATING` | termination is not safeguarded or observed |
| `TRIVIAL_FORCED_RESULT` | result exists initially or follows without meaningful choice |
| `A_DOMINANT` | evidence indicates a material A advantage |
| `B_DOMINANT` | evidence indicates a material B advantage |
| `EXCESSIVE_DRAWS` | draw rate exceeds the evaluator gate |
| `TOO_SYMMETRIC` | roles lack meaningful action/goal differences |
| `TOO_COMPLEX` | candidate exceeds an explicit complexity gate |
| `TOO_SHORT` | play terminates before meaningful interaction |
| `TOO_LONG` | play is operationally excessive |
| `NO_MEANINGFUL_CHOICE` | most decision points have at most one legal action |
| `SINGLE_STRATEGY` | evidence suggests one viable strategic family |
| `SOLVED_OPENING` | one opening dominates under adequate analysis |
| `AGENT_DISAGREEMENT` | evaluator families materially disagree |
| `EVALUATOR_SUSPECTED_FALSE_POSITIVE` | candidate likely exploits current proxies |

New codes require an observed failure that existing categories obscure, a decision
record, and regression evidence where practical.
