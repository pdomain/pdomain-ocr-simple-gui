#!/usr/bin/env bash
set -eu

RELEASE_REPO="pdomain/pdomain-ocr-simple-gui"
# Pinned so an environment override cannot drop the real-OCR acceptance test.
RELEASE_PREFLIGHT="just ci-slow"

. "$(dirname "$0")/release-common.sh"
pd_release_main "$@"
