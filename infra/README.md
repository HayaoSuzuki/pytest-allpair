# GitHub settings

The pytest-allpair rulesets follow the hoimin configuration. [hoimin rulesets](https://github.com/HayaoSuzuki/hoimin/rules) · [pytest-allpair rulesets](https://github.com/HayaoSuzuki/pytest-allpair/rules)

| Scope | Protection |
| --- | --- |
| Default branch `main` | Block deletion and force pushes |
| `pytest-allpair-release-state` | Block deletion and force pushes |
| `v*` tags | Block updates to existing tags and deletion |

The rulesets have empty bypass lists. CI reports `CI result`, and `main` has no required status checks. GitHub deletes merged branches, offers to update PR branches, and enables Discussions. Wiki and Projects are disabled.

The `Wheel builds` workflow uploads wheels as artifacts. Use `pytest-allpair-release-state` if the project starts tracking release state in Git.
