use std::collections::BTreeSet;
use std::fmt::Display;
use std::str::FromStr;

use pytest_allpair_core::{ForbiddenRule, GenerateError, generate};
use serde::{Deserialize, Deserializer};

#[derive(Deserialize)]
struct CoverageTrace {
    states: Vec<CoverageState>,
}

#[derive(Deserialize)]
struct CoverageState {
    cases: Vec<Witness>,
}

#[derive(Deserialize)]
struct Witness {
    name: String,
    counts: Vec<ItfInt<usize>>,
    order: ItfInt<usize>,
    rules: Vec<Vec<Term>>,
    #[serde(rename = "legalRows")]
    legal_rows: ItfSet<Vec<ItfInt<usize>>>,
    feasible: ItfSet<Vec<ItfInt<i64>>>,
}

#[derive(Deserialize)]
struct Term {
    axis: ItfInt<usize>,
    levels: Vec<ItfInt<usize>>,
}

#[derive(Deserialize)]
#[serde(bound(deserialize = "T: FromStr, T::Err: Display"))]
struct ItfInt<T> {
    #[serde(rename = "#bigint", deserialize_with = "parse_int")]
    value: T,
}

fn parse_int<'de, D, T>(deserializer: D) -> Result<T, D::Error>
where
    D: Deserializer<'de>,
    T: FromStr,
    T::Err: Display,
{
    String::deserialize(deserializer)?
        .parse()
        .map_err(serde::de::Error::custom)
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

fn unpack_ints<T>(values: Vec<ItfInt<T>>) -> Vec<T> {
    values.into_iter().map(|integer| integer.value).collect()
}

#[test]
fn generator_matches_quint_coverage() {
    let fixture = include_str!("../../../formal/quint/coverage.itf.json");
    let trace: CoverageTrace = serde_json::from_str(fixture).expect("decode Quint coverage ITF");
    let [state] = <[_; 1]>::try_from(trace.states)
        .unwrap_or_else(|states| panic!("expected one Quint coverage state, got {}", states.len()));
    assert!(
        !state.cases.is_empty(),
        "Quint coverage trace has no witnesses"
    );
    for witness in state.cases {
        check_witness(witness);
    }
}

fn check_witness(witness: Witness) {
    let name = &witness.name;
    let counts = unpack_ints(witness.counts);
    let order = witness.order.value;
    let legal_rows = witness.legal_rows.into_rows();
    let forbidden: Vec<_> = witness
        .rules
        .into_iter()
        .map(|rule| ForbiddenRule {
            terms: rule
                .into_iter()
                .map(|term| (term.axis.value, unpack_ints(term.levels)))
                .collect(),
        })
        .collect();
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
