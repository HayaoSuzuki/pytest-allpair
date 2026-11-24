# Marker reference

## pairwise_parametrize

`pytest.mark.pairwise_parametrize(argnames, argvalues, *, ids=None, indirect=False, scope=None)` declares one factor. You can apply it to a function, class, or module. If a factor groups several arguments, each candidate row counts as one level. The plugin treats equal rows at different positions as distinct levels.

Generated rows carry the marks and IDs from each selected `pytest.param`. Pass a sequence or a callable as `ids`. A candidate with `pytest.HIDDEN_PARAM` contributes no fragment to the generated ID. Use `indirect` to pass a candidate value to the corresponding fixture through `request.param`. If you set `scope`, give every factor the same scope.

Standard `pytest.mark.parametrize` and fixture parametrization form a Cartesian product with the generated rows. Specifying the same argument in both a covering factor and standard `parametrize` or `fixture(params=...)` causes a collection error.

## pairwise

You can apply `pytest.mark.pairwise(*, order=..., exclude=...)` once per test function. The default order is the smaller of 2 and the number of factors. `order=1` covers each feasible level. `order="max"` generates every valid complete case. An integer order can range from 1 to the number of factors.

Pass a sequence of dictionaries as `exclude`. A dictionary matches a case when all its argument values match. A case is excluded if any dictionary matches. Values follow Python's normal equality rules.

Coverage includes each n-way interaction that appears in at least one valid complete case. pytest applies selection with `-k` and `-m` after generation. If a factor has an empty candidate list, pytest applies its `empty_parameter_set_mark` setting. If every factor has candidates and the exclusions rule out all cases, the plugin reports a collection error.
