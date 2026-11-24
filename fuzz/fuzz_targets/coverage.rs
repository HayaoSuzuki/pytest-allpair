#![no_main]

use arbitrary::Unstructured;
use libfuzzer_sys::fuzz_target;
use pytest_allpair_core::{ForbiddenRule, generate};

#[path = "../../formal/coverage_oracle.rs"]
mod oracle;

fn exercise(input: &mut Unstructured<'_>) -> arbitrary::Result<()> {
    let factors = input.int_in_range(1..=5)?;
    let counts: Vec<usize> = (0..factors)
        .map(|_| input.int_in_range(1..=3))
        .collect::<arbitrary::Result<_>>()?;
    let order = input.int_in_range(1..=factors)?;
    let mut rules = Vec::new();
    for _ in 0..input.int_in_range(0..=5)? {
        let mut terms = Vec::new();
        for (axis, &count) in counts.iter().enumerate() {
            let selected = input.int_in_range(0..=(1_usize << count) - 1)?;
            if selected != 0 {
                let levels = (0..count)
                    .filter(|level| selected & (1 << level) != 0)
                    .collect();
                terms.push((axis, levels));
            }
        }
        if !terms.is_empty() {
            rules.push(ForbiddenRule { terms });
        }
    }

    oracle::check(&counts, order, &rules, &generate(&counts, order, &rules));
    Ok(())
}

fuzz_target!(|data: &[u8]| {
    let _ = exercise(&mut Unstructured::new(data));
});
