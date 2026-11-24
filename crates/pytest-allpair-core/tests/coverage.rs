use std::collections::BTreeSet;

use pytest_allpair_core::{ForbiddenRule, GenerateError, generate};

#[path = "../../../formal/coverage_oracle.rs"]
mod oracle;

#[test]
fn covers_feasible_pairs() {
    let forbidden = [ForbiddenRule {
        terms: vec![(0, vec![0]), (1, vec![0])],
    }];
    let result = generate(&[2, 2, 2], 2, &forbidden);
    assert_eq!(oracle::check(&[2, 2, 2], 2, &forbidden, &result), (6, 11));
}

#[test]
fn multiple_rules_block_one_projection() {
    let forbidden = [0, 1].map(|c| ForbiddenRule {
        terms: vec![(0, vec![0]), (1, vec![0]), (2, vec![c])],
    });
    let result = generate(&[2, 2, 2], 2, &forbidden);
    assert_eq!(oracle::check(&[2, 2, 2], 2, &forbidden, &result), (6, 11));
}

#[test]
fn supports_order_one_three_and_full() {
    let counts = [2, 3, 2, 2];
    let forbidden = [ForbiddenRule {
        terms: vec![(1, vec![0, 2]), (3, vec![0])],
    }];
    for order in [1, 3, 4] {
        oracle::check(
            &counts,
            order,
            &forbidden,
            &generate(&counts, order, &forbidden),
        );
    }
}

#[test]
fn rejects_invalid_or_unsatisfiable_models() {
    for result in [
        generate(&[], 1, &[]),
        generate(&[0, 2], 1, &[]),
        generate(&[2, 2], 0, &[]),
        generate(&[2, 2], 3, &[]),
        generate(
            &[2, 2],
            2,
            &[ForbiddenRule {
                terms: vec![(0, vec![2])],
            }],
        ),
        generate(
            &[2, 2],
            2,
            &[ForbiddenRule {
                terms: vec![(0, vec![0]), (0, vec![1])],
            }],
        ),
    ] {
        assert!(matches!(result, Err(GenerateError::InvalidModel(_))));
    }

    let forbidden = [ForbiddenRule {
        terms: vec![(0, vec![0, 1])],
    }];
    assert_eq!(
        generate(&[2, 2], 2, &forbidden),
        Err(GenerateError::NoValidCases)
    );
}

#[test]
fn deterministic_on_large_cartesian_space() {
    let counts = [2; 20];
    let rows = generate(&counts, 2, &[]).unwrap();
    assert_eq!(generate(&counts, 2, &[]).unwrap(), rows);
    assert!(rows.len() <= 760);
    let pairs: BTreeSet<_> = rows
        .iter()
        .flat_map(|row| {
            assert_eq!(row.len(), 20);
            assert!(row.iter().all(|&level| level < 2));
            (0..20).flat_map(move |a| (a + 1..20).map(move |b| (a, row[a], b, row[b])))
        })
        .collect();
    assert_eq!(pairs.len(), 760);
}
