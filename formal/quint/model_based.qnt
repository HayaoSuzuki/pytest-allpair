module ConnectCoverage {
  import CoveringDomain.* from "./covering"
  import CoveringExamples.* from "./covering"
  import BinaryExclusions.* from "./exhaustive"
  import GeneratedProblems.* from "./generated_inputs"

  type Observation = { no_valid_cases: bool, legal_unique_rows: bool, covered: Set[Row] }
  var observed: Observation

  pure val catalog = problems.indices().map(i => problems[i])
  pure val binaryCatalog = 1.to(binaryCounts.length()).map(order => binaryProblems(order)).flatten()
  pure val levelLists = 1.to(3).allListsUpTo(5)

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

  action sampleGenerated = {
    nondet factorCount = 1.to(5).oneOf()
    nondet counts = levelLists.filter(levels => levels.length() == factorCount).oneOf()
    nondet order = 1.to(factorCount).oneOf()
    nondet ruleCount = 0.to(5).oneOf()
    val codes = 1.to(lastRuleCode(counts))
    // Sample the product directly to avoid enumerating lists of rule codes.
    nondet sampled = tuples(codes, codes, codes, codes, codes).oneOf()
    val words = List(sampled._1, sampled._2, sampled._3, sampled._4, sampled._5)
    val rules = words.slice(0, ruleCount).foldl(List(), (rulesSoFar, word) =>
      rulesSoFar.append(ruleFromCode(counts, word)))
    nondet scenario = Set({
      name: "generated covering array",
      counts: counts,
      order: order,
      rules: rules,
    }).oneOf()
    observed' = expected(scenario)
  }

  action step = any { sampleCatalog, sampleBinary }
}
