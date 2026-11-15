#!/bin/sh
set -eu

# Uninstall pdomain-ocr-simple-gui without removing shared dependencies or data.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh
#
# Unattended app removal (uv itself is always preserved):
#   curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh -s -- -y
#   ASSUME_YES=1 curl -sSL https://raw.githubusercontent.com/pdomain/pdomain-ocr-simple-gui/master/uninstall.sh | sh

ASSUME_YES="${ASSUME_YES:-0}"

usage() {
	printf '%s\n' 'Usage: uninstall.sh [-y|--yes]'
	printf '%s\n' '  -y, --yes  Remove only pdomain-ocr-simple-gui without an interactive prompt.'
	printf '%s\n' '             uv, its Python installations, other uv tools, caches, drivers, and data stay.'
}

for arg in "$@"; do
	case "$arg" in
	-y | --yes) ASSUME_YES=1 ;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		usage >&2
		exit 64
		;;
	esac
done

# A piped installer script has no terminal on standard input.  Probe the
# controlling terminal in a subshell before opening it in this shell: dash
# exits if an unsuccessful redirection is attempted directly in an if body.
HAS_TTY=0
if sh -c "exec 3</dev/tty" 2>/dev/null; then
	exec 3</dev/tty
	HAS_TTY=1
fi

# prompt_yn "Question?" "N" returns zero only for an explicit yes.  A
# non-interactive run without -y cannot confirm a destructive action.
prompt_yn() {
	prompt=$1
	default=$2
	if [ "$ASSUME_YES" = "1" ]; then
		return 0
	fi
	if [ "$HAS_TTY" != "1" ]; then
		return 1
	fi
	hint="[y/N]"
	if [ "$default" = "Y" ]; then
		hint="[Y/n]"
	fi
	printf '%s %s ' "$prompt" "$hint" >/dev/tty
	if IFS= read -r answer <&3; then
		:
	else
		answer=""
	fi
	if [ -z "$answer" ]; then
		answer=$default
	fi
	case "$answer" in
	y | Y | yes | YES) return 0 ;;
	*) return 1 ;;
	esac
}

printf '%s\n' 'This removes only pdomain-ocr-simple-gui.'
printf '%s\n' 'uv, its Python installations, other uv tools, model caches, drivers, and user data are preserved.'
printf '%s\n' 'Close any running app before continuing. This script does not stop processes; press Ctrl+C to cancel.'

if ! prompt_yn "Remove pdomain-ocr-simple-gui?" "N"; then
	printf '%s\n' 'Cancelled. No changes were made.'
	exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
	printf '%s\n' 'uv is not on PATH, so pdomain-ocr-simple-gui was not removed.'
	printf '%s\n' 'No shortcut or suite-registry changes were made.'
	exit 0
fi

# The app command owns its shortcut and suite registration.  Run those cleanup
# operations only after confirmation, and stop if either native operation fails.
if command -v pdomain-ocr-simple-gui >/dev/null 2>&1; then
	printf '%s\n' 'Removing desktop shortcut...'
	if pdomain-ocr-simple-gui --remove-desktop-shortcut; then
		:
	else
		status=$?
		printf '%s\n' 'Could not remove the desktop shortcut; the app was not uninstalled.' >&2
		exit "$status"
	fi

	printf '%s\n' 'Unregistering from the suite registry...'
	if pdomain-ocr-simple-gui --unregister-suite; then
		:
	else
		status=$?
		printf '%s\n' 'Could not unregister the app; the app was not uninstalled.' >&2
		exit "$status"
	fi
else
	printf '%s\n' 'pdomain-ocr-simple-gui is not on PATH; its shortcut and registry entry were left unchanged.'
fi

printf '%s\n' 'Uninstalling pdomain-ocr-simple-gui...'
if uv tool uninstall pdomain-ocr-simple-gui; then
	:
else
	status=$?
	printf '%s\n' 'uv could not uninstall pdomain-ocr-simple-gui.' >&2
	exit "$status"
fi

printf '%s\n' 'pdomain-ocr-simple-gui removed.'
printf '%s\n' 'Keeping uv, its Python installations, and other uv tools.'
printf '%s\n' ''
printf '%s\n' 'Preserved data and dependencies:'
printf '%s\n' '  uv, its managed Python installations, and every other uv tool remain installed.'
printf '%s\n' '  OCR model caches and system graphics or GPU drivers remain installed.'
printf '%s\n' '  Shared suite preferences and registry data remain in the platform-specific suite data directory.'
printf '%s\n' '    PD_SUITE_DATA_DIR, when set, selects that shared location; other pdomain apps may use it.'
printf '%s\n' "  Projects default to \$HOME/.local/share/pdomain-suite/simple-gui/projects."
printf '%s\n' '    PD_OCR_SIMPLE_GUI_PROJECTS_ROOT or the app\047s Jobs location preference can select another location.'
printf '%s\n' '  App-managed outputs, uploads, and job metadata default to:'
printf '%s\n' "    \$HOME/.local/share/pdomain-ocr-simple-gui/outputs"
printf '%s\n' "    \$HOME/.local/share/pdomain-ocr-simple-gui/uploads"
printf '%s\n' "    \$HOME/.local/share/pdomain-ocr-simple-gui/jobs"
printf '%s\n' '    Their overrides are PD_OCR_SIMPLE_GUI_OUTPUT_ROOT, PD_OCR_SIMPLE_GUI_UPLOAD_ROOT,'
printf '%s\n' '    and PD_OCR_SIMPLE_GUI_JOBS_META_ROOT.'
printf '%s\n' '  If you downloaded the AppImage installer, its single file is at:'
printf '%s\n' "    \$HOME/.local/bin/pdomain-ocr-simple-gui-installer.AppImage"
printf '%s\n' 'Review those locations individually before removing anything.'
