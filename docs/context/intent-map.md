---
Status: active
Owner: CT
Created: 2026-07-13
Last verified: 2026-07-13
Kind: context
---

# Intent map

## Agent Index

- **Kind:** context
- **Status:** active
- **Read when:** deciding whether to expand deployment or packaging scope.
- **Search terms:** intent, hosted deployment, Windows, macOS, packaging.

## Active bets

None.

## Deferred work

- **Hosted deployment — deferred.** The app ships local and managed mode
  selection, capability-token protection through `PDOMAIN_API_TOKEN`, and
  managed-mode source/output restrictions. It does not ship a hosted service,
  hosted persistence, account model, or production deployment contract. Owner:
  a future hosted-product maintainer. Start only after a consumer and threat
  model are approved.
- **Windows and macOS packaging — deferred.** The supported installer path is
  Linux/browser-first. Shortcut helpers report unsupported platforms rather
  than pretending Windows or macOS installers exist. Owner: platform packaging
  maintainers. Require platform-native install, uninstall, launch, and upgrade
  tests before support is claimed.

## Rejected directions

- Do not describe authentication or mode selection as wholly unbuilt. Token
  auth and local/managed branching already ship in `auth.py`, `runtime/mode.py`,
  route guards, and their tests.

## Blocked (waiting on)

None.

## Needs owner decision

None.
