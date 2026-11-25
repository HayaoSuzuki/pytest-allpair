//! Model-based checks against the public Rust generator.

#[cfg(test)]
mod tests {
    use std::collections::BTreeSet;

    use anyhow::Context;
    use proptest::prelude::*;
    use pytest_allpair_core::{ForbiddenRule, GenerateError, generate};
    use quint_connect::runner::{self, RunConfig};
    use quint_connect::{Config, Driver, Result, State, Step, switch};
    use serde::Deserialize;

    #[derive(Deserialize)]
    struct Scenario {
        name: String,
        counts: Vec<usize>,
        order: usize,
        rules: Vec<Vec<Term>>,
    }

    #[derive(Deserialize)]
    struct Term {
        axis: usize,
        levels: Vec<usize>,
    }

    impl Scenario {
        fn is_legal(&self, row: &[usize]) -> bool {
            row.len() == self.counts.len()
                && row
                    .iter()
                    .zip(&self.counts)
                    .all(|(level, count)| level < count)
                && !self.rules.iter().any(|rule| {
                    rule.iter()
                        .all(|term| term.levels.contains(&row[term.axis]))
                })
        }
    }

    #[derive(Clone, Copy, Default)]
    struct RuleEncoding {
        extra_copies: usize,
        reverse: bool,
    }

    impl RuleEncoding {
        fn encode(self, scenario: &Scenario) -> Vec<ForbiddenRule> {
            let mut rules: Vec<_> = (0..=self.extra_copies)
                .flat_map(|_| &scenario.rules)
                .map(|terms| ForbiddenRule {
                    terms: terms
                        .iter()
                        .map(|term| (term.axis, term.levels.clone()))
                        .collect(),
                })
                .collect();
            if self.reverse {
                rules.reverse();
                for rule in &mut rules {
                    rule.terms.reverse();
                    for (_, levels) in &mut rule.terms {
                        levels.reverse();
                    }
                }
            }
            rules
        }
    }

    #[derive(Clone, Copy)]
    enum GeneratorOrder {
        Requested,
        Lowered,
    }

    #[derive(Clone, Debug, Deserialize, PartialEq, Eq)]
    struct Observation {
        no_valid_cases: bool,
        legal_unique_rows: bool,
        covered: BTreeSet<Vec<i64>>,
    }

    struct CoverageDriver {
        encoding: RuleEncoding,
        order: GeneratorOrder,
        observed: Option<Observation>,
    }

    impl CoverageDriver {
        fn evaluate(&mut self, scenario: Scenario) -> Result {
            let order = match self.order {
                GeneratorOrder::Requested => scenario.order,
                GeneratorOrder::Lowered => scenario.order.saturating_sub(1).max(1),
            };
            let rules = self.encoding.encode(&scenario);
            let observation = match generate(&scenario.counts, order, &rules) {
                Ok(rows) => observe_rows(&scenario, &rows),
                Err(GenerateError::NoValidCases) => Observation {
                    no_valid_cases: true,
                    legal_unique_rows: true,
                    covered: BTreeSet::new(),
                },
                Err(error) => return Err(error).context(scenario.name),
            };
            self.observed = Some(observation);
            Ok(())
        }
    }

    impl State<CoverageDriver> for Observation {
        fn from_driver(driver: &CoverageDriver) -> Result<Self> {
            driver
                .observed
                .clone()
                .context("no generator result for this step")
        }
    }

    impl Driver for CoverageDriver {
        type State = Observation;

        fn config() -> Config {
            Config {
                state: &["observed"],
                ..Config::default()
            }
        }

        fn step(&mut self, step: &Step) -> Result {
            switch!(step {
                init(scenario) => self.evaluate(scenario)?,
                sampleCatalog(scenario) => self.evaluate(scenario)?,
                sampleBinary(scenario) => self.evaluate(scenario)?,
            })
        }
    }

    fn observe_rows(scenario: &Scenario, rows: &[Vec<usize>]) -> Observation {
        let mut legal = BTreeSet::new();
        for row in rows {
            if scenario.is_legal(row) {
                legal.insert(row);
            }
        }

        // The fixture families have at most four factors.
        let masks = (0_usize..(1 << scenario.counts.len()))
            .filter(|mask| mask.count_ones() as usize == scenario.order);
        let mut covered = BTreeSet::new();
        for row in &legal {
            for mask in masks.clone() {
                let projection = row.iter().enumerate().map(|(axis, &level)| {
                    if mask & (1 << axis) == 0 {
                        -1
                    } else {
                        i64::try_from(level).expect("candidate level fits into ITF integer")
                    }
                });
                covered.insert(projection.collect());
            }
        }

        Observation {
            no_valid_cases: false,
            legal_unique_rows: legal.len() == rows.len(),
            covered,
        }
    }

    fn run(seed: u32, encoding: RuleEncoding, order: GeneratorOrder) -> Result {
        runner::run_test(
            CoverageDriver {
                encoding,
                order,
                observed: None,
            },
            runner::Config {
                test_name: format!("covering array seed {seed}"),
                gen_config: RunConfig {
                    spec: format!("{}/../model_based.qnt", env!("CARGO_MANIFEST_DIR")),
                    main: Some("ConnectCoverage".into()),
                    init: None,
                    step: None,
                    max_samples: Some(4),
                    max_steps: Some(4),
                    seed: seed.to_string(),
                },
            },
        )
    }

    #[test]
    fn fixed_quint_traces_match_the_generator() -> Result {
        run(42, RuleEncoding::default(), GeneratorOrder::Requested)
    }

    #[test]
    fn quint_trace_detects_lowered_coverage_order() {
        let error = run(42, RuleEncoding::default(), GeneratorOrder::Lowered)
            .expect_err("the three-way model must reject a missing triple");
        assert!(
            error.to_string().contains("State invariant failed"),
            "{error:#}",
        );
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(8))]

        #[test]
        fn generated_quint_traces_match_equivalent_rule_encodings(
            seed in any::<u32>(),
            extra_copies in 0_usize..=3,
            reverse in any::<bool>(),
        ) {
            let encoding = RuleEncoding { extra_copies, reverse };
            let result = run(seed, encoding, GeneratorOrder::Requested);
            prop_assert!(result.is_ok(), "{result:#?}");
        }
    }
}
