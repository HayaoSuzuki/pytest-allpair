module CoveringDomain {
  type Row = List[int]
  type Term = { axis: int, levels: List[int] }
  type Rule = List[Term]
  type Problem = { name: str, counts: List[int], order: int, rules: List[Rule] }

  // -1 represents an unassigned factor in a partial row or projection.
  pure def assignments(counts: List[int], first: int): Set[Row] =
    counts.foldl(Set(List()), (prefixes, count) =>
      prefixes.map(prefix => first.to(count - 1).map(level => prefix.append(level))).flatten())

  pure def matchesTerm(row: Row, term: Term): bool =
    term.levels.indices().exists(i => term.levels[i] == row[term.axis])

  // Exhaustive specification used as the reference, independently of search.
  pure def legalRows(problem: Problem): Set[Row] =
    assignments(problem.counts, 0).filter(row =>
      problem.rules.indices().forall(r =>
        problem.rules[r].indices().exists(t => not(matchesTerm(row, problem.rules[r][t])))))

  pure def extends(partial: Row, complete: Row): bool =
    partial.indices().forall(axis => partial[axis] == -1 or partial[axis] == complete[axis])

  pure def completions(legal: Set[Row], partial: Row): Set[Row] =
    legal.filter(row => extends(partial, row))

  pure def project(row: Row, mask: Set[int]): Row =
    range(0, row.length()).foldl(List(), (partial, axis) =>
      partial.append(if (mask.contains(axis)) row[axis] else -1))

  pure def interactions(order: int, rows: Set[Row]): Set[Row] =
    rows.map(row =>
      row.indices().powerset().filter(mask => mask.size() == order)
        .map(mask => project(row, mask))
    ).flatten()
}

module CoveringExamples {
  import CoveringDomain.*

  pure val problems: List[Problem] = List(
    {
      name: "compound exclusions",
      counts: List(2, 2, 2),
      order: 2,
      rules: List(
        List({ axis: 0, levels: List(0) }, { axis: 1, levels: List(0) }, { axis: 2, levels: List(0) }),
        List({ axis: 0, levels: List(0) }, { axis: 1, levels: List(0) }, { axis: 2, levels: List(1) }),
      ),
    },
    {
      name: "single-factor coverage with mixed levels",
      counts: List(2, 3, 2),
      order: 1,
      rules: List(
        List({ axis: 1, levels: List(0, 2) }, { axis: 2, levels: List(0) }),
      ),
    },
    {
      name: "three-way coverage of four factors",
      counts: List(2, 2, 2, 1),
      order: 3,
      // Requiring two ones makes 111 redundant at order two but required at order three.
      rules: List(
        List({ axis: 0, levels: List(0) }, { axis: 1, levels: List(0) }),
        List({ axis: 0, levels: List(0) }, { axis: 2, levels: List(0) }),
        List({ axis: 1, levels: List(0) }, { axis: 2, levels: List(0) }),
      ),
    },
    {
      name: "full order",
      counts: List(2, 3),
      order: 2,
      rules: List(
        List({ axis: 0, levels: List(0) }, { axis: 1, levels: List(1) }),
      ),
    },
    {
      name: "no valid cases",
      counts: List(2, 2),
      order: 1,
      rules: List(
        List({ axis: 0, levels: List(0, 1) }),
      ),
    },
  )
}

module DepthFirstModel {
  import CoveringDomain.*
  import CoveringExamples.*

  const OMIT_LEVEL: bool
  type SearchContext = { problem: Problem, expected: Set[Row] }

  var search: SearchContext
  // The first frame holds the next siblings to visit. Children go before them.
  var frontier: List[Set[Row]]
  var found: Set[Row]
  var previousWeight: int

  pure def prunes(problem: Problem, partial: Row): bool =
    problem.rules.indices().exists(r =>
      problem.rules[r].indices().forall(t => {
        val term = problem.rules[r][t]
        partial[term.axis] != -1 and matchesTerm(partial, term)
      }))

  pure def weight(counts: List[int], partial: Row): int =
    range(0, counts.length()).foldl(1, (total, axis) =>
      if (partial[axis] == -1) total * (counts[axis] + 1) else total)

  pure def remainingWeight(counts: List[int], stack: List[Set[Row]]): int =
    stack.foldl(0, (total, frame) =>
      total + frame.fold(0, (sum, partial) => sum + weight(counts, partial)))

  action init = {
    nondet input = problems.indices().oneOf()
    val problem = problems[input]
    nondet seed = assignments(problem.counts, -1).oneOf()
    all {
      search' = { problem: problem, expected: completions(legalRows(problem), seed) },
      frontier' = List(Set(seed)),
      found' = Set(),
      previousWeight' = weight(problem.counts, seed) + 1,
    }
  }

  action step =
    if (frontier == List()) all {
      search' = search,
      frontier' = frontier,
      found' = found,
      previousWeight' = previousWeight,
    } else {
      nondet partial = frontier.head().oneOf()
      val siblings = frontier.head().exclude(Set(partial))
      val rest = if (siblings == Set()) frontier.tail() else List(siblings).concat(frontier.tail())
      val gaps = range(0, partial.length()).select(axis => partial[axis] == -1)
      val pruned = prunes(search.problem, partial)

      all {
        search' = search,
        previousWeight' = remainingWeight(search.problem.counts, frontier),
        found' = if (not(pruned) and gaps == List()) found.union(Set(partial)) else found,
        frontier' = if (pruned or gaps == List()) rest else {
          val axis = gaps.head()
          val first = if (OMIT_LEVEL) 1 else 0
          val children = first.to(search.problem.counts[axis] - 1)
            .map(level => partial.replaceAt(axis, level))
          if (children == Set()) rest else List(children).concat(rest)
        },
      }
    }

  // Conservation proves both safe pruning and complete enumeration at exhaustion.
  val CompletionConservation = {
    val unvisited = frontier.foldl(Set(), (remaining, frame) =>
      remaining.union(frame.map(partial => completions(search.expected, partial)).flatten()))
    found.union(unvisited) == search.expected
  }

  // Expanding one node replaces a factor of (levels + 1) by at most levels children.
  val SearchProgress = remainingWeight(search.problem.counts, frontier) < previousWeight
}

module CoveringLoopModel {
  import CoveringDomain.*
  import CoveringExamples.*

  const OMIT_SEED: bool
  type CoverageContext = { order: int, legal: Set[Row], required: Set[Row] }

  var coverage: CoverageContext
  var pending: Set[Row]
  var selected: Set[Row]

  action init = {
    nondet input = problems.indices().oneOf()
    val problem = problems[input]
    val allRows = assignments(problem.counts, 0)
    val legal = legalRows(problem)
    all {
      coverage' = { order: problem.order, legal: legal, required: interactions(problem.order, legal) },
      pending' = interactions(problem.order, allRows),
      selected' = Set(),
    }
  }

  action step =
    if (pending == Set()) all { coverage' = coverage, pending' = pending, selected' = selected }
    else {
      nondet seed = pending.oneOf()
      val witnesses = completions(coverage.legal, seed)
      val covered = interactions(coverage.order, selected).contains(seed)
      val omit = OMIT_SEED and seed == List(1, 1, -1)
      all {
        coverage' = coverage,
        pending' = pending.exclude(Set(seed)),
        if (covered or witnesses == Set() or omit) selected' = selected else {
          // The verified search contract allows any legal completion of this seed.
          nondet witness = witnesses.oneOf()
          selected' = selected.union(Set(witness))
        },
      }
    }

  val LegalRows = selected.subseteq(coverage.legal)
  val ProcessedCoverage =
    coverage.required.exclude(pending).subseteq(interactions(coverage.order, selected))
  val FinalCoverage =
    pending != Set() or interactions(coverage.order, selected) == coverage.required
  val NoValidCases = pending != Set() or (selected == Set()) == (coverage.legal == Set())
}

module DepthFirst {
  import DepthFirstModel(OMIT_LEVEL = false).*
}

module DepthFirstMutant {
  import DepthFirstModel(OMIT_LEVEL = true).*
}

module CoveringLoop {
  import CoveringLoopModel(OMIT_SEED = false).*
}

module CoveringLoopMutant {
  import CoveringLoopModel(OMIT_SEED = true).*
}

module Witnesses {
  import CoveringDomain.*
  import CoveringExamples.*

  type Witness = {
    name: str,
    counts: List[int],
    order: int,
    rules: List[Rule],
    legalRows: Set[Row],
    feasible: Set[Row],
  }
  var cases: List[Witness]

  action init = cases' = problems.foldl(List(), (examples, problem) => {
    val legal = legalRows(problem)
    examples.append({
      name: problem.name,
      counts: problem.counts,
      order: problem.order,
      rules: problem.rules,
      legalRows: legal,
      feasible: interactions(problem.order, legal),
    })
  })

  action step = cases' = cases
}
