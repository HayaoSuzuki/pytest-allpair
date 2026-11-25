# pytest-allpair design

## Purpose and example

At collection time, the plugin generates constraint-aware n-way combinations from the declared factors. It registers those cases as pytest parameters so pytest can select and run them as usual.

```python
import pytest


@pytest.mark.pairwise(order=3, exclude=[{"os": "linux", "filesystem": "ntfs"}])
@pytest.mark.pairwise_parametrize("os", ["linux", "windows"])
@pytest.mark.pairwise_parametrize("filesystem", ["ext4", "ntfs"])
@pytest.mark.pairwise_parametrize("cache", [False, True])
@pytest.mark.pairwise_parametrize("mode", ["read", "write"])
def test_storage(os, filesystem, cache, mode):
    ...
```

The design follows PICT on coverage order, when to apply constraints, and how to reproduce generated cases. The first release exposes `order` and `exclude`. Submodels, weights, seed rows, and negative-value rules remain candidates for later releases. [PICT documentation](https://github.com/microsoft/pict/blob/main/doc/pict.md)

## pytest interface

Each `pairwise_parametrize(argnames, argvalues, *, ids=None, indirect=False, scope=None)` declares a factor, and each candidate row is one level. For example, the candidates `(1, 2)` and `(3, 6)` for `"input,expected"` are separate levels that keep each input paired with its expected result. The plugin distinguishes equal candidate rows by position. It collects markers from functions, classes, and modules in pytest's marker lookup order.

The optional configuration marker `pairwise(*, order=..., exclude=...)` can appear once on a test function. Standard `parametrize` and `fixture(params=...)` form a Cartesian product with the generated cases. pytest reports a duplicate parametrization error if a factor and either of the standard mechanisms specify the same argument. That includes a duplicate fixture parameter declared with `indirect=True`. To include fixture values in the covering array, declare them on the factor marker. [pytest's fixture collection hook](https://docs.pytest.org/en/stable/_modules/_pytest/fixtures.html#FixtureManager.pytest_generate_tests)

| Setting | Coverage |
| --- | --- |
| Omitted | Order 2 or the number of factors, whichever is smaller. With one factor, this covers every feasible level. |
| `order=1` | Each level that can appear in a valid complete case |
| `order=n` | Each feasible n-way interaction. The integer must be between 1 and the number of factors. |
| `order="max"` | Every valid complete case |

The plugin preserves marks and IDs from `pytest.param(..., marks=..., id=...)`, each factor's `ids`, and its `indirect` setting. It combines marks from the selected levels and joins ID fragments in factor order. pytest supplies missing IDs and resolves duplicates. A level with `pytest.HIDDEN_PARAM` contributes no ID fragment. The Python compatibility layer prefers public APIs and handles differences between pytest versions.

Fixtures specified by `indirect` receive the candidate through `request.param`. The plugin registers the generated table in one call to `Metafunc.parametrize`, so every factor must specify the same scope if you set `scope`. If you omit it, pytest infers the scope. [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) · [Metafunc.parametrize](https://docs.pytest.org/en/stable/reference/reference.html#pytest.Metafunc.parametrize)

## Exclusions and collection errors

`exclude` accepts a sequence of dictionaries that map argument names to values. A dictionary matches a full case when every entry matches using Python equality. Any matching dictionary excludes the case. If several candidates compare equal to a value, the rule covers all of them. If one dictionary names several arguments from the same factor, it matches only candidate rows that satisfy all of those entries.

Collection fails for duplicate or misplaced configuration markers, a configuration marker without factors, duplicate argument names, invalid orders, and invalid exclusions. Invalid exclusions include empty dictionaries, unknown argument names, values that match no candidate, and equality results that cannot be evaluated as booleans. An empty candidate list follows pytest's `empty_parameter_set_mark` setting. If every factor has candidates and exclusions rule out all complete cases, the collection error includes the test name and the cause.

## Coverage contract

A complete case selects one level from each factor. A case is valid if it avoids every exclusion. An n-way interaction is identified by the positions of its n factors and their selected levels.

Every output row must be valid, and **every n-way interaction present in a valid complete case must appear in at least one output row**. An interaction qualifies for coverage if it can be extended to a valid complete case. Coverage applies to the generated rows. pytest selection and marks, including `-k`, `-m`, and `skip`, determine which rows run.

Within one version, the same factor order, candidate order, coverage order, and exclusions produce the same rows in the same order. The generator chooses rows that cover several interactions at once. It can choose any row count that meets the coverage contract.

## Repository layout and implementation

| Location | Responsibility |
| --- | --- |
| `crates/pytest-allpair-core/` | Search for valid complete cases and cover interactions of the requested order in Rust |
| `crates/pytest-allpair-python/` | PyO3 bridge and Python package for pytest markers, values, IDs, and fixture settings |
| `tests/` | Integration tests for pytest collection, execution, and distribution checks |
| `formal/`, `fuzz/` | Reference oracle, formal verification experiments, and generator fuzzing with small models |
| `docs/user/`, `docs/development/` | Usage, design, and verification guides |
| `tools/`, `.github/workflows/`, `infra/` | Local verification, CI, and distribution configuration |

The root contains the Cargo workspace and `pyproject.toml`. maturin builds the distribution, and pytest loads the plugin through the `pytest11` entry point. Supporting directories follow the layout of hoimin. The project uses the MIT license.

Python passes the number of candidates per factor, the coverage order, and the exclusion rules to Rust. Each rule maps factor positions to sets of candidate row indices. A complete case matches a rule if its selected row index belongs to the specified set for every factor in that rule. The Rust generator computes the selected row indices from its inputs, independent of pytest, files, the network, and the clock. The Python plugin handles pytest, and PyO3 passes the numeric model and translates errors. Python uses the returned indices to recover the original values, marks, and IDs and register them with pytest.

The first generator considers uncovered interactions in sequence. It uses an interaction that has a valid completion as the starting point for a row that can cover several interactions. Only an exhaustive search of the remaining candidates can establish that an interaction has no valid completion. The search order and tie-breaking are deterministic. The generator avoids materializing the Cartesian product as an intermediate table. When the order equals the number of factors, the required output itself can reach that size. The implementation chooses the search order, how to represent uncovered interactions, and the pruning conditions.

The plugin collects dedicated markers and registers the generated cases through the public `pytest_generate_tests` hook. One option was to add a configuration marker to standard parametrization, which would require intercepting pytest's expansion. Another was to filter collected items using their existing IDs and marks, after pytest had expanded the full Cartesian product. Dedicated markers identify the factors in the declaration and allow the plugin to apply constraints before it generates complete cases.

## Verification

The first release must include tests that enumerate all complete cases for small models and compare the Rust output with the n-way interactions in the valid cases. The tests check that each generated row is valid and that the sets of covered and required interactions match. They cover orders 1, 2, 3, and the maximum, factors with different candidate counts, interactions made infeasible by a combination of rules, and models with no valid cases. Fuzz tests check the same contract on generated small inputs.

The reference regression uses three binary factors `A, B, C` and forbids `A=0, B=0`. Six complete cases are valid, and the generator must cover 11 pairs. If you choose `000, 011, 101, 110` without considering constraints and then remove `000`, you lose the feasible pairs `A=0, C=0` and `B=0, C=0`. The coverage oracle detects this error.

Quint and TLC check that pruning preserves every legal completion, depth-first search progresses, and the covering loop selects legal rows that cover every feasible interaction. These checks run on a finite catalog with exclusions and several coverage orders. The three-binary-factor model checks every possible set of legal rows, including how the covering loop maintains its cache and reaches completion. Intentional faults in the models yield counterexamples. Rust execution traces feed candidate order, the row selected by the coverage score and tie-break, and cache contents back into the same Quint transition definitions. Quint Connect also compares the order of rows returned at full coverage order. Depth-first traces check pruning decisions, completion visits, and the first-hit return. The Quint Connect test workspace also uses model-generated ITF executions to check the public Rust generator with rule encodings chosen by Proptest. Its generated-input action varies the factor counts, coverage order, and exclusions within the exhaustive oracle's bounds. The catalog also exports legal rows and feasible interactions as an ITF trace for a regression test of the public Rust generator. [Quint model checkers](https://quint.sh/docs/model-checkers) · [ITF](https://apalache-mc.org/docs/adr/015adr-trace.html)

The pytest integration tests collect and run cases with grouped arguments, marks and IDs, indirect fixtures, class and module markers, standard parametrization, duplicate arguments, other collection errors, and empty candidate lists. They target standard (GIL-enabled) builds of CPython 3.11 through 3.15 and pytest 8.4.x and 9.x. The Linux, macOS, and Windows checks install wheels and verify plugin discovery and execution.

During design review, check that PyO3 sends only the numeric model to Rust and that the reference oracle computes its results independently of the generator's search. For performance, use a low coverage order with a large Cartesian product. Check that the generator returns the required rows before pytest collects the cases without holding all complete cases in memory.
