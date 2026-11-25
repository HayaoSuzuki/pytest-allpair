# Quint models for coverage and pruning

## Coverage models

[`covering.qnt`](covering.qnt) uses one catalog for model checking and Rust test data. It includes compound pairwise exclusions, single-factor coverage with mixed level counts and a multi-level exclusion term, three-way coverage of four factors where pairwise coverage can omit a required triple, full order, and a model with no legal rows.

- `DepthFirst` starts from every partial assignment in the catalog. It fills the first unassigned factor and explores every possible sibling order. `CompletionConservation` checks that discovered rows and the legal completions of unvisited branches together equal the legal completions of the original seed. `SearchProgress` checks that each nonterminal step reduces the remaining search weight.
- `CoveringLoop` consumes one interaction per step in any order. It can choose any legal completion of an uncovered feasible interaction. The invariants check row legality, coverage of processed feasible interactions, exact final coverage, and an empty result exactly when no legal row exists.

Run the models from the repository root with Quint 0.33.1 and Java 21.

```sh
quint typecheck formal/quint/covering.qnt
quint verify formal/quint/covering.qnt --backend=tlc --main DepthFirst \
    --invariants CompletionConservation SearchProgress
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
    --invariants CompletionConservation SearchProgress
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
