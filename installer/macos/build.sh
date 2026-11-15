#!/bin/sh
set -eu

SOURCE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH='' cd -- "$SOURCE/../.." && pwd)
OUT=${1:-"$ROOT/dist"}
WHEEL=${2:-}
BUNDLE="$OUT/Install OCR Simple GUI.app"
CONTENTS="$BUNDLE/Contents"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources/payload"
touch "$OUT/.nobackup"
PAYLOAD="$CONTENTS/Resources/payload"
cp "$ROOT/install.sh" "$ROOT/uninstall.sh" "$SOURCE/install-native.sh" "$SOURCE/dialog.applescript" "$PAYLOAD/"
cp "$SOURCE/../unix/native.py" "$PAYLOAD/native.py"
rm -f "$PAYLOAD/bundled-wheel.path"
if [ -n "$WHEEL" ]; then
    case "$WHEEL" in *.whl) ;; *)
        echo 'Expected a .whl file' >&2
        exit 1
        ;;
    esac
    cp "$WHEEL" "$PAYLOAD/"
    basename "$WHEEL" >"$PAYLOAD/bundled-wheel.path"
fi
cat >"$CONTENTS/MacOS/launch" <<'SCRIPT'
#!/bin/sh
set -eu
CONTENTS=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
exec /bin/sh "$CONTENTS/Resources/payload/install-native.sh"
SCRIPT
chmod +x "$CONTENTS/MacOS/launch"
cat >"$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Install OCR Simple GUI</string>
<key>CFBundleIdentifier</key><string>org.pdomain.ocr-simple-gui.installer</string>
<key>CFBundleExecutable</key><string>launch</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSUIElement</key><true/>
</dict></plist>
PLIST
printf '%s\n' "$BUNDLE"
