# Finite model of pruning

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
