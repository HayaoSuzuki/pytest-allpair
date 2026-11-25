module DepthFirstReplay {
  import CoveringDomain.* from "./covering"

  import CoveringExamples.* from "./covering"
  import DepthFirstTransitions.* from "./covering"
  export DepthFirstTransitions.Expanded
  export DepthFirstTransitions.Pruned
  export DepthFirstTransitions.Found

  type SearchRun = { events: List[SearchEvent], yielded: List[Row], returned: List[Row] }

  pure def coversCatalog(inputs: List[(int, Row, bool)]): bool = {
    val expected = problems.indices().map(i =>
      assignments(problems[i].counts, -1).map(seed => Set((i, seed, false), (i, seed, true))).flatten()
    ).flatten()
    inputs.length() == expected.size() and inputs.indices().map(i => inputs[i]) == expected
  }

  pure def validSeed(problem: Problem, seed: Row): bool =
    if (seed.length() != problem.counts.length()) false else
      seed.indices().forall(i => -1 <= seed[i] and seed[i] < problem.counts[i])

  pure def replaysSearch(caseIndex: int, seed: Row, stopAtFirst: bool, runTrace: SearchRun): bool =
    if (not(problems.indices().contains(caseIndex))) false else {
      val problem = problems[caseIndex]
      if (not(validSeed(problem, seed))) false else {
        val initial = { cursor: startSearch(seed), yielded: List(), valid: true }
        val end = runTrace.events.foldl(initial, (replay, event) => {
          val stopped = stopAtFirst and replay.yielded != List()
          if (replay.valid and not(stopped) and nextSearchEvents(problem, replay.cursor).contains(event)) {
            {
              cursor: advanceSearch(problem, replay.cursor, event, 0),
              yielded: if (event.kind == Found) replay.yielded.append(event.node) else replay.yielded,
              valid: true,
            }
          } else replay.with("valid", false)
        })
        val returned = if (stopAtFirst and end.yielded != List()) List(end.yielded.head()) else List()
        end.valid and end.yielded == runTrace.yielded and returned == runTrace.returned and
          (returned != List() or end.cursor.frontier == List())
      }
    }
}

module DepthFirstReplayTests {
  import DepthFirstReplay.*

  // Catalog case 3 has counts [2, 3] and excludes [0, 1].
  pure val seed = [0, -1]
  pure val expand = { node: seed, kind: Expanded }
  pure val low = { node: [0, 0], kind: Found }
  pure val excluded = { node: [0, 1], kind: Pruned }
  pure val high = { node: [0, 2], kind: Found }
  pure val completeRun: SearchRun = {
    events: List(expand, low, excluded, high),
    yielded: List(low.node, high.node),
    returned: List(),
  }
  pure val firstRun: SearchRun = {
    events: List(expand, high),
    yielded: List(high.node),
    returned: List(high.node),
  }

  run rejectsIncompleteMatrixTest =
    assert(not(coversCatalog(List((3, seed, true)))))
  run acceptsExhaustedSearchTest = assert(replaysSearch(3, seed, false, completeRun))
  run acceptsFirstHitTest = assert(replaysSearch(3, seed, true, firstRun))
  run acceptsPrunedRootTest = assert(replaysSearch(4, seed, true, {
    events: List({ node: seed, kind: Pruned }), yielded: List(), returned: List(),
  }))
  run rejectsIncompleteExhaustionTest = assert(not(replaysSearch(3, seed, false,
    completeRun.with("events", List(expand, low, excluded)).with("yielded", List(low.node)))))
  run rejectsFalsePruneTest = assert(not(replaysSearch(3, seed, false,
    completeRun.with("events", completeRun.events.replaceAt(1, low.with("kind", Pruned)))
      .with("yielded", List(high.node)))))
  run rejectsPostBreakVisitTest = assert(not(replaysSearch(3, seed, true,
    firstRun.with("events", firstRun.events.append(low)).with("yielded", List(high.node, low.node)))))
  run rejectsWrongReturnTest = assert(not(replaysSearch(3, seed, true,
    firstRun.with("returned", List(low.node)))))
  run rejectsWrongYieldOrderTest = assert(not(replaysSearch(3, seed, false,
    completeRun.with("yielded", List(high.node, low.node)))))
  run rejectsWrongStackFrameTest = assert(not(replaysSearch(3, [-1, -1], false, {
    events: List(
      { node: [-1, -1], kind: Expanded },
      expand,
      { node: [1, -1], kind: Expanded },
      { node: [1, 0], kind: Found },
      { node: [1, 1], kind: Found },
      { node: [1, 2], kind: Found },
      low,
      excluded,
      high,
    ),
    yielded: List([1, 0], [1, 1], [1, 2], low.node, high.node),
    returned: List(),
  })))
  run rejectsMalformedSeedTest = assert(not(replaysSearch(3, [0, 3], false, completeRun)))
}
