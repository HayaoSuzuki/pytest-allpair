use std::collections::BTreeSet;

use proptest::prelude::*;
use pytest_allpair_core::{ForbiddenRule, generate};

#[path = "../../../formal/coverage_oracle.rs"]
mod oracle;

#[test]
fn exhausts_all_binary_row_exclusions_and_orders() {
    let rows: [[usize; 3]; 8] =
        std::array::from_fn(|index| [index >> 2, (index >> 1) & 1, index & 1]);
    let counts = [2; 3];
    for excluded in 0..(1_usize << rows.len()) {
        let rules: Vec<_> = rows
            .iter()
            .enumerate()
            .filter(|(index, _)| excluded & (1 << index) != 0)
            .map(|(_, row)| ForbiddenRule {
                terms: row
                    .iter()
                    .enumerate()
                    .map(|(axis, &level)| (axis, vec![level]))
                    .collect(),
            })
            .collect();
        for order in 1..=counts.len() {
            let result = generate(&counts, order, &rules);
            oracle::check(&counts, order, &rules, &result);
            if let Ok(selected) = result {
                let distinct: BTreeSet<_> = selected.iter().collect();
                assert_eq!(
                    distinct.len(),
                    selected.len(),
                    "exclusions {excluded:08b}, order {order}"
                );
            }
        }
    }
}

fn models() -> impl Strategy<Value = (Vec<usize>, usize, Vec<ForbiddenRule>)> {
    prop::collection::vec(1_usize..=3, 1..=5)
        .prop_flat_map(|counts| {
            let per_factor = counts
                .iter()
                .map(|&count| prop::collection::btree_set(0..count, 0..=count))
                .collect::<Vec<_>>();
            let orders = 1..=counts.len();
            (
                Just(counts),
                orders,
                prop::collection::vec(per_factor, 0..=5),
            )
        })
        .prop_map(|(counts, order, exclusions)| {
            let rules = exclusions
                .into_iter()
                .map(|levels| {
                    levels
                        .into_iter()
                        .enumerate()
                        .filter(|(_, permitted)| !permitted.is_empty())
                        .map(|(factor, levels)| (factor, levels.into_iter().collect()))
                        .collect::<Vec<_>>()
                })
                .filter(|terms| !terms.is_empty())
                .map(|terms| ForbiddenRule { terms })
                .collect();
            (counts, order, rules)
        })
}

proptest! {
    #[test]
    fn generated_rows_cover_every_feasible_interaction((counts, order, rules) in models()) {
        let actual = generate(&counts, order, &rules);
        oracle::check(&counts, order, &rules, &actual);
    }

    #[test]
    fn reordering_equivalent_constraints_keeps_the_same_rows((counts, order, mut rules) in models()) {
        let original = generate(&counts, order, &rules);
        rules.reverse();
        for rule in &mut rules {
            rule.terms.reverse();
            for (_, levels) in &mut rule.terms {
                levels.reverse();
            }
        }
        prop_assert_eq!(generate(&counts, order, &rules), original);
    }
}
