# Publishing a release

Build and validate three ABI3 wheels for Linux x86-64 (manylinux 2.28), macOS
Arm64, and Windows x86-64. The release workflow publishes the same wheel bytes
to GitHub Releases, TestPyPI, and PyPI. CI also exercises installation from an
sdist. The index uploads contain wheels, as in hoimin.

## Configure Trusted Publishing

The two GitHub environments, `testpypi` and `pypi`, accept deployments from the
`main` branch. The upload jobs use GitHub OIDC through the official PyPA
publishing action. Register a pending Trusted Publisher for the new project on
each index. [GitHub environments](https://github.com/HayaoSuzuki/pytest-allpair/settings/environments) · [PyPI setup guide](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)

| Field | TestPyPI | PyPI |
| --- | --- | --- |
| PyPI project name | `pytest-allpair` | `pytest-allpair` |
| GitHub owner | `HayaoSuzuki` | `HayaoSuzuki` |
| Repository | `pytest-allpair` | `pytest-allpair` |
| Workflow filename | `release.yml` | `release.yml` |
| Environment | `testpypi` | `pypi` |

Sign in to each of these accounts to configure its publisher. The first upload
on each index creates the corresponding project. [TestPyPI publishers](https://test.pypi.org/manage/account/publishing/) · [PyPI publishers](https://pypi.org/manage/account/publishing/)

## Preview and publish

Dispatch the workflow with `operation=preview` to build and smoke-test the
wheels and validate the SBOM inventory. A preview can use a candidate branch
and uploads its files as Actions artifacts.

```sh
gh workflow run release.yml --repo HayaoSuzuki/pytest-allpair --ref main -f operation=preview
```

For a release, set the intended stable version in the Python and Rust manifests
and commit the corresponding lockfiles. Create the corresponding `vX.Y.Z` tag
at that commit on `main`. Dispatch `operation=release` while that commit is at
the tip of `main`. The workflow checks that the tag, Python package version,
and workflow source commit agree.

```sh
gh workflow run release.yml --repo HayaoSuzuki/pytest-allpair --ref main \
  -f operation=release -f tag=v0.1.0
```

After the GitHub Release succeeds, dispatch `operation=testpypi`. Review the
verification results, then dispatch `operation=pypi` to promote the release.
The production job requires fresh verification of the complete TestPyPI
publication. Release and promotion run on demand.

```sh
gh workflow run release.yml --repo HayaoSuzuki/pytest-allpair --ref main \
  -f operation=testpypi -f tag=v0.1.0
gh workflow run release.yml --repo HayaoSuzuki/pytest-allpair --ref main \
  -f operation=pypi -f tag=v0.1.0
```

## Verify artifacts

- maturin includes the Cargo CycloneDX SBOM in the wheel under
  `.dist-info/sboms/`. GitHub Releases also carry the extracted SBOM files and
  `SHA256SUMS`. The Cargo SBOM records native build dependencies. The wheel's
  Python metadata declares its pytest requirement. [maturin SBOM guide](https://www.maturin.rs/sbom)
- GitHub Actions signs the release inventory, signs each wheel with a
  single-subject SLSA build attestation, and registers a CycloneDX attestation
  for each wheel's Cargo SBOM. [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)
- Promotion verifies original wheel signatures against the release tag's commit
  and the `release.yml` workflow. PyPA attaches the original SLSA statement
  and a separate PEP 740 publish attestation to each wheel on both indexes.
  Verification downloads each served wheel and checks both predicates and the
  expected publisher. [PyPI attestations](https://docs.pypi.org/attestations/)

When an index already has the complete release and its bytes and attestations
verify, a rerun reuses it. Treat a partial release, changed file, or invalid
signature as a failed promotion. Review the index before choosing a new version.
