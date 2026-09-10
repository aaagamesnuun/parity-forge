> 共有スナップショットの参照資料。元ホストの記録であり、実行・再開・公開の指示ではありません。未収録の証拠へのリンクを含みます。共有範囲は `docs/team/SHARING_SCOPE_JA.md` を参照してください。

# Experiment protocol

Every significant experiment begins with a written hypothesis and one primary
variable. Preserve a baseline, freeze the components not under study, and specify
the expected result and decision rule before running.

Each immutable run directory uses a UTC timestamp plus collision-resistant suffix
and contains, where applicable:

- run ID, git commit or `UNCOMMITTED`, dirty-state flag, host and Python version
- start/completion timestamps and status
- configuration, component versions, seeds, and corpus identity
- aggregate and candidate-level metrics
- rejection reasons and failure histogram
- hypothesis, baseline, treatment, expectation, result, interpretation, decision

Never overwrite a run. Failed runs remain evidence. Frozen corpus definitions and
expected classifications change only through a documented decision explaining why
the old expectation was wrong. Reports distinguish observation, inference,
hypothesis, proof, and human judgment.

For stochastic work, record the complete seed list and use locally constructed
random-number generators. A repeated run with identical versions, definition,
configuration, and seed must reproduce candidate-level output.

Search budgets use deterministic work units such as expanded nodes or searched
states. Wall time is recorded only as an environmental observation. A budget limit
produces an explicit censored/unknown result and must never be silently converted
into a game rejection or evaluator success.

A one-shot held-out run writes immutable attempt metadata before candidate
generation. Completion writes a separate result record; an exception writes a
separate failure record. The runner fails closed on configuration/source drift, a
dirty or uncommitted repository, or prior attempt evidence for the same protocol.

The landscape protocol extends this into three separately committed stages:

1. freeze an outcome-free selection manifest and byte-level SHA lock from a clean
   source commit;
2. evaluate every frozen case and commit the raw record;
3. select exact draws only from that committed record and commit the separate
   depth-limited stress record.

Manifest attempt, provenance, lock, source metadata, component fingerprints, and
Git ancestry must agree independently. Scientific source metadata uses
repository-relative paths; absolute paths belong only to environment-specific
attempt evidence. Existing source runs may contain outcomes, so provenance states
whether outcome fields were consulted rather than claiming the files were unread.

Each one-shot landscape evaluator atomically reserves its protocol ID before
creating a run directory. The reservation, attempt, completed record, or failure is
permanent evidence and blocks concurrent or later reruns. Raw-to-stress validation
rejoins every candidate to the manifest, recomputes structural gates, validates
cheap summaries and failure codes, and reconstructs exact aggregates before any
adaptive draw search begins.

The schema-v2 stalemate test adds a stricter paired chain. Its outcome-free
manifest is derived only from the frozen landscape manifest and records both v1
and one-field v2 identities. The raw runner first re-evaluates the complete ordered
v1 subset and requires candidate-level equality with the pinned historical raw
record, excluding elapsed time. Only after that full replay check may the runner
evaluate a v2 treatment. A source-byte or executable-fingerprint change across
that boundary aborts the attempt. The adaptive stress stage consumes only a
committed paired record and independently revalidates the manifest, historical v1
join, exact proofs, play summaries, aggregates, selection order, and assessments.

The completed schema-v2 chain exposed an evidence-completeness requirement for
future paired experiments. Passing a replay gate in frozen control flow is not, by
itself, a reconstructable artifact-level attestation. A paired raw record must seal
timing-free candidate-level replay evidence, or an ordered collision-resistant
digest with per-case digests, and its public validator must recompute that evidence
from the pinned baseline. A match count derived from the treatment denominator is
not sufficient. This requirement applies before any later treatment evaluation and
does not retroactively alter the immutable schema-v2 record.

Completed records are not trusted merely because they have the expected keys.
Validators reconstruct derived fields and totals from candidate evidence, verify
principal variations as legal terminal plays, and reject non-finite observations,
budget contradictions, unknown terminal reasons, or hook/configuration drift.
