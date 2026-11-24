use proptest::prelude::*;
use pytest_allpair_core::{ForbiddenRule, generate};

#[path = "../../../formal/coverage_oracle.rs"]
mod oracle;

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
