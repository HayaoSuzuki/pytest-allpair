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
  pure def binaryProblem(order: int, forbidden: Set[Row]): Problem = {
    name: "three binary factors",
    counts: binaryCounts,
    order: order,
    rules: orderedBinaryRows.select(row => forbidden.contains(row))
      .foldl(List(), (rules, row) => rules.append(
        range(0, row.length()).foldl(List(), (terms, axis) =>
          terms.append({ axis: axis, levels: List(row[axis]) })
        )
      )),
  }

  pure def binaryProblems(order: int): Set[Problem] =
    binaryRows.powerset().map(forbidden => binaryProblem(order, forbidden))
}

module OrderedCoveringTransitions {
  import CoveringDomain.* from "./covering"
  import BinaryExclusions.*

  type CoverageInput = { legal: Set[Row], order: int, masks: List[Set[int]], required: Set[Row] }
  type CoveringState = { pending: List[Row], selected: List[Row], covered: Set[Row] }
  // Addition holds zero or one selected row. Cache is the set after the seed is processed.
  type CoveringEvent = { seed: Row, addition: List[Row], cache: Set[Row] }

  // Prefix each suffix first. Filtering by size gives Rust's lexicographic axis order.
  pure def axisCombinations(count: int, order: int): List[Set[int]] =
    range(0, count).foldl(List(Set()), (suffixes, offset) => {
      val axis = count - 1 - offset
      suffixes.foldl(List(), (withAxis, suffix) => withAxis.append(suffix.union(Set(axis))))
        .concat(suffixes)
    }).select(axes => axes.size() == order)

  pure def seedSequence(masks: List[Set[int]]): List[Row] =
    masks.foldl(List(), (seeds, mask) => seeds.concat(candidateRows(mask)))

  pure def coveringInput(order: int, forbidden: Set[Row]): CoverageInput = {
    val legal = legalRows(binaryProblem(order, forbidden))
    {
      legal: legal,
      order: order,
      masks: axisCombinations(binaryCounts.length(), order),
      required: interactions(order, legal),
    }
  }

  pure def startCovering(input: CoverageInput): CoveringState =
    { pending: seedSequence(input.masks), selected: List(), covered: Set() }

  // All observations allowed by one transition, regardless of the search scoring.
  pure def nextEvents(input: CoverageInput, state: CoveringState): Set[CoveringEvent] =
    if (state.pending == List()) Set() else {
      val seed = state.pending.head()
      val witnesses = completions(input.legal, seed)
      if (state.covered.contains(seed) or witnesses == Set()) {
        Set({ seed: seed, addition: List(), cache: state.covered })
      } else {
        witnesses.map(witness => {
          val projections = input.masks.indices().map(i => project(witness, input.masks[i]))
          { seed: seed, addition: List(witness), cache: state.covered.union(projections) }
        })
      }
    }

  // Apply an event admitted by nextEvents.
  pure def advance(state: CoveringState, event: CoveringEvent): CoveringState =
    { pending: state.pending.tail(), selected: state.selected.concat(event.addition), covered: event.cache }
}

module OrderedCoveringModel {
  import CoveringDomain.* from "./covering"
  import BinaryExclusions.*
  import OrderedCoveringTransitions.*

  const OMIT_CACHE_UPDATE: bool
  var input: CoverageInput
  var cover: CoveringState

  // Compare axis combinations first, then the levels of those axes.
  pure def seedRank(seed: Row): int = {
    val axisRank = seed.foldl(0, (rank, level) => 2 * rank + (if (level == -1) 1 else 0))
    val levelRank = seed.foldl(0, (rank, level) => 2 * rank + (if (level == 1) 1 else 0))
    binaryRows.size() * axisRank + levelRank
  }

  pure def asSet(rows: List[Row]): Set[Row] = rows.indices().map(index => rows[index])

  action init = {
    nondet order = 1.to(binaryCounts.length()).oneOf()
    nondet forbidden = binaryRows.powerset().oneOf()
    val initial = coveringInput(order, forbidden)
    all { input' = initial, cover' = startCovering(initial) }
  }

  action step = if (cover.pending == List()) all { input' = input, cover' = cover } else {
    nondet event = nextEvents(input, cover).oneOf()
    val following = advance(cover, event)
    all {
      input' = input,
      cover' = if (OMIT_CACHE_UPDATE) following.with("covered", cover.covered) else following,
    }
  }

  val SeedEnumeration = {
    val seeds = seedSequence(input.masks)
    val expected = interactions(input.order, binaryRows)
    val offset = seeds.length() - cover.pending.length()
    all {
      asSet(seeds) == expected,
      1.to(seeds.length() - 1).forall(i => seedRank(seeds[i - 1]) < seedRank(seeds[i])),
      if (offset < 0) false else cover.pending.indices().forall(i => cover.pending[i] == seeds[offset + i]),
    }
  }
  val CacheMatchesSelection = cover.covered == interactions(input.order, asSet(cover.selected))
  val LegalUniqueRows =
    asSet(cover.selected).subseteq(input.legal) and asSet(cover.selected).size() == cover.selected.length()
  val ProcessedCoverage = input.required.exclude(asSet(cover.pending)).subseteq(cover.covered)
  val FinalCoverage = cover.pending != List() or cover.covered == input.required
  val NoValidCases = cover.pending != List() or (cover.selected == List()) == (input.legal == Set())

  // A continuously enabled step must eventually run.
  temporal Finishes = step.weakFair(cover).implies(eventually(cover.pending == List()))
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
