use std::collections::BTreeSet;

use pytest_allpair_core::{ForbiddenRule, GenerateError, generate};
use serde::Deserialize;

#[path = "support/quint_witness.rs"]
mod quint_witness;

use quint_witness::{ItfInt, WitnessModel, load_witnesses, unpack_ints};

#[derive(Deserialize)]
struct Witness {
    #[serde(flatten)]
    model: WitnessModel,
    #[serde(rename = "legalRows")]
    legal_rows: ItfSet<Vec<ItfInt<usize>>>,
    feasible: ItfSet<Vec<ItfInt<i64>>>,
}

#[derive(Deserialize)]
struct ItfSet<T> {
    #[serde(rename = "#set")]
    values: Vec<T>,
}

impl<T: Ord> ItfSet<Vec<ItfInt<T>>> {
    fn into_rows(self) -> BTreeSet<Vec<T>> {
        self.values.into_iter().map(unpack_ints).collect()
    }
}

#[test]
fn generator_matches_quint_coverage() {
    for witness in load_witnesses::<Witness>() {
        check_witness(witness);
    }
}

fn check_witness(witness: Witness) {
    let WitnessModel {
        name,
        counts,
        order,
        forbidden,
    } = witness.model;
    let legal_rows = witness.legal_rows.into_rows();
    let result = generate(&counts, order, &forbidden);
    let rows = if legal_rows.is_empty() {
        assert_eq!(result, Err(GenerateError::NoValidCases), "{name}");
        Vec::new()
    } else {
        result.unwrap_or_else(|error| panic!("{name}: {error}"))
    };

    let row_count = rows.len();
    let rows: BTreeSet<_> = rows.into_iter().collect();
    assert_eq!(rows.len(), row_count, "{name}: duplicate rows");
    for row in &rows {
        assert!(legal_rows.contains(row), "{name}: illegal row {row:?}");
    }

    // The bounded Quint witnesses have only a few factors, so enumerate axis subsets by mask.
    let axis_masks =
        (0_usize..(1 << counts.len())).filter(|mask| mask.count_ones() as usize == order);
    let mut covered = BTreeSet::new();
    for row in &rows {
        for mask in axis_masks.clone() {
            let projection: Vec<_> = row
                .iter()
                .enumerate()
                .map(|(axis, &level)| {
                    if mask & (1 << axis) == 0 {
                        -1
                    } else {
                        i64::try_from(level).expect("Quint witness level fits in i64")
                    }
                })
                .collect();
            covered.insert(projection);
        }
    }
    assert_eq!(
        covered,
        witness.feasible.into_rows(),
        "{name}: feasible projections"
    );

    if order == counts.len() {
        assert_eq!(rows, legal_rows, "{name}: full-order rows");
    }
}
