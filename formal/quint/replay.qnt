module CoveringReplay {
  import CoveringDomain.* from "./covering"
  import BinaryExclusions.* from "./exhaustive"
  import OrderedCoveringTransitions.* from "./exhaustive"
  export OrderedCoveringTransitions.CoveringEvent

  pure def replays(order: int, forbidden: Set[Row], events: List[CoveringEvent]): bool =
    if (not(1.to(binaryCounts.length() - 1).contains(order) and forbidden.subseteq(binaryRows))) false
    else {
      val input = coveringInput(order, forbidden)
      val end = events.foldl({ state: startCovering(input), valid: true }, (replay, event) =>
        if (replay.valid and nextEvents(input, replay.state).contains(event))
          { state: advance(replay.state, event), valid: true }
        else { state: replay.state, valid: false })
      end.valid and end.state.pending == List()
    }
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
