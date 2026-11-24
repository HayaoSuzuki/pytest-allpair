module PruningModel {
  const MUTANT: bool
  type Assignment = { a: int, b: int, c: int }

  pure def assignments(levels: Set[int]): Set[Assignment] =
    tuples(levels, levels, levels).map(row => { a: row._1, b: row._2, c: row._3 })

  pure val legal = assignments(Set(0, 1)).filter(row => row.a != 0 or row.b != 0)
  pure val partials = assignments(Set(-1, 0, 1))

  pure def extends(partial: Assignment, row: Assignment): bool =
    (partial.a == -1 or partial.a == row.a)
    and (partial.b == -1 or partial.b == row.b)
    and (partial.c == -1 or partial.c == row.c)

  var candidate: Assignment
  var pruned: bool

  action init = all {
    candidate' = { a: -1, b: -1, c: -1 },
    pruned' = false,
  }

  action step = {
    nondet choice = partials.oneOf()
    all {
      candidate' = choice,
      pruned' = if (MUTANT) choice.a == 0 or choice.b == 0 else choice.a == 0 and choice.b == 0,
    }
  }

  val SoundPrune = not(pruned) or not(legal.exists(row => extends(candidate, row)))
}

module Pruning {
  import PruningModel(MUTANT = false).*
}

module PruningMutant {
  import PruningModel(MUTANT = true).*
}
