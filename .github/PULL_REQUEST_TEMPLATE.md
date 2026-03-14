## Summary

<!-- Brief description of what this PR does and why -->

## Related Issue(s)

<!-- Link to the Issue(s) this PR addresses -->
Closes #

## Changes

<!-- Bullet list of specific changes made -->
-

## Test Plan

<!-- How was this tested? What evidence proves it works? -->

### 8-Stage Development Loop Checklist

- [ ] **Code** — Changes implemented
- [ ] **Iterate** — Re-read changes, checked edge cases, refined
- [ ] **Static Test** — `pytest` / `cargo test` — zero failures
- [ ] **Deep Static Test** — `mypy --strict` / `cargo clippy -D warnings` — zero errors
- [ ] **Check Syntax** — `ruff check && ruff format --check` / `cargo fmt --check` — clean
- [ ] **Code Review** — Reviewed for correctness, security, edge cases
- [ ] **E2E** — Runtime verified — app boots and change works live
- [ ] **Dogfood** — Feature exercised through the UI as a real user

### Documentation

- [ ] `README.md` updated (if applicable)
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] GitHub Wiki updated (if architecture/setup changed)

### General

- [ ] No lint errors
- [ ] No type-check errors
- [ ] All tests passing
- [ ] No security vulnerabilities introduced
