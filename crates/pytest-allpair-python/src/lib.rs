use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pytest_allpair_core::ForbiddenRule;

/// The caller owns Python values and metadata. Only the numeric model crosses
/// the boundary, so the search can run without holding the Python interpreter.
#[pyfunction]
fn generate(
    py: Python<'_>,
    level_counts: Vec<usize>,
    order: usize,
    forbidden: Vec<Vec<(usize, Vec<usize>)>>,
) -> PyResult<Vec<Vec<usize>>> {
    let rules: Vec<_> = forbidden
        .into_iter()
        .map(|terms| ForbiddenRule { terms })
        .collect();
    py.detach(|| pytest_allpair_core::generate(&level_counts, order, &rules))
        .map_err(|error| PyValueError::new_err(error.to_string()))
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(generate, module)?)
}
