# pytest-allpair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal**

Build an MIT-licensed pytest plugin that generates constraint-aware n-way covering cases from declared factors at collection time.

**Architecture**

Python translates pytest markers into candidate row indices and exclusion rules. Rust chooses valid rows that meet the coverage requirements. Python restores the values, marks, and IDs for each row and registers them in a single call to `Metafunc.parametrize`.

**Tech stack**

Rust 2024, PyO3 0.30.1 with `abi3-py311`, maturin, uv, pytest, and cargo-fuzz. Use Quint and TLC for an independent pruning experiment.

**Spec**

[pytest-allpair design](../../architecture/pairwise-plugin.md)

## Global Constraints

- Support standard (GIL-enabled) builds of CPython 3.11 through 3.15 and pytest 8.4.x and 9.x.
- On Linux, macOS, and Windows, install the wheel and verify plugin discovery and test execution.
- Expose `order` and `exclude` as the initial generator options. Use the MIT license.
- Within one version, the same factor order, candidate order, coverage order, and exclusions must produce the same rows in the same order.
- Avoid holding the full Cartesian product of complete cases as an intermediate table. Limit the reference oracle to small models.
- Complete each task with its own tests and commit. Publishing through the release account is a separate task.
- Use `main` as the default GitHub branch and block deletion and force pushes. Report CI results on GitHub and leave required merge checks empty, matching `HayaoSuzuki/hoimin`.
- Reserve `pytest-allpair-release-state` for release state. The rulesets block deletion and force pushes on that branch and block updates and deletion of existing `v*` tags.

## Review Focus

- Cover every n-way interaction that can extend to a valid complete case. Exclude an interaction from the coverage requirements when a combination of rules prevents all completions (Task 1).
- Ensure generated node IDs stay unique when joining distinct factor IDs produces identical strings (Task 3).
- Keep equal candidate rows distinct and apply exclusions to every candidate row that compares equal to the specified value (Task 3).
- Report a collection error when `indirect=True` and `fixture(params=...)` supply values for the same argument (Task 3).
- Install the wheel in a clean environment outside the source tree and run tests with standard plugin discovery (Tasks 2 and 5).

---

## File layout

| Location | Responsibility |
| --- | --- |
| `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `.cargo/config.toml` | Workspace, pinned toolchain, and Rust development settings |
| `crates/pytest-allpair-core/src/lib.rs` | Validate candidate indices, search under constraints, and select covering rows |
| `crates/pytest-allpair-python/src/lib.rs` | Expose the Rust generator through PyO3 and translate failures into Python exceptions |
| `crates/pytest-allpair-python/python/pytest_allpair/` | pytest hooks and model construction in `plugin.py`, with pytest version differences handled by `_pytest_compat.py` |
| `pyproject.toml`, `uv.lock`, `prek.toml` | maturin and the pytest entry point, Python development environment, and static checks |
| `formal/coverage_oracle.rs`, `fuzz/`, `formal/quint/` | Independent exhaustive oracle, fuzz tests, and pruning model checks |
| `tests/`, `tools/`, `infra/`, `.github/workflows/` | pytest integration tests, distribution verification, and CI configuration |
| `README.md`, `LICENSE`, `docs/user/`, `docs/development/` | Installation and usage, license, development, and verification |

### Task 1. Constraint-aware coverage and exhaustive oracle

**Files**

Create `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`, `.cargo/config.toml`, `crates/pytest-allpair-core/{Cargo.toml,src/lib.rs,tests/coverage.rs}`, and `formal/coverage_oracle.rs`.

**Interfaces**

The public function and types below define the generator contract. Each term in a forbidden rule pairs a factor index with a set of candidate indices. A rule excludes a complete case that matches every term. The function `check(level_counts: &[usize], order: usize, forbidden: &[ForbiddenRule], result: &Result<Vec<Vec<usize>>, GenerateError>) -> (usize, usize)` in `formal/coverage_oracle.rs` fails on a mismatch and returns the counts of valid rows and required interactions.

```rust
pub struct ForbiddenRule {
    pub terms: Vec<(usize, Vec<usize>)>,
}
pub enum GenerateError {
    InvalidModel(String),
    NoValidCases,
}
pub fn generate(
    level_counts: &[usize],
    order: usize,
    forbidden: &[ForbiddenRule],
) -> Result<Vec<Vec<usize>>, GenerateError>;
```

- [ ] Create the workspace and tests. Use Cargo resolver `3`, pin Rust to `1.100.0` as in hoimin, and keep `fuzz/` in a separate workspace. The oracle enumerates small Cartesian products to check row validity and coverage. Load the oracle from `coverage.rs` with `#[path]`.
- [ ] Write the regression test `covers_feasible_pairs` first. With counts `[2, 2, 2]`, order 2, and forbidden rule `[(0,[0]), (1,[0])]`, verify that the oracle finds 6 valid rows and 11 required interactions, and that every generated row is valid.
- [ ] In `multiple_rules_block_one_projection`, use separate rules to forbid `(A,B,C)=(0,0,0),(0,0,1)` in the same model and verify that 11 pairs remain required. In `supports_order_one_three_and_full`, check orders 1, 3, and 4 against the oracle for `[2,3,2,2]`. In `rejects_invalid_or_unsatisfiable_models`, expect `InvalidModel` for order 0 or an order above the factor count and `NoValidCases` when a constraint excludes all levels.
- [ ] Run `cargo test -p pytest-allpair-core --test coverage` and confirm that it fails because the generator is missing.
- [ ] Implement `generate`. Enumerate interactions of the requested order and use each uncovered interaction as the starting point for a depth-first search for a valid row. Order candidates by the number of interactions they can add to coverage and by factor and level position. Prune a branch once every term of a forbidden rule is assigned and matches. If the search exhausts the candidates without a valid row, remove the interaction from the coverage requirements. Record the interactions covered by each completed row and proceed to the next uncovered interaction. When the order equals the factor count, enumerate the valid complete rows in order.
- [ ] Add `deterministic_on_large_cartesian_space`. Run the generator twice at order 2 with 20 binary factors. Compare the results, confirm coverage of all 760 pairs, and check that the generator returns at most 760 rows. Build the expected set from pairs of factors and their values.
- [ ] Run `cargo fmt --all --check`, `cargo test --locked -p pytest-allpair-core`, and `cargo clippy --locked -p pytest-allpair-core --all-targets -- -D warnings`. Commit the generator and oracle when the checks pass.

### Task 2. Installable Python package and Rust bridge

**Files**

Modify `Cargo.toml`, `Cargo.lock`, and `.gitignore`. Create `pyproject.toml`, `uv.lock`, `LICENSE`, `crates/pytest-allpair-python/{Cargo.toml,src/lib.rs,python/pytest_allpair/__init__.py,python/pytest_allpair/plugin.py}`, and `tests/test_native.py`.

**Interfaces**

`pytest_allpair._native.generate(level_counts: list[int], order: int, forbidden: list[list[tuple[int, list[int]]]]) -> list[list[int]]` calls the generator from Task 1. Invalid and unsatisfiable Rust models become Python `ValueError` exceptions.

- [ ] Add `test_native_solves_two_by_two`. Check that `_native.generate([2, 2], 2, [])` returns all four rows and that `_native.generate([2], 1, [[(0, [0, 1])]])` raises `ValueError`. Build the mixed package with an empty `_native` module first. Run `uv run --locked pytest -q tests/test_native.py` and confirm that it fails because `generate` is missing.
- [ ] Use `pytest-allpair` as the distribution name and `pytest_allpair._native` as the extension module name. Use PyO3 to convert the Task 1 input and output types. Set maturin's `manifest-path` to the Python crate's manifest and `python-source` to its `python/` directory. Set `allpair = "pytest_allpair.plugin"` under `[project.entry-points.pytest11]`. Set the Python requirement to `>=3.11,<3.16` and the pytest requirement to `>=8.4,<10`. [maturin project layout](https://www.maturin.rs/project_layout.html) · [PyO3 ABI](https://docs.rs/crate/pyo3/0.30.1/source/guide/src/features.md)
- [ ] Add the MIT `LICENSE` and distribution metadata. Run `uv lock` and `uv sync --locked`. Commit when `uv run --locked pytest -q tests/test_native.py` passes.

### Task 3. pytest markers, values, IDs, and fixtures

**Files**

Modify `crates/pytest-allpair-python/python/pytest_allpair/plugin.py`. Create `crates/pytest-allpair-python/python/pytest_allpair/_pytest_compat.py` and `tests/test_plugin.py`.

**Interfaces**

Implement `pytest_configure(config: pytest.Config) -> None` and `pytest_generate_tests(metafunc: pytest.Metafunc) -> None`. The compatibility module's `parameter_rows(argnames, argvalues, ids, *, metafunc)` returns the argument names for a factor and each level's tuple of values, marks, and resolved ID. Keep the list of candidate rows empty when a factor has no candidates. Pass the numeric model to the native function from Task 2.

- [ ] Declare `pytest_plugins = ("pytester",)` in `tests/test_plugin.py`. Use `pytester` in `test_pairwise_cases` to check that the default order covers all four pairs of values for each pair of factors in a model with three binary factors. In `test_order_and_exclusions`, use four binary factors with `order=3` and `exclude=[{"a": 0, "b": 0}]`. Check that every row is valid and that the covered triples match the triples in all valid rows.
- [ ] In `test_grouped_values_and_ids`, check that `(input, expected)` values stay paired. Test sequence and callable forms of `ids`, explicit `pytest.param` IDs and `xfail` marks, and `pytest.HIDDEN_PARAM`. In `test_joined_ids_are_unique`, use `a-b` and `a` as IDs for one factor and `c` and `b-c` for the other. Verify that all four node IDs remain distinct after joining the fragments.
- [ ] In `test_exclusions_match_every_equal_level`, provide two equal lists and a different list. Verify that both equal candidates retain their explicit IDs without an exclusion and that the exclusion removes both. In `test_empty_factor_follows_pytest_ini`, exercise the default skip behavior and `empty_parameter_set_mark=fail_at_collect`.
- [ ] In `test_fixtures_and_standard_parametrize`, check that the standard marker and a separately named `fixture(params=...)` contribute to the Cartesian product. Check that the fixture declared with `indirect` receives `request.param`. In `test_duplicate_indirect_fixture_parameter`, specify the same argument in `fixture(params=...)` and a factor marker and expect a collection error. In `test_class_and_module_factors`, declare factors at both levels and check that the function's settings apply to all factors.
- [ ] Parametrize `test_invalid_declarations` to check collection errors for out-of-range orders, duplicate or misplaced configuration markers, unknown exclusion keys or values, equality comparisons with no boolean result, empty exclusion dictionaries, `order=True`, conflicting explicit scopes, scopes set on only some factors, and constraints that rule out all valid cases. Check that each error includes the test name and the cause.
- [ ] Run `uv run --locked pytest -q tests/test_plugin.py` and confirm that the relevant tests fail because the hooks are missing.
- [ ] Register and validate the markers in the hooks. Get the factor and configuration markers from `metafunc.definition.iter_markers_with_node`. Handle argument shape, candidate rows, and factor IDs in the compatibility module. Reuse pytest's `ParameterSet` and `IdMaker` there for operations outside the public API. Resolve exclusions to candidate indices without requiring Python values to be hashable.
- [ ] Assemble values, marks, and IDs from the selected rows. For an empty candidate list, call `Metafunc.parametrize(..., [])` with the original argument shape and fixture settings. For generated cases, join the visible ID fragments. Pass `pytest.HIDDEN_PARAM` for a row whose fragments are all hidden and let pytest resolve any duplicate IDs. Collect the indirect argument names across all factors and register them with the common scope in one `Metafunc.parametrize` call. [ID resolution in pytest 8.4](https://docs.pytest.org/en/8.4.x/_modules/_pytest/python.html) · [Metafunc API](https://docs.pytest.org/en/stable/reference/reference.html#pytest.Metafunc.parametrize)
- [ ] Use `pytest>=8.4,<9` and `pytest>=9,<10` for the two supported pytest series. Install each in a fresh virtual environment with `uv pip install --python <venv-python> -e . <pytest-requirement>`. Commit when `python -m pytest -q tests/test_plugin.py tests/test_native.py` passes in both environments.

### Task 4. Fuzz testing and the Quint experiment

**Files**

Create `fuzz/{Cargo.toml,Cargo.lock,.gitignore,fuzz_targets/coverage.rs}`, `formal/quint/{pruning.qnt,README.md}`, and `docs/development/guides/verification.md`. Reuse `formal/coverage_oracle.rs` from Task 1.

**Interfaces**

Convert fuzz input into a model with one to five factors, one to three levels per factor, a coverage order, and forbidden rules. Call the same `generate` function. The Quint model uses the same form of forbidden rule and represents partial assignments.

- [ ] Add `fuzz_targets/coverage.rs`. Keep its Cargo lockfile separate from the root lockfile and load `formal/coverage_oracle.rs` from the target. Run `cargo +nightly fuzz run coverage -- -runs=1000` to check row validity, complete n-way coverage, and agreement about unsatisfiable models. Convert failing inputs into concrete values that reproduce the failure in a regular Rust test.
- [ ] In `pruning.qnt`, model three binary factors, the prohibition of `A=0, B=0`, and a transition that prunes a partial assignment. Have `SoundPrune` enumerate valid complete cases and verify that no valid case extends a discarded assignment.
- [ ] Verify that `quint verify formal/quint/pruning.qnt --backend=tlc --main Pruning --invariants SoundPrune` finds no violation. Run the same command with `--main PruningMutant` and check that it finds a counterexample to pruning when only part of the forbidden rule matches. For example, `A=0` can be completed with `B=1`. [Quint CLI verification options](https://quint.sh/docs/quint#command-verify)
- [ ] Use the model input from the counterexample in a regression test against the public Rust generator. Record whether the existing oracle catches the error. If you need an ITF trace, check the same invariant with Apalache's `--out-itf` option. Record the results, the bounds of the finite model, and how its checks relate to the Rust oracle, then commit. Use the results to decide whether to add ITF traces and model-based testing to routine verification.

### Task 5. CI, wheels, and user and developer guides

**Files**

Modify `README.md` and `pyproject.toml`. Create `prek.toml`, `mkdocs.yml`, `docs/index.md`, `docs/user/guides/quickstart.md`, `docs/user/reference/markers.md`, `tools/wheel_smoke.py`, `infra/README.md`, and `.github/workflows/{ci.yml,non-linux-ci.yml,release.yml}`.

**Interfaces**

`python tools/wheel_smoke.py WHEEL_PATH` installs the wheel in a clean environment and runs pytest from a working directory outside the checkout. It checks plugin discovery, collection, and execution.

- [ ] Put an example with three binary factors in the wheel smoke test. Check both the number of passing cases and that the executed rows cover all 12 pairs. Verify that the smoke test fails with plugin auto-loading disabled and passes with standard settings.
- [ ] Document how to reproduce the Rust checks and pytest integration tests with `uv run`. In CI, test CPython 3.11, 3.12, 3.13, 3.14, and 3.15 against pytest 8.4.x and 9.x. On Linux, macOS, and Windows, smoke-test wheels built by `maturin build --release --locked`. Build Linux distribution wheels in a manylinux 2.28 environment and check the resulting manylinux tags. Separate verification and distribution jobs as in hoimin, and upload distribution builds as artifacts.
- [ ] In `infra/README.md`, record the applied GitHub rulesets and the settings for deleting merged branches, updating PR branches, and Discussions. Refer to the release branch as `pytest-allpair-release-state`. [GitHub rulesets](https://github.com/HayaoSuzuki/pytest-allpair/rules)
- [ ] In the user docs, cover installation, basic usage, `order=3` and `exclude`, standard `parametrize` alongside covering factors, empty candidate lists, and collection errors. In the developer docs, cover the reference oracle, fuzz tests, the Quint experiment, and wheel verification.
- [ ] Run `cargo fmt --all --check`, `cargo clippy --workspace --all-targets --locked -- -D warnings`, `cargo test --workspace --locked`, `uv run --locked pytest -q`, and the wheel smoke tests in the target environments. Check that the implementation meets its public contract, that the Rust core takes only the numeric model, and that generation avoids an intermediate Cartesian product. Record the verification results and commit.
