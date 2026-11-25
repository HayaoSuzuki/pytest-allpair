module ConnectCoverage {
  import CoveringDomain.* from "./covering"
  import CoveringExamples.* from "./covering"
  import BinaryExclusions.* from "./exhaustive"

  type Observation = { no_valid_cases: bool, legal_unique_rows: bool, covered: Set[Row] }
  var observed: Observation

  pure val catalog = problems.indices().map(i => problems[i])
  pure val binaryCatalog = 1.to(binaryCounts.length()).map(order => binaryProblems(order)).flatten()

  pure def expected(scenario: Problem): Observation = {
    val legal = legalRows(scenario)
    { no_valid_cases: legal == Set(), legal_unique_rows: true, covered: interactions(scenario.order, legal) }
  }

  action init = {
    // This catalog case distinguishes three-way coverage from pairwise coverage.
    nondet scenario = Set(problems[2]).oneOf()
    observed' = expected(scenario)
  }

  action sampleCatalog = {
    nondet scenario = catalog.oneOf()
    observed' = expected(scenario)
  }

  action sampleBinary = {
    nondet scenario = binaryCatalog.oneOf()
    observed' = expected(scenario)
  }

  action step = any { sampleCatalog, sampleBinary }
}
