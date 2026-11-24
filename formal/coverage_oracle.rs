use std::collections::BTreeSet;

use pytest_allpair_core::{ForbiddenRule, GenerateError};

// Intentionally enumerate the Cartesian space. Only bounded test models belong here.
pub fn check(
    level_counts: &[usize],
    order: usize,
    forbidden: &[ForbiddenRule],
    result: &Result<Vec<Vec<usize>>, GenerateError>,
) -> (usize, usize) {
    let mut legal = vec![Vec::new()];
    for &count in level_counts {
        legal = legal
            .into_iter()
            .flat_map(|row| {
                (0..count).map(move |value| {
                    let mut next = row.clone();
                    next.push(value);
                    next
                })
            })
            .collect();
    }
    legal.retain(|row| {
        !forbidden.iter().any(|rule| {
            rule.terms
                .iter()
                .all(|(axis, values)| values.contains(&row[*axis]))
        })
    });

    if legal.is_empty() {
        assert_eq!(result, &Err(GenerateError::NoValidCases));
        return (0, 0);
    }

    let actual = result.as_ref().expect("a valid completion exists");
    for row in actual {
        assert!(legal.contains(row), "invalid output row: {row:?}");
    }
    let expected = projections(&legal, order);
    assert_eq!(projections(actual, order), expected, "coverage differs");
    (legal.len(), expected.len())
}

fn projections(rows: &[Vec<usize>], order: usize) -> BTreeSet<Vec<(usize, usize)>> {
    rows.iter()
        .flat_map(|row| {
            // The oracle exercises at most five factors; a bit mask is enough here.
            (0_usize..(1 << row.len()))
                .filter(move |mask| mask.count_ones() as usize == order)
                .map(|mask| {
                    row.iter()
                        .copied()
                        .enumerate()
                        .filter(|(index, _)| mask & (1 << index) != 0)
                        .collect()
                })
        })
        .collect()
}
