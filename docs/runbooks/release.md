# Release Runbook

Use only the local release targets:

```bash
make release-patch
make release-minor
make release-major
```

The release script verifies clean, up-to-date `main`, runs release preflight, creates an
annotated semver tag, pushes `main` and the tag, and dispatches the release workflow.

The release workflow builds a wheel and sdist with `make build`, publishes both as
GitHub Release artifacts, and dispatches `pdomain-index-pip` with
`PDOMAIN_INDEX_DISPATCH`. If dispatch is unavailable, the scheduled index regen is
the fallback.
