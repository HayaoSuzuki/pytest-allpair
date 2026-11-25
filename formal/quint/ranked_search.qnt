module RankedSearch {
  import CoveringDomain.* from "./covering"

  pure def coverageGain(partial: Row, axis: int, level: int, order: int, covered: Set[Row]): int = {
    val candidate = partial.replaceAt(axis, level)
    val assigned = candidate.indices().filter(i => candidate[i] != -1)
    val masks = assigned.powerset().filter(mask => mask.contains(axis) and mask.size() == order)
    masks.map(mask => project(candidate, mask)).exclude(covered).size()
  }

  // Depth-first traversal compares paths at their first differing candidate.
  pure def rankKey(seed: Row, row: Row, order: int, covered: Set[Row]): List[int] =
    range(0, seed.length()).foldl({ partial: seed, key: List() }, (path, axis) =>
      if (seed[axis] != -1) path else {
        val level = row[axis]
        val gain = coverageGain(path.partial, axis, level, order, covered)
        {
          partial: path.partial.replaceAt(axis, level),
          key: path.key.append(-gain).append(level),
        }
      }).key

  // Both keys come from completions of the same seed.
  pure def precedes(left: List[int], right: List[int]): bool =
    left.indices().exists(i =>
      left[i] < right[i] and 0.to(i - 1).forall(j => left[j] == right[j]))

  // Legal-row enumeration makes the expected choice independent of pruning and the stack.
  pure def firstRankedCompletion(seed: Row, order: int, covered: Set[Row], legal: Set[Row]): List[Row] = {
    val best = completions(legal, seed)
      .map(row => { row: row, key: rankKey(seed, row, order, covered) })
      .fold({ row: List(), key: List() }, (minimum, candidate) =>
        if (minimum.row == List()) candidate
        else if (precedes(candidate.key, minimum.key)) candidate
        else minimum)
    if (best.row == List()) List() else List(best.row)
  }

  pure def orderedLegalRows(counts: List[int], legal: Set[Row]): List[Row] =
    orderedAssignments(counts, counts.indices()).select(row => legal.contains(row))
}

module RankedSearchTests {
  import RankedSearch.*

  pure val twoChoices = Set([0, 0, 0], [0, 1, 0])
  pure val zeroInteractions = Set([0, 0, -1], [-1, 0, 0])

  run gainCountsOnlyNewInteractionsInvolvingTheCandidateTest =
    assert(coverageGain([1, -1, 0], 1, 0, 2, Set([1, 0, -1])) == 1)

  run highestGainWinsTest =
    assert(firstRankedCompletion([0, -1, 0], 2, zeroInteractions, twoChoices) == List([0, 1, 0]))

  run lowestLevelWinsTieTest =
    assert(firstRankedCompletion([0, -1, 0], 2, Set(), twoChoices.union(Set([0, 2, 0]))) == List([0, 0, 0]))

  run infeasiblePreferredLevelFallsBackTest =
    assert(firstRankedCompletion([0, -1, 0], 2, zeroInteractions, Set([0, 0, 0], [1, 1, 0])) ==
      List([0, 0, 0]))

  run recalculatesGainAfterExtendingThePrefixTest =
    assert(firstRankedCompletion([0, -1, -1], 2, Set([0, 0, -1], [0, -1, 0], [-1, 1, 0]),
      Set([0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1])) == List([0, 1, 1]))

  run fullOrderVisitsMixedLevelsInLexicographicOrderTest =
    assert(orderedLegalRows([3, 2], Set([2, 1], [1, 0], [0, 0], [2, 0])) ==
      List([0, 0], [1, 0], [2, 0], [2, 1]))

  run noLegalCompletionTest =
    assert(firstRankedCompletion([0, -1, 0], 2, Set(), Set([1, 0, 0])) == List())
}
