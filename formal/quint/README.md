# Quint models for coverage and pruning

## Coverage models

[`covering.qnt`](covering.qnt) uses one catalog for model checking and Rust test data. It includes compound pairwise exclusions, single-factor coverage with mixed level counts and a multi-level exclusion term, three-way coverage of four factors where pairwise coverage can omit a required triple, full order, and a model with no legal rows.

- `DepthFirst` starts from every partial assignment in the catalog. It fills the first unassigned factor and explores every possible sibling order. `CompletionConservation` checks that discovered rows and the legal completions of unvisited branches together equal the legal completions of the original seed. `SearchProgress` checks that each nonterminal step reduces the remaining search weight. `NoRepeatCompletion` checks that every discovered row is outside the branches yet to be explored.
- `CoveringLoop` consumes one interaction per step in any order. It can choose any legal completion of an uncovered feasible interaction. The invariants check row legality, coverage of processed feasible interactions, exact final coverage, and an empty result exactly when no legal row exists.

Run the models from the repository root with Quint 0.33.1 and Java 21.

```sh
quint typecheck formal/quint/covering.qnt
quint verify formal/quint/covering.qnt --backend=tlc --main DepthFirst \
    --invariants CompletionConservation SearchProgress NoRepeatCompletion
quint verify formal/quint/covering.qnt --backend=tlc --main CoveringLoop \
    --invariants LegalRows ProcessedCoverage FinalCoverage NoValidCases
```

TLC checked 1,230 reachable states in `DepthFirst` and 1,720,037 in `CoveringLoop` with no violations. The catalog bounds this result. The coverage loop abstracts search through the contract that an uncovered feasible interaction has a legal completion. The depth-first model checks the contract for these inputs and abstracts the generator's scoring by allowing any sibling order. The covering model derives covered interactions from its selected rows. The Rust generator maintains an incremental set.

Each command below should exit with a counterexample. `DepthFirstMutant` drops level zero from a branch. `CoveringLoopMutant` skips an uncovered feasible pair.

```sh
quint verify formal/quint/covering.qnt --backend=tlc --main DepthFirstMutant \
    --invariants CompletionConservation
quint verify formal/quint/covering.qnt --backend=tlc --main CoveringLoopMutant \
    --invariants ProcessedCoverage
```

## Exhaustive checks for three binary factors

[`exhaustive.qnt`](exhaustive.qnt) checks all 256 subsets of the eight binary rows. Each excluded row becomes a rule that matches all three factors. This gives one rule representation of each legal-row set. The original catalog also exercises rules that match partial assignments.

- `BinaryDepthFirst` checks every partial assignment for each exclusion set. TLC started from 6,912 initial states and found no invariant violations in 50,512 reachable states.
- `BinaryCovering` checks all 256 exclusion sets at orders one through three. It processes seeds in lexicographic order by factor indices and then by levels, as Rust does for partial orders. The model accepts any legal completion of the current seed. Rust uses the first completion from its scored search, and at full order it enumerates all legal rows directly.
- The covering model checks that its candidate sequence matches the exhaustive projection set in the specified order, that the pending seeds remain a suffix of that sequence, that its cache equals the projections of the selected rows, and that each selected row is legal and unique. It checks coverage after each processed seed and at completion. `Finishes` checks that the seed list eventually becomes empty under weak fairness. A continuously enabled step must eventually run. TLC checked these properties from 768 initial states across 19,193 reachable states.

```sh
quint typecheck formal/quint/exhaustive.qnt
quint verify formal/quint/exhaustive.qnt --backend=tlc --main BinaryDepthFirst \
    --invariants CompletionConservation SearchProgress NoRepeatCompletion
quint verify formal/quint/exhaustive.qnt --backend=tlc --main BinaryCovering \
    --invariants SeedEnumeration CacheMatchesSelection LegalUniqueRows \
    ProcessedCoverage FinalCoverage NoValidCases --temporal Finishes
```

The mutant appends a legal row without updating the cache. TLC reports a counterexample after the first selected row. In a separate copy of the model, leaving the pending list untouched also produces a counterexample to `Finishes`.

```sh
quint verify formal/quint/exhaustive.qnt --backend=tlc --main BinaryCoveringMutant \
    --invariants CacheMatchesSelection
```

The Rust regression test exercises the same 768 inputs through `generate` and checks the returned rows against the exhaustive Rust oracle. Clearing the cache after selecting a row in an isolated copy of the generator causes the test to report duplicate rows at order one.

```sh
cargo test --locked -p pytest-allpair-core --test coverage_properties \
    exhausts_all_binary_row_exclusions_and_orders
```

## Replaying Rust covering traces

The replay test checks the Rust covering loop at each processed seed. An internal observer records the seed, the row appended when there is one, and the coverage cache after the step. The Rust test exports 512 executions for all three-binary-factor exclusion sets at orders one and two. They contain 4,608 steps, including already-covered and infeasible seeds.

[`replay.qnt`](replay.qnt) uses the same transition definitions as `BinaryCovering`. It starts from the corresponding model input, checks each observed event against the allowed next events, and accepts the execution once every seed has been processed. The model allows any legal completion of a seed. The existing depth-first model and final-output tests cover search and full-order enumeration.

Run from the repository root with Quint 0.33.1. The Rust exporter writes the generated Quint tests into `target/quint/`. The replay uses the TypeScript backend.

```sh
cargo test --locked -p pytest-allpair-core --lib export_binary_covering_traces -- --ignored
quint test formal/quint/replay.qnt --main CoveringReplayTests --backend=typescript
quint test target/quint/covering_replay.qnt --main CoveringReplayCases --backend=typescript
```

The hand-written traces exercise rejection of an invalid exclusion, a missing or extra step, a wrong seed, an unsupported row, and a stale cache. In an isolated Rust copy, reversing the candidate levels within each axis combination still satisfies the exhaustive output oracle. Quint rejects the reordered trace.

## Replaying Rust depth-first traces

The Rust exporter takes the five problems from the checked-in Quint ITF catalog. It runs the actual depth-first search on all 138 partial assignments. The exhaustive visitor records every completion in ascending candidate order. The first-hit visitor uses descending candidate scores and returns the first completion.

The exporter records 276 executions and 775 node visits, including 152 prunes. A Quint assertion checks that the exported tests include each catalog problem, partial assignment, and termination mode exactly once. For each visit, [`depth_first_replay.qnt`](depth_first_replay.qnt) checks the current stack frame and the prune, expand, or complete decision against the same transitions that TLC checks. It also matches the visitor's delivered rows and the actual return value. An exhaustive execution must empty the frontier. A first-hit execution must return immediately on its first completion, or exhaust the frontier if no completion exists. The model allows any sibling order.

```sh
cargo test --locked -p pytest-allpair-core --lib export_depth_first_traces -- --ignored
quint test formal/quint/depth_first_replay.qnt --main DepthFirstReplayTests --backend=typescript
quint test target/quint/depth_first_replay.qnt --main DepthFirstReplayCases --backend=typescript
```

In isolated Rust copies, the replay rejects reversed factor order and continuing after the visitor requests a break. The reversed-factor version still satisfies the exhaustive output oracle for three binary factors.

## Live model-based tests with Quint Connect

Quint Connect generates ITF traces from [`model_based.qnt`](model_based.qnt). The standalone Rust test workspace in [`connect/`](connect/) decodes each sampled input and calls the public `generate` function. It compares whether a legal case exists, whether selected rows are legal and unique, and the exact set of covered interactions. Quint derives the expected state by enumerating legal rows. The model samples the example catalog and the binary exclusion tables used by the exhaustive checks.

A separate Proptest requires all sixteen generated-input steps across the four traces of each run. It samples one to five factors, one to three levels per factor, any valid coverage order, and zero to five exclusion rules. A rule can refer to any nonempty subset of factors and can select several levels per factor. Quint's decoder tests compare all rule encodings for a mixed-level model against the Cartesian product of the allowed level subsets. In an isolated Rust copy, dropping every level except the first from each exclusion term produced a state mismatch.

The fixed seed exercises the bridge. The negative control lowers the Rust request from three-way to pairwise coverage and requires Quint Connect to report a state mismatch. Proptest generates Quint seeds and equivalent rule encodings by repeating and reversing rules and reversing the order of their terms and levels. A failure reports the seed and the rule encoding selected by Proptest.

The dedicated CI job installs Quint 0.33.1 with npm and uses the TypeScript evaluator. On Linux or macOS, run the same test from the repository root with Node 22 and the repository's Rust toolchain.

```sh
npm ci --prefix formal/quint --ignore-scripts --no-audit --no-fund
formal/quint/connect/bin/quint test formal/quint/generated_inputs.qnt --main GeneratedProblemsTests
PATH="$PWD/formal/quint/connect/bin:$PATH" \
    cargo test --manifest-path formal/quint/connect/Cargo.toml --locked
```

Set `PROPTEST_RNG_SEED` to reproduce a Proptest run. Use `QUINT_VERBOSE=1` and pass `-- --nocapture` to Cargo to see generated actions and state differences.

## Rust conformance test

The `Witnesses` module exports a one-state [ITF trace](https://apalache-mc.org/docs/adr/015adr-trace.html) with the catalog inputs, legal rows, and feasible interactions derived by exhaustive enumeration. Each interaction is a row with `-1` in every unselected factor. The Rust integration test calls the public `generate` function on each input and checks legality, uniqueness, exact interaction coverage, all legal rows at full order, and `NoValidCases` for an infeasible input. The test uses the checked-in trace and runs without Java or Quint. Replacing order three with order two in an isolated copy of the Rust generator fails the test on the four-factor model.

```sh
cargo test --locked -p pytest-allpair-core --test quint_coverage
```

When the catalog or its expected results change, regenerate the trace from the repository root. Remove the two time-dependent metadata fields so the file is reproducible.

```sh
quint run formal/quint/covering.qnt --main Witnesses --backend=typescript \
    --max-steps=0 --max-samples=1 --seed=1 --verbosity=0 \
    --out-itf=formal/quint/coverage.itf.json
python3 - <<'PY'
import json
from pathlib import Path

path = Path("formal/quint/coverage.itf.json")
trace = json.loads(path.read_text(encoding="utf-8"))
for field in ("description", "timestamp"):
    trace["#meta"].pop(field, None)
path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
PY
```

## Pruning model

The model uses three binary factors, A, B, and C. It excludes rows where A and B are both 0 and represents unassigned values as `-1`. The `SoundPrune` invariant enumerates valid rows to check that no discarded assignment can extend to a valid complete case.

Run the model with Quint 0.33.1 and Java 21.

```sh
quint typecheck formal/quint/pruning.qnt
quint verify formal/quint/pruning.qnt --backend=tlc --main Pruning --invariants SoundPrune
quint verify formal/quint/pruning.qnt --backend=tlc --main PruningMutant --invariants SoundPrune
```

TLC checked 27 reachable states in `Pruning` and found no violation. `PruningMutant` discards a branch when either A or B is 0. TLC found a counterexample in which the mutant discarded the partial assignment `B=0, C=0`. Setting `A=1` makes that assignment valid.

Use Apalache to write a violation of the same invariant as an ITF trace. The command exits after reporting the violation.

```sh
quint verify formal/quint/pruning.qnt --backend=apalache --main PruningMutant \
    --invariants SoundPrune --max-steps=1 --out-itf=pruning-mutant.itf.json
```

The Rust test `covers_feasible_pairs` calls the public generator with the same factors and constraint and checks the 11 pairs from the valid rows. In an isolated copy of the Rust code, we changed the pruning condition from a match on every term to a match on any term. The test failed because the generated set of pairs differed from the expected set. Keep the public-generator test in the regression suite and generate ITF traces when investigating model counterexamples.

TLC checks the pruning rule within this finite model. The coverage oracle and fuzz tests exercise the Rust search with varying numbers of factors.
