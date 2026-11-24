# GitHub settings

The pytest-allpair rulesets follow the hoimin configuration. [hoimin rulesets](https://github.com/HayaoSuzuki/hoimin/rules) · [pytest-allpair rulesets](https://github.com/HayaoSuzuki/pytest-allpair/rules)

| Scope | Protection |
| --- | --- |
| Default branch `main` | Block deletion and force pushes |
| `pytest-allpair-release-state` | Block deletion and force pushes |
| `v*` tags | Block updates to existing tags and deletion |

The rulesets have empty bypass lists. CI reports `CI result`, and `main` has no required status checks. GitHub deletes merged branches, offers to update PR branches, and enables Discussions. Wiki and Projects are disabled.

The `Wheel builds` workflow uploads preview wheels as artifacts. The `Package release` workflow creates GitHub Releases and promotes verified wheels through the `testpypi` and `pypi` environments, each restricted to `main`. Set `PYPI_AUTO_PUBLISH=true` to automate this workflow for updates to `main`. See the [publishing guide](../docs/development/guides/publishing.md) for Trusted Publisher settings, versioning, and release verification.
