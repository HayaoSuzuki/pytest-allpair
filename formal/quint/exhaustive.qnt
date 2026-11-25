module BinaryExclusions {
  import CoveringDomain.* from "./covering"

  pure val binaryCounts = List(2, 2, 2)
  pure val binaryRows = assignments(binaryCounts, 0)

  // Candidate levels are lexicographic within an axis combination.
  pure def candidateRows(mask: Set[int]): List[Row] =
    range(0, binaryCounts.length()).foldl(List(List()), (prefixes, axis) => {
      val low = if (mask.contains(axis)) 0 else -1
      val high = if (mask.contains(axis)) binaryCounts[axis] else 0
      prefixes.foldl(List(), (rows, prefix) =>
        range(low, high).foldl(rows, (allRows, level) => allRows.append(prefix.append(level))))
    })

  pure val orderedBinaryRows = candidateRows(binaryCounts.indices())

  // A full-row exclusion can encode any forbidden subset of the Boolean cube.
  pure def binaryProblems(order: int): Set[Problem] =
    binaryRows.powerset().map(forbidden => {
      name: "three binary factors",
      counts: binaryCounts,
      order: order,
      rules: orderedBinaryRows.select(row => forbidden.contains(row))
        .foldl(List(), (rules, row) => rules.append(
          range(0, row.length()).foldl(List(), (terms, axis) =>
            terms.append({ axis: axis, levels: List(row[axis]) })
          )
        )),
    })
}

module OrderedCoveringModel {
  import CoveringDomain.* from "./covering"
  import BinaryExclusions.*

  const OMIT_CACHE_UPDATE: bool
  type CoverageInput = { legal: Set[Row], order: int, masks: List[Set[int]], required: Set[Row] }

  var input: CoverageInput
  var pending: List[Row]
  var selected: List[Row]
  var covered: Set[Row]

  // Prefix each suffix first. Filtering by size gives Rust's lexicographic axis order.
  pure def axisCombinations(count: int, order: int): List[Set[int]] =
    range(0, count).foldl(List(Set()), (suffixes, offset) => {
      val axis = count - 1 - offset
      suffixes.foldl(List(), (withAxis, suffix) => withAxis.append(suffix.union(Set(axis))))
        .concat(suffixes)
    }).select(axes => axes.size() == order)

  pure def seedSequence(masks: List[Set[int]]): List[Row] =
    masks.foldl(List(), (seeds, mask) => seeds.concat(candidateRows(mask)))

  // Compare axis combinations first, then the levels of those axes.
  pure def seedRank(seed: Row): int = {
    val axisRank = seed.foldl(0, (rank, level) => 2 * rank + (if (level == -1) 1 else 0))
    val levelRank = seed.foldl(0, (rank, level) => 2 * rank + (if (level == 1) 1 else 0))
    binaryRows.size() * axisRank + levelRank
  }

  pure def asSet(rows: List[Row]): Set[Row] = rows.indices().map(index => rows[index])

  action init = {
    nondet order = 1.to(binaryCounts.length()).oneOf()
    nondet problem = binaryProblems(order).oneOf()
    val legal = legalRows(problem)
    val masks = axisCombinations(binaryCounts.length(), order)
    all {
      input' = { legal: legal, order: order, masks: masks, required: interactions(order, legal) },
      pending' = seedSequence(masks),
      selected' = List(),
      covered' = Set(),
    }
  }

  action step = if (pending == List()) all {
    input' = input,
    pending' = pending,
    selected' = selected,
    covered' = covered,
  } else {
    val seed = pending.head()
    val witnesses = completions(input.legal, seed)
    all {
      input' = input,
      pending' = pending.tail(),
      if (covered.contains(seed) or witnesses == Set()) all {
        selected' = selected,
        covered' = covered,
      } else {
        nondet witness = witnesses.oneOf()
        val projections = input.masks.indices().map(index => project(witness, input.masks[index]))
        all {
          selected' = selected.append(witness),
          covered' = if (OMIT_CACHE_UPDATE) covered else covered.union(projections),
        }
      },
    }
  }

  val SeedEnumeration = {
    val seeds = seedSequence(input.masks)
    val expected = interactions(input.order, binaryRows)
    val offset = seeds.length() - pending.length()
    all {
      asSet(seeds) == expected,
      1.to(seeds.length() - 1).forall(i => seedRank(seeds[i - 1]) < seedRank(seeds[i])),
      if (offset < 0) false else pending.indices().forall(i => pending[i] == seeds[offset + i]),
    }
  }
  val CacheMatchesSelection = covered == interactions(input.order, asSet(selected))
  val LegalUniqueRows =
    asSet(selected).subseteq(input.legal) and asSet(selected).size() == selected.length()
  val ProcessedCoverage = input.required.exclude(asSet(pending)).subseteq(covered)
  val FinalCoverage = pending != List() or covered == input.required
  val NoValidCases = pending != List() or (selected == List()) == (input.legal == Set())

  // A continuously enabled step must eventually run.
  temporal Finishes = step.weakFair(pending).implies(eventually(pending == List()))
}

module BinaryDepthFirst {
  import BinaryExclusions.*
  // Completion search is independent of the coverage order.
  import DepthFirstModel(INPUTS = binaryProblems(2), OMIT_LEVEL = false).* from "./covering"
}

module BinaryCovering {
  import OrderedCoveringModel(OMIT_CACHE_UPDATE = false).*
}

module BinaryCoveringMutant {
  import OrderedCoveringModel(OMIT_CACHE_UPDATE = true).*
}
