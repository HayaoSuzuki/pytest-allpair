module GeneratedProblems {
  import CoveringDomain.* from "./covering"

  pure def lastRuleCode(counts: List[int]): int =
    (2 ^ counts.foldl(0, (sum, levels) => sum + levels)) - 1

  // Each factor consumes one bit per level. An all-zero field omits that factor.
  pure def ruleFromCode(counts: List[int], code: int): Rule =
    range(0, counts.length()).foldl({ remaining: code, terms: List() }, (decoded, axis) => {
      val levels = range(0, counts[axis]).select(level =>
        (decoded.remaining / (2 ^ level)) % 2 == 1)
      {
        remaining: decoded.remaining / (2 ^ counts[axis]),
        terms: if (levels == List()) decoded.terms else decoded.terms.append({ axis: axis, levels: levels }),
      }
    }).terms
}

module GeneratedProblemsTests {
  import CoveringDomain.* from "./covering"
  import GeneratedProblems.*

  pure def levelsAt(rule: Rule, axis: int): Set[int] =
    rule.indices().filter(i => rule[i].axis == axis)
      .map(i => rule[i].levels.indices().map(j => rule[i].levels[j])).flatten()

  run zeroHasNoTermsTest =
    assert(ruleFromCode([1, 3, 2], 0) == List())

  run selectsNoncontiguousLevelsAndSkipsAnAxisTest =
    assert(ruleFromCode([1, 3, 2], 26) == List(
      { axis: 1, levels: [0, 2] },
      { axis: 2, levels: [0] },
    ))

  run capsTheRuleCodeAtFifteenBitsTest =
    assert(lastRuleCode([3, 3, 3, 3, 3]) == 32767)

  run includesEveryLevelAtMaximumCodeTest =
    assert(ruleFromCode([3, 3, 3, 3, 3], lastRuleCode([3, 3, 3, 3, 3])) ==
      List(
        { axis: 0, levels: [0, 1, 2] },
        { axis: 1, levels: [0, 1, 2] },
        { axis: 2, levels: [0, 1, 2] },
        { axis: 3, levels: [0, 1, 2] },
        { axis: 4, levels: [0, 1, 2] },
      ))

  run matchesEverySubsetForMixedLevelsTest = {
    val zero = 0.to(0).powerset()
    val one = 0.to(2).powerset()
    val two = 0.to(1).powerset()
    val expected = tuples(zero, one, two)
    val matchByAxis = 0.to(lastRuleCode([1, 3, 2])).map(word => {
      val rule = ruleFromCode([1, 3, 2], word)
      (levelsAt(rule, 0), levelsAt(rule, 1), levelsAt(rule, 2))
    })
    assert(matchByAxis == expected)
  }
}
