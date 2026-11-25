//! Deterministic covering arrays over numbered levels.
//!
//! The generator depends only on its inputs, so callers can use the same search
//! from pytest, a standalone application, or a test oracle.

use std::collections::BTreeSet;
use std::convert::Infallible;
use std::fmt;
use std::ops::ControlFlow;

/// A conjunction of factor/level-set matches that excludes a complete row.
#[derive(Debug)]
pub struct ForbiddenRule {
    /// Each factor occurs at most once. Both the factor and level numbers are zero-based.
    pub terms: Vec<(usize, Vec<usize>)>,
}

/// A failure to describe or satisfy the requested coverage model.
#[derive(Debug, PartialEq, Eq)]
pub enum GenerateError {
    InvalidModel(String),
    NoValidCases,
}

impl fmt::Display for GenerateError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidModel(message) => formatter.write_str(message),
            Self::NoValidCases => formatter.write_str("no valid cases satisfy the exclusions"),
        }
    }
}

impl std::error::Error for GenerateError {}

type Projection = Vec<(usize, usize)>;

/// Return legal rows covering every interaction with a legal completion.
///
/// Rows contain one level number per factor, in input order. Output order is
/// deterministic. With full order, the result contains every legal row.
pub fn generate(
    level_counts: &[usize],
    order: usize,
    forbidden: &[ForbiddenRule],
) -> Result<Vec<Vec<usize>>, GenerateError> {
    generate_with_observer(level_counts, order, forbidden, |_, _, _| {})
}

// The observer borrows the cache and any row appended after each partial-order seed.
fn generate_with_observer(
    level_counts: &[usize],
    order: usize,
    forbidden: &[ForbiddenRule],
    mut observe: impl FnMut(&Projection, Option<&[usize]>, &BTreeSet<Projection>),
) -> Result<Vec<Vec<usize>>, GenerateError> {
    let model = Model::new(level_counts, order, forbidden)?;
    let mut rows = Vec::new();

    if order == level_counts.len() {
        let _ = model.visit_completions(
            &mut vec![None; level_counts.len()],
            |_, _, _| 0,
            |row| {
                rows.push(row);
                ControlFlow::<Infallible>::Continue(())
            },
            |_, _| {},
        );
    } else {
        let mut covered = BTreeSet::new();
        for axes in combinations(level_counts.len(), order) {
            let counts: Vec<_> = axes.iter().map(|&axis| level_counts[axis]).collect();
            for levels in digit_vectors(&counts) {
                let seed: Projection = axes.iter().copied().zip(levels).collect();
                if covered.contains(&seed) {
                    observe(&seed, None, &covered);
                    continue;
                }

                // A seed is infeasible only after searching all its completions.
                let mut partial = vec![None; level_counts.len()];
                for &(axis, level) in &seed {
                    partial[axis] = Some(level);
                }
                let completion = model.visit_completions(
                    &mut partial,
                    |row, axis, level| coverage_gain(row, axis, level, order, &covered),
                    ControlFlow::Break,
                    |_, _| {},
                );
                let addition =
                    match completion {
                        ControlFlow::Break(row) => {
                            covered.extend(combinations(level_counts.len(), order).map(|axes| {
                                axes.into_iter().map(|axis| (axis, row[axis])).collect()
                            }));
                            rows.push(row);
                            rows.last().map(Vec::as_slice)
                        }
                        ControlFlow::Continue(()) => None,
                    };
                observe(&seed, addition, &covered);
            }
        }
    }

    if rows.is_empty() {
        Err(GenerateError::NoValidCases)
    } else {
        Ok(rows)
    }
}

#[cfg_attr(test, derive(Debug))]
enum SearchEventKind {
    Expanded,
    Pruned,
    Found,
}

struct Model<'a> {
    level_counts: &'a [usize],
    forbidden: &'a [ForbiddenRule],
}

impl<'a> Model<'a> {
    fn new(
        level_counts: &'a [usize],
        order: usize,
        forbidden: &'a [ForbiddenRule],
    ) -> Result<Self, GenerateError> {
        let invalid = |message: &str| GenerateError::InvalidModel(message.to_owned());
        if order == 0 || order > level_counts.len() {
            return Err(invalid("order must be between 1 and the number of factors"));
        }
        if level_counts.contains(&0) {
            return Err(invalid("each factor must have at least one level"));
        }

        for rule in forbidden {
            if rule.terms.is_empty() {
                return Err(invalid("an exclusion must specify at least one factor"));
            }
            let mut axes = BTreeSet::new();
            for (axis, levels) in &rule.terms {
                let Some(&count) = level_counts.get(*axis) else {
                    return Err(invalid("an exclusion refers to an unknown factor"));
                };
                if !axes.insert(*axis) {
                    return Err(invalid("an exclusion repeats a factor"));
                }
                if levels.is_empty() || levels.iter().any(|&level| level >= count) {
                    return Err(invalid("an exclusion must specify existing levels"));
                }
            }
        }
        Ok(Self {
            level_counts,
            forbidden,
        })
    }

    fn excludes(&self, row: &[Option<usize>]) -> bool {
        self.forbidden.iter().any(|rule| {
            rule.terms
                .iter()
                .all(|(axis, levels)| row[*axis].is_some_and(|level| levels.contains(&level)))
        })
    }

    /// Visit legal completions in score order. A break returns the visitor's value.
    /// The observer borrows the current row at the seed and each candidate decision.
    /// The stack holds choices only for the unresolved suffix of the current path.
    fn visit_completions<B>(
        &self,
        row: &mut [Option<usize>],
        score: impl Fn(&[Option<usize>], usize, usize) -> usize,
        mut visit: impl FnMut(Vec<usize>) -> ControlFlow<B>,
        mut observe: impl FnMut(&[Option<usize>], SearchEventKind),
    ) -> ControlFlow<B> {
        if self.excludes(row) {
            observe(row, SearchEventKind::Pruned);
            return ControlFlow::Continue(());
        }
        let gaps: Vec<_> = (0..row.len()).filter(|&axis| row[axis].is_none()).collect();
        let Some(&first) = gaps.first() else {
            observe(row, SearchEventKind::Found);
            return visit(complete(row));
        };
        observe(row, SearchEventKind::Expanded);
        let rank = |row: &[Option<usize>], axis: usize| {
            let mut candidates: Vec<_> = (0..self.level_counts[axis])
                .map(|level| (std::cmp::Reverse(score(row, axis, level)), level))
                .collect();
            candidates.sort_unstable();
            candidates.into_iter()
        };

        let mut stack = vec![rank(row, first)];
        while !stack.is_empty() {
            let depth = stack.len() - 1;
            let axis = gaps[depth];
            match stack[depth].next() {
                Some((_, level)) => {
                    row[axis] = Some(level);
                    if self.excludes(row) {
                        observe(row, SearchEventKind::Pruned);
                        continue;
                    }
                    match gaps.get(depth + 1) {
                        Some(&next) => {
                            observe(row, SearchEventKind::Expanded);
                            stack.push(rank(row, next));
                        }
                        None => {
                            observe(row, SearchEventKind::Found);
                            visit(complete(row))?;
                        }
                    }
                }
                None => {
                    row[axis] = None;
                    stack.pop();
                }
            }
        }
        ControlFlow::Continue(())
    }
}

fn coverage_gain(
    row: &[Option<usize>],
    axis: usize,
    level: usize,
    order: usize,
    covered: &BTreeSet<Projection>,
) -> usize {
    let known: Projection = row
        .iter()
        .enumerate()
        .filter_map(|(axis, level)| level.map(|level| (axis, level)))
        .collect();
    combinations(known.len(), order - 1)
        .filter(|others| {
            let mut projection: Projection = others.iter().map(|&index| known[index]).collect();
            let insert_at = projection.partition_point(|&(other_axis, _)| other_axis < axis);
            projection.insert(insert_at, (axis, level));
            !covered.contains(&projection)
        })
        .count()
}

fn complete(row: &[Option<usize>]) -> Vec<usize> {
    row.iter()
        .map(|level| level.expect("complete search row"))
        .collect()
}

fn combinations(size: usize, order: usize) -> impl Iterator<Item = Vec<usize>> {
    let mut next = (order <= size).then(|| (0..order).collect::<Vec<_>>());
    std::iter::from_fn(move || {
        let current = next.take()?;
        if let Some(index) = (0..order).rfind(|&index| current[index] < size - order + index) {
            let mut following = current.clone();
            following[index] += 1;
            for pos in index + 1..order {
                following[pos] = following[pos - 1] + 1;
            }
            next = Some(following);
        }
        Some(current)
    })
}

fn digit_vectors(counts: &[usize]) -> impl Iterator<Item = Vec<usize>> + '_ {
    let mut next = Some(vec![0; counts.len()]);
    std::iter::from_fn(move || {
        let current = next.take()?;
        let mut following = current.clone();
        for (digit, &count) in following.iter_mut().zip(counts).rev() {
            *digit += 1;
            if *digit < count {
                next = Some(following);
                break;
            }
            *digit = 0;
        }
        Some(current)
    })
}

#[cfg(test)]
mod covering_trace;

#[cfg(test)]
mod depth_first_trace;

#[cfg(test)]
#[path = "../tests/support/quint_witness.rs"]
mod quint_witness;
