use std::fmt::{Debug, Write};
use std::fs;
use std::ops::ControlFlow;
use std::path::Path;

use super::quint_witness::{WitnessModel, load_witnesses};
use super::{Model, digit_vectors};

#[test]
#[ignore = "exports the Rust DFS traces consumed by Quint"]
fn export_depth_first_traces() -> std::io::Result<()> {
    let mut out = String::from(
        "module DepthFirstReplayCases {\n  import DepthFirstReplay.* from \"../../formal/quint/depth_first_replay\"\n",
    );

    let mut inputs = String::new();
    for (case_index, witness) in load_witnesses::<WitnessModel>().into_iter().enumerate() {
        let model = Model::new(&witness.counts, witness.order, &witness.forbidden)
            .unwrap_or_else(|error| panic!("{}: {error}", witness.name));
        let seed_counts: Vec<_> = witness.counts.iter().map(|count| count + 1).collect();
        for (seed_index, digits) in digit_vectors(&seed_counts).enumerate() {
            let seed: Vec<_> = digits
                .into_iter()
                .map(|digit| digit.checked_sub(1))
                .collect();
            for stop_at_first in [false, true] {
                let encoded_seed = write_trace_case(
                    &mut out,
                    &model,
                    case_index,
                    seed_index,
                    &seed,
                    stop_at_first,
                );
                writeln!(
                    inputs,
                    "    ({case_index}, {encoded_seed:?}, {stop_at_first}),"
                )
                .unwrap();
            }
        }
    }
    out.push_str("  run coversCatalogTest = assert(coversCatalog(List(\n");
    out.push_str(&inputs);
    out.push_str("  )))\n}\n");

    let directory = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../target/quint");
    fs::create_dir_all(&directory)?;
    fs::write(directory.join("depth_first_replay.qnt"), out)
}

fn write_trace_case(
    out: &mut String,
    model: &Model<'_>,
    case_index: usize,
    seed_index: usize,
    seed: &[Option<usize>],
    stop_at_first: bool,
) -> Vec<i64> {
    let mode = if stop_at_first { "First" } else { "All" };
    let encoded_seed = padded_row(seed);
    write!(
        out,
        "  run case{case_index}Seed{seed_index}{mode}Test = assert(replaysSearch({case_index}, {encoded_seed:?}, {stop_at_first}, {{ events: List("
    )
    .unwrap();

    let mut yielded = Vec::new();
    let mut events = 0;
    let result = model.visit_completions(
        &mut seed.to_vec(),
        |_, _, level| if stop_at_first { level } else { 0 },
        |row| {
            if stop_at_first {
                yielded.push(row.clone());
                ControlFlow::Break(row)
            } else {
                yielded.push(row);
                ControlFlow::Continue(())
            }
        },
        |row, kind| {
            if events != 0 {
                out.push(',');
            }
            write!(
                out,
                "\n      {{ node: {:?}, kind: {kind:?} }}",
                padded_row(row)
            )
            .unwrap();
            events += 1;
        },
    );

    assert!(
        events != 0,
        "missing root event for case {case_index}, seed {encoded_seed:?}, mode {mode}"
    );
    out.push_str("\n    ), yielded: ");
    write_list(out, &yielded);
    out.push_str(", returned: ");
    let returned = match &result {
        ControlFlow::Break(row) => std::slice::from_ref(row),
        ControlFlow::Continue(()) => &[],
    };
    write_list(out, returned);
    out.push_str(" }))\n");
    encoded_seed
}

fn padded_row(row: &[Option<usize>]) -> Vec<i64> {
    row.iter()
        .map(|level| level.map_or(-1, |value| i64::try_from(value).unwrap()))
        .collect()
}

fn write_list<T: Debug>(out: &mut String, rows: &[T]) {
    out.push_str("List(");
    for (index, row) in rows.iter().enumerate() {
        if index != 0 {
            out.push_str(", ");
        }
        write!(out, "{row:?}").unwrap();
    }
    out.push(')');
}
