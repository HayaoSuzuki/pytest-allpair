use std::fmt::Display;
use std::str::FromStr;

use serde::de::DeserializeOwned;
use serde::{Deserialize, Deserializer};

use super::ForbiddenRule;

#[derive(Deserialize)]
struct CoverageTrace<T> {
    states: Vec<CoverageState<T>>,
}

#[derive(Deserialize)]
struct CoverageState<T> {
    cases: Vec<T>,
}

#[derive(Deserialize)]
pub(crate) struct WitnessModel {
    pub(crate) name: String,
    #[serde(deserialize_with = "deserialize_levels")]
    pub(crate) counts: Vec<usize>,
    #[serde(deserialize_with = "deserialize_usize")]
    pub(crate) order: usize,
    #[serde(rename = "rules", deserialize_with = "deserialize_rules")]
    pub(crate) forbidden: Vec<ForbiddenRule>,
}

#[derive(Deserialize)]
struct Term {
    #[serde(deserialize_with = "deserialize_usize")]
    axis: usize,
    #[serde(deserialize_with = "deserialize_levels")]
    levels: Vec<usize>,
}

#[derive(Deserialize)]
#[serde(bound(deserialize = "T: FromStr, T::Err: Display"))]
pub(crate) struct ItfInt<T> {
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

fn deserialize_usize<'de, D: Deserializer<'de>>(deserializer: D) -> Result<usize, D::Error> {
    Ok(ItfInt::deserialize(deserializer)?.value)
}

fn deserialize_levels<'de, D: Deserializer<'de>>(deserializer: D) -> Result<Vec<usize>, D::Error> {
    Vec::deserialize(deserializer).map(unpack_ints)
}

fn deserialize_rules<'de, D: Deserializer<'de>>(
    deserializer: D,
) -> Result<Vec<ForbiddenRule>, D::Error> {
    let rules = Vec::<Vec<Term>>::deserialize(deserializer)?;
    Ok(rules
        .into_iter()
        .map(|rule| ForbiddenRule {
            terms: rule
                .into_iter()
                .map(|term| (term.axis, term.levels))
                .collect(),
        })
        .collect())
}

pub(crate) fn unpack_ints<T>(values: Vec<ItfInt<T>>) -> Vec<T> {
    values.into_iter().map(|integer| integer.value).collect()
}

pub(crate) fn load_witnesses<T: DeserializeOwned>() -> Vec<T> {
    let fixture = include_str!("../../../../formal/quint/coverage.itf.json");
    let trace: CoverageTrace<T> = serde_json::from_str(fixture).expect("decode Quint coverage ITF");
    let [state] = <[_; 1]>::try_from(trace.states)
        .unwrap_or_else(|states| panic!("expected one Quint coverage state, got {}", states.len()));
    assert!(
        !state.cases.is_empty(),
        "Quint coverage trace has no witnesses"
    );
    state.cases
}
