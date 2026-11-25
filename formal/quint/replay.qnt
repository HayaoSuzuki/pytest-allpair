module CoveringReplay {
  import CoveringDomain.* from "./covering"
  import BinaryExclusions.* from "./exhaustive"
  import OrderedCoveringTransitions.* from "./exhaustive"
  export OrderedCoveringTransitions.CoveringEvent

  pure def replaysInput(input: CoverageInput, events: List[CoveringEvent]): bool = {
    val end = events.foldl({ state: startCovering(input), valid: true }, (replay, event) =>
      if (replay.valid and rankedEvents(input, replay.state).contains(event))
        { state: advance(replay.state, event), valid: true }
      else { state: replay.state, valid: false })
    end.valid and end.state.pending == List()
  }

  pure def replays(order: int, forbidden: Set[Row], events: List[CoveringEvent]): bool =
    if (not(1.to(binaryCounts.length() - 1).contains(order) and forbidden.subseteq(binaryRows))) false
    else replaysInput(coveringInput(order, forbidden), events)

  pure def replaysUnconstrained(counts: List[int], order: int, events: List[CoveringEvent]): bool =
    if (not(1.to(counts.length() - 1).contains(order) and counts.indices().forall(i => counts[i] > 0))) false
    else replaysInput(coveringInputFor({ name: "unconstrained replay", counts: counts, order: order, rules: List() }), events)
}

module CoveringReplayTests {
  import CoveringReplay.*
  import BinaryExclusions.* from "./exhaustive"

  pure val forbidden = binaryRows.exclude(Set([0, 0, 0]))
  pure val cached = Set([0, -1, -1], [-1, 0, -1], [-1, -1, 0])
  pure val events: List[CoveringEvent] = List(
    { seed: [0, -1, -1], addition: List([0, 0, 0]), cache: cached },
    { seed: [1, -1, -1], addition: List(), cache: cached },
    { seed: [-1, 0, -1], addition: List(), cache: cached },
    { seed: [-1, 1, -1], addition: List(), cache: cached },
    { seed: [-1, -1, 0], addition: List(), cache: cached },
    { seed: [-1, -1, 1], addition: List(), cache: cached },
  )

  pure val fullyCovered = cached.union(Set([1, -1, -1], [-1, 1, -1], [-1, -1, 1]))
  pure val unconstrainedEvents =
    events.replaceAt(1, { seed: [1, -1, -1], addition: List([1, 1, 1]), cache: fullyCovered })
      .slice(0, 2).concat(
        events.slice(2, 6).foldl(List(), (rest, event) => rest.append(event.with("cache", fullyCovered))))

  run acceptsHighestGainAcrossUnconstrainedTraceTest =
    assert(replays(1, Set(), unconstrainedEvents))

  run rejectsLegalButLowerRankedChoiceTest = {
    val changedCache = Set([0, -1, -1], [-1, 1, -1], [-1, -1, 1])
    val changed = unconstrainedEvents
      .replaceAt(0, { seed: [0, -1, -1], addition: List([0, 1, 1]), cache: changedCache })
      .replaceAt(1, unconstrainedEvents[1].with("addition", List([1, 0, 0])))
    assert(not(replays(1, Set(), changed)))
  }

  run acceptsCompleteTraceTest = assert(replays(1, forbidden, events))
  run rejectsOutOfDomainExclusionTest =
    assert(not(replays(1, forbidden.union(Set([0, 0, 2])), events)))
  run rejectsTruncatedTraceTest = assert(not(replays(1, forbidden, events.slice(0, events.length() - 1))))
  run rejectsExtraEventTest = assert(not(replays(1, forbidden, events.append(events[5]))))
  run rejectsWrongSeedTest =
    assert(not(replays(1, forbidden, events.replaceAt(1, events[2]))))
  run rejectsStaleCacheTest =
    assert(not(replays(1, forbidden, events.replaceAt(0,
      { seed: events[0].seed, addition: events[0].addition, cache: Set() }))))
  run rejectsIllegalChoiceTest =
    assert(not(replays(1, forbidden, events.replaceAt(0,
      { seed: events[0].seed, addition: List([1, 1, 1]), cache: cached }))))
}
