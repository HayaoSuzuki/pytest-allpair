use std::fmt::{Debug, Write};
use std::fs;
use std::path::Path;

use super::{ForbiddenRule, GenerateError, generate_with_observer};

const LEVEL_COUNTS: [usize; 3] = [2; 3];
const BINARY_ROWS: [[usize; 3]; 8] = [
    [0, 0, 0],
    [0, 0, 1],
    [0, 1, 0],
    [0, 1, 1],
    [1, 0, 0],
    [1, 0, 1],
    [1, 1, 0],
    [1, 1, 1],
];

#[test]
#[ignore = "exports the Rust traces consumed by Quint"]
fn export_binary_covering_traces() -> std::io::Result<()> {
    let mut out = String::from(
        "module CoveringReplayCases {\n  import CoveringReplay.* from \"../../formal/quint/replay\"\n",
    );

    for (order, expected_events) in [(1, 6), (2, 12)] {
        for mask in 0..=u8::MAX {
            write_trace_case(&mut out, order, mask, expected_events);
        }
    }
    out.push_str(
        "  run rescoringAPartialRowTest = assert(replaysUnconstrained([2, 2, 2, 2], 2, List(",
    );
    write_events(&mut out, &[2; 4], 2, &[], 24).unwrap();
    out.push_str("}\n");

    let directory = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../target/quint");
    fs::create_dir_all(&directory)?;
    fs::write(directory.join("covering_replay.qnt"), out)
}

fn write_trace_case(out: &mut String, order: usize, mask: u8, expected_events: usize) {
    let forbidden_rows = BINARY_ROWS
        .into_iter()
        .enumerate()
        .filter_map(|(bit, row)| (mask & (1 << bit) != 0).then_some(row));
    let rules: Vec<_> = forbidden_rows
        .clone()
        .map(|row| ForbiddenRule {
            terms: row
                .into_iter()
                .enumerate()
                .map(|(axis, level)| (axis, vec![level]))
                .collect(),
        })
        .collect();

    write!(
        out,
        "  run order{order}Mask{mask}Test = assert(replays({order}, "
    )
    .unwrap();
    write_set(out, forbidden_rows);
    out.push_str(", List(");

    let result = write_events(out, &LEVEL_COUNTS, order, &rules, expected_events);
    if mask == u8::MAX {
        assert_eq!(result, Err(GenerateError::NoValidCases));
    } else {
        result.unwrap();
    }
}

fn write_events(
    out: &mut String,
    counts: &[usize],
    order: usize,
    rules: &[ForbiddenRule],
    expected_events: usize,
) -> Result<Vec<Vec<usize>>, GenerateError> {
    let mut events = 0;
    let mut selected = Vec::new();
    let result = generate_with_observer(counts, order, rules, |seed, addition, cache| {
        if events != 0 {
            out.push(',');
        }
        write!(
            out,
            "\n      {{ seed: {:?}, addition: [",
            padded_row(seed, counts.len())
        )
        .unwrap();
        if let Some(row) = addition {
            selected.push(row.to_vec());
            write!(out, "{row:?}").unwrap();
        }
        out.push_str("], cache: ");
        write_set(
            out,
            cache
                .iter()
                .map(|projection| padded_row(projection, counts.len())),
        );
        out.push_str(" }");
        events += 1;
    });
    out.push_str("\n    )))\n");

    assert_eq!(
        events, expected_events,
        "{counts:?}, order {order}, exclusions {rules:?}"
    );
    match &result {
        Ok(rows) => assert_eq!(rows, &selected, "returned row order must match the trace"),
        Err(_) => assert!(selected.is_empty(), "a failed generation selected rows"),
    }
    result
}

fn padded_row(projection: &[(usize, usize)], factor_count: usize) -> Vec<isize> {
    // Padding preserves cache identity only for canonical projection keys.
    assert!(
        projection.windows(2).all(|axes| axes[0].0 < axes[1].0),
        "projection axes must be strictly increasing",
    );
    let mut row = vec![-1; factor_count];
    for &(axis, level) in projection {
        row[axis] = isize::try_from(level).unwrap();
    }
    row
}

fn write_set<T: Debug>(out: &mut String, rows: impl Iterator<Item = T>) {
    out.push_str("Set(");
    for (index, row) in rows.enumerate() {
        if index != 0 {
            out.push_str(", ");
        }
        write!(out, "{row:?}").unwrap();
    }
    out.push(')');
}

#[test]
#[should_panic(expected = "projection axes must be strictly increasing")]
fn refuses_a_reordered_projection_key() {
    let _ = padded_row(&[(1, 0), (0, 0)], 3);
}
