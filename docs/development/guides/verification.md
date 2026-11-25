# Verifying coverage

## Python static checks

CI checks the package, tests, and verification tools using Python 3.11 syntax and types.

```sh
uv sync --locked
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync ty check
```

## Coverage oracle

The Rust generator takes a candidate count per factor, a coverage order, and exclusion rules. It returns the indices of the selected candidates. For small models, enumerate the valid complete cases and compare the n-way interactions they contain with those in the generated output. The reference oracle in `formal/coverage_oracle.rs` uses exhaustive enumeration to compute the expected result independently of the generator's search and pruning.

## Property tests and randomized test order

Rust's proptest varies the number of factors, their levels, the coverage order, and the exclusion rules, then compares the sets of interactions. It also checks that reordering equivalent exclusion rules preserves the generated rows and their order. Python's Hypothesis generates models with multiple arguments in one factor and compares the cases collected by pytest with the valid cases derived from comparisons of the original values.

```sh
cargo test --workspace --locked
PROPTEST_CASES=1024 PROPTEST_RNG_SEED=812 cargo test --locked -p pytest-allpair-core --test coverage_properties
uv run --locked pytest --hypothesis-show-statistics
```

CI runs Python tests in an order chosen by pytest-randomly and also runs the Rust tests with shuffling on a pinned nightly toolchain. To reproduce a failure, use the seed from the log. Rust prints a seed for each test binary.

```sh
uv run --locked pytest --randomly-seed=812
cargo +nightly-2026-11-23 test --workspace --locked -- -Z unstable-options --shuffle
cargo +nightly-2026-11-23 test --locked -p pytest-allpair-core --test coverage_properties -- -Z unstable-options --shuffle-seed 812
```

## Coverage-guided fuzzing

The libFuzzer target compares generated results with exhaustive enumeration for models with at most five factors and three levels per factor. The `fuzz/` workspace has a separate Cargo lockfile. Pull request CI runs 1,000 iterations. The scheduled run lasts 60 seconds, and manual runs offer 30-, 60-, and 300-second budgets. CI reuses the discovered corpus and saves logs and failure inputs as artifacts.

```sh
cargo install cargo-fuzz --version 0.13.2 --locked
cargo +nightly-2026-11-23 fuzz run coverage -- -runs=1000 -seed=812
```

## Quint model checking

Quint and TLC check depth-first completion search and interaction coverage. The example catalog includes compound exclusions, full order, and a model with no legal rows. A separate bounded model covers all 256 legal-row sets of three binary factors and checks the incremental coverage cache and termination. A Rust test exercises all 768 combinations of exclusion set and coverage order against the exhaustive oracle. Quint also replays 512 Rust executions and checks candidate order, row additions, and the cache at each step using the model's transition definitions. The depth-first replay checks 276 Rust executions from that catalog, including branch pruning, visit order, and the visitor's return. The Rust ITF output test uses the legal rows and feasible interactions that Quint exports for the example catalog. TLC requires Java. Quint and Python regenerate the trace. The Rust test reads the checked-in trace. [Quint models and trace generation](https://github.com/HayaoSuzuki/pytest-allpair/blob/main/formal/quint/README.md)

```sh
cargo test --locked -p pytest-allpair-core --test quint_coverage
cargo test --locked -p pytest-allpair-core --test coverage_properties \
    exhausts_all_binary_row_exclusions_and_orders
```
