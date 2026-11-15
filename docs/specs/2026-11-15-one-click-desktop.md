---
Status: draft
Owner: CT
Created: 2026-11-15
Last verified: 2026-11-15
Kind: spec
---

# Install, run and remove OCR Simple GUI without a terminal

## Agent Index

- **Kind:** spec
- **Status:** draft
- **Read when:** implementing the owner's one-click desktop goal.
- **Search terms:** installer, launcher, uninstall, heartbeat, multiple tabs, storage migration, PWA.

## Outcome and authority

Users install, launch and uninstall the browser-based OCR app through desktop controls on Windows,
macOS and Linux. The owner requested iterative implementation on 2026-11-15 and asked us to keep
working. Ordinary use should require no terminal. Normal operating-system consent prompts remain.

The app-side session owns this work. The guide worker retains exclusive ownership of
`/mnt/work/projects/pdomain/.worktrees/gui-walkthrough`. Publishing, releases and paid signing
services still need separate authorization. This spec describes work in progress, not released behavior.

## Approaches and selected design

Keep the browser application and add native installation and launch controls. A lightweight launcher
starts the backend once, opens the UI and handles a second launch. Windows uses a graphical executable.
macOS uses application bundles, and Linux uses the existing AppImage installer and desktop entries.
Each platform also gets a graphical uninstall entry. The native controls run the same tested installation
and removal operations as the command-line scripts.

A browser-only installation would still need something to start the Python backend. Replacing the
browser with a native webview would change the requested multiple-tab experience. The selected design
keeps the current app and supplies the missing desktop behavior. This is the implementer's choice
within the owner's request.

Build working local artifacts before signing or publication work. Do not claim that an unpublished
script URL or unsigned download is a finished public installation experience.

## App-owned data and suite integration

The app owns its configuration, projects, uploads, managed outputs, metadata, runtime records and
logs. Its default data folder uses the platform's user-data location for `pdomain-ocr-simple-gui`.
The data folder contains `projects/`, `uploads/`, `outputs/` and `jobs/`. A stable app configuration
file outside that relocatable folder records its location. Runtime locks and active logs remain in
the app's state location so a data move cannot move a live lock.

The suite retains installed-app registration and shared integration settings. Per-app settings and
actual OCR documents do not belong under the suite folder. Preserve unrelated apps and shared
preferences when moving this app's settings out of the shared preference file.

Settings presents one app-data folder and a model-cache choice. It also shows effective paths,
including environment overrides. Installation, managed Python and package-cache locations are
displayed for reference; uv and the installer continue to own them. Per-job output-folder choices
remain available. Existing explicit environment variables take precedence and are shown as overrides.

Changing app-data location must offer a safe move of existing app-owned data. Refuse moves during
active work, uploads or another move. Reject overlapping paths, unexpected nonempty destinations and
symlink escapes. Copy and verify before changing the saved location. Failure leaves the old location
authoritative. Preserve the originals until the move is confirmed complete; report any retained backup.

Legacy discovery includes the old suite `simple-gui/projects` directory and the separate app upload,
output and job-metadata roots. Rebase only references to relocated app-owned files. Never rewrite or
delete original source folders or arbitrary specified output folders. A custom jobs folder can contain
unrelated files, so discovery and migration must select valid app project directories only.

Model providers can read cache locations at import time. Save their requested location and apply it
before loading those providers on the next launch. Show a restart-required state and the currently
effective location. Never silently switch a loaded predictor between cache roots.

## Job deletion and uninstall preserve user work

Deleting a job may remove its canonical project and app metadata. It may remove its managed output
mirror only when both its stored mode and resolved path establish that the app owns that job's mirror.
Missing metadata, specified output folders, source folders, the output root itself and symlink escapes
must be preserved. Do not implement uninstall cleanup by calling the job-deletion API.

Uninstall asks for confirmation before changing anything. It stops only this app's verified process
and removes this app's registration before removing its tool environment. Keep the removal control
and manifest until finalization succeeds, so Retry still works after the tool environment is gone.
Then remove this app's desktop controls. Cancellation and failures are visible. An already-removed
app is handled without reinstalling dependencies.

Keep projects, original scans, uploaded copies, outputs, shared uv, managed Python, model caches,
Visual C++ and GPU drivers by default. Show retained paths. Removing data requires a separate explicit
choice and must never recursively delete arbitrary saved source or output paths.

After removing this app, clean up known suite integration files only when no other suite app remains.
Check the unpruned registration file and every installed environment under the directory returned by
`uv tool dir`. Inspect its distribution file manifests for `pdomain-suite.json`; a tool containing that
file owns suite integration even if it has never registered. An unreadable manifest, registry or tool
inventory makes ownership uncertain;
retain shared files in that case. Never use a registry API that silently prunes stale entries for this
decision. Tests cover an installed but unregistered app and every inventory failure.
Preserve unknown files, shared work and legacy project backups.
Remove the suite directory only if it is then empty. Never delete a lock that another process holds.

## One backend and multiple browser tabs

The launcher serializes startup through an app-owned lock. It validates an existing instance using
its app identity and an instance secret, not a PID or a port alone. A second launch reuses that server.
If no UI client acknowledges a request to show the app, the launcher opens its URL once.

The state directory contains a private `instance.json` record with schema version, app ID, random
instance ID, PID, loopback origin and a 256-bit random capability. Use owner-only permissions on POSIX
and the current user's inherited private profile ACL on Windows. Hold an OS advisory startup lock
until discovery or startup finishes; publish the complete record through atomic replacement. The
server holds a separate lifetime lock. Never replace or remove another instance's record. Discovery
sends the capability in an authorization header and a random challenge; the server returns its app
ID, instance ID and that challenge. A successful TCP connection alone is insufficient. On failed
discovery, retry while the lifetime lock is held; report an unresponsive instance rather than kill it.
Replace a stale record only after obtaining the lifetime lock. Test startup races, wrong challenges,
wrong capabilities, malformed records, reused PIDs and occupied ports.

Browser bootstrap requires a loopback Host and same-origin request before setting a private,
HttpOnly, SameSite=Strict session cookie. Mutating lifecycle requests and WebSocket handshakes must
also carry the matching Origin and that cookie. Do not expose the runtime capability to browser code.
Tests must reject cross-origin bootstrap, commands and socket handshakes.

Each loaded page owns a distinct server lease. A WebSocket connection is preferred so background-tab
timer throttling does not cause shutdown. Application heartbeats and reconnects recover from network
interruptions. Closing one tab leaves the server running while any other tab remains.

Generate a fresh random lease ID in memory for each page load, including duplicated tabs. The server
keys leases by its instance ID and that page ID, and assigns a connection generation on each attach.
A replacement connection supersedes its predecessor; a late disconnect from the predecessor cannot
remove the replacement. Only live connections count. Protocol ping/pong detects dead sockets, with a
60-second timeout. Disconnection starts the last-tab grace only after that detection; reconnect before
the deadline cancels it. A restarted server rejects the old instance ID and forces fresh bootstrap.
Use one server lock and a monotonic clock for lease changes, activity changes and the shutdown
decision. Recheck both live connections and activity under that lock immediately before exit.

After the last connection disappears, wait 30 seconds before shutdown. A reconnect cancels the pending
shutdown. Initial launch allows 120 seconds for a browser to connect. Running OCR, uploads, reruns,
saves, model downloads and data moves defer automatic shutdown until they finish. No closed-tab event
is assumed to arrive reliably. The server owns the decision and shuts down gracefully.

Provide a Quit app button. It reports other tabs and refuses to discard active work silently. Closing
one browser tab is not an instruction to cancel a job. An explicit headless launch remains persistent;
automatic exit applies to desktop-managed instances. Settings can keep a desktop instance running.

Native launcher commands require the current instance capability in an authorization header. Browser
lifecycle commands instead require the session cookie and same-origin checks described above; they
never receive the launcher capability. Keep secrets out of URLs and logs. Bind local desktop instances
to loopback. A stale runtime record cannot authorize
stopping an unrelated process. A new launch must recover from a crashed backend without killing by name.

## Browser install and focus limits

The native installer creates the app icon; browser installation is optional. When supported, an
in-app Install control can invoke the browser's installation prompt after a user click. It cannot
accept that prompt automatically. The browser controls final consent.

An installed browser app can request `focus-existing` launch handling where supported. Ordinary
browser tabs cannot be focused reliably across every browser from an external launcher. Treat focus
as best effort and avoid duplicate server processes regardless of browser behavior. Do not advertise
a browser-installed icon as an independent backend starter. Until cold-launch recovery is implemented,
do not offer an in-app browser Install button. Existing browser-installed icons require starting the
native app icon first; explain this in the installer and launch help. A future Install button requires
an offline service-worker recovery page that remains reachable with the backend stopped and opens
a registered native launch URI only after a click. Test that cold launch before enabling the button.

References: [installation prompt](https://developer.mozilla.org/en-US/docs/Web/API/BeforeInstallPromptEvent/prompt),
[launch handling](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/launch_handler),
and [focus behavior](https://developer.mozilla.org/en-US/docs/Web/API/Window/focus).

## Acceptance and operating limits

For each platform, independently verify install, launch, shutdown and uninstall. Use the native
Windows VM, Linux gui-sandbox and a native macOS runner or machine. Cross-compilation and shell tests
alone do not prove a graphical installation works. Keep lack of macOS access or publication authority
visible as a platform-specific deficit while continuing authorized work elsewhere.

Tests cover a second launch, two tabs, refresh, disconnect and reconnect, crashed/stale instances,
active jobs, cancellation, failed installs, upgrades, changed data roots, failed migration, last-app
and other-app uninstall, and preservation of external files. Run real CPU OCR after installing the
actual artifact. Keep GPU selection tests separate from native GPU execution evidence.

Use no paid calls or services without authorization. Serialize full CI and other heavy checks;
use at most four test workers and two CPU threads per native OCR process. Bound subprocess checks
and record their actual results. No unbounded background producers, automatic reboots or live
publishing are authorized by this design.

The execution order and completion records are in
[the implementation plan](../plans/2026-11-15-one-click-desktop.md).

## Adversarial Review

Independent design review identified gaps in shared-suite ownership, instance authentication,
lease reconnection, browser-installed recovery and native artifact contracts. The design now
defines those contracts and defers the browser Install button until cold-launch recovery works.
A focused recheck found no actionable findings. Implementation and native acceptance remain
tracked in the implementation plan.
