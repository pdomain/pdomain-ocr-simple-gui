"""Cross-module constants for pdomain-ocr-simple-gui.

Kept separate from any single route/app module so both the suite mount
(``app.py``) and the app-scoped prefs routes (``routes/jobs.py``) reference
the exact same value — a divergent copy is how prefs ended up split across
two keys in the past (ocr-container-meta review-fixes plan, Task 18).
"""

from __future__ import annotations

#: The app_id this process registers under in the pdomain-suite registry and
#: persists its own prefs section under (``UIPrefs.apps[APP_ID]``). Must match
#: ``app_id`` in the bundled ``pdomain-suite.json`` fragment.
APP_ID = "pdomain-ocr-simple-gui"
