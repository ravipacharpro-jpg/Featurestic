#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Featurestic brand patch — idempotent.
#
# Re-applies every "this app is Featurestic, not AntiGem" change on top of the
# upstream source. Safe to run again and again; it does nothing when a change is
# already there. The upstream sync workflow runs it after every merge, so a
# conflict in a branded file is repaired instead of blocking the update.
#
# It fails loudly (exit 1) when a pattern it needs is gone, which means upstream
# refactored that file and a human must look at it.
# -----------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OWNER="ravipacharpro-jpg"
REPO="Featurestic"
NAME="Featurestic"
SLUG="featurestic"

FAILED=0
changed=0

# sub <file> <literal old> <literal new>
# Replaces a literal string (all occurrences). Prints nothing when already done.
sub() {
    local file="$1" old="$2" new="$3"
    [[ -f "$file" ]] || { echo "  ! missing file: $file" >&2; FAILED=1; return 0; }
    if grep -qF -- "$old" "$file"; then
        python3 - "$file" "$old" "$new" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, "r", encoding="utf-8") as f:
    data = f.read()
data = data.replace(old, new)
with open(path, "w", encoding="utf-8") as f:
    f.write(data)
PY
        changed=$((changed + 1))
    fi
}

# require <file> <literal>  — the branded value must be present afterwards
require() {
    local file="$1" needle="$2"
    if ! grep -qF -- "$needle" "$file"; then
        echo "  ! expected '$needle' in $file" >&2
        FAILED=1
    fi
}

echo "→ branding as $NAME ($OWNER/$REPO)"

# --- app name (launcher, accessibility, About) -------------------------------
sub app/src/main/res/values/strings.xml ">AntiGem<" ">$NAME<"
sub app/src/main/res/values/strings.xml "AntiGem Android Automation" "$NAME Android Automation"
sub app/src/main/res/values/strings.xml "AntiGem\\'s Android Automation MCP" "$NAME\\'s Android Automation MCP"

# --- in-app updater: where updates are checked and downloaded from -----------
sub app/src/main/java/com/example/gemini/data/updater/AppUpdateManager.kt \
    "raw.githubusercontent.com/santoshkurmi/antigem/" \
    "raw.githubusercontent.com/$OWNER/$REPO/"
sub app/src/main/java/com/example/gemini/data/updater/AppUpdateManager.kt \
    "github.com/santoshkurmi/antigem/releases/download/v\$remoteVersionName/antiGem-" \
    "github.com/$OWNER/$REPO/releases/download/v\$remoteVersionName/$SLUG-"

# --- About screen links ------------------------------------------------------
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    "https://github.com/santoshkurmi/antigem/releases" \
    "https://github.com/$OWNER/$REPO/releases"
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    "https://github.com/santoshkurmi/antigem" \
    "https://github.com/$OWNER/$REPO"
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    "github.com/santoshkurmi/antigem" \
    "github.com/$OWNER/$REPO"
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    'contentDescription = "AntiGem"' \
    "contentDescription = \"$NAME\""
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    'text = "AntiGem"' \
    "text = \"$NAME\""
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    '"AntiGem is up to date' \
    "\"$NAME is up to date"
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    '"AntiGem connects via gRPC-Web' \
    "\"$NAME connects via gRPC-Web"
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    're-open AntiGem to start fresh' \
    "re-open $NAME to start fresh"
sub app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt \
    '"AntiGem is wiping all local app data' \
    "\"$NAME is wiping all local app data"

# --- update dialog repo link -------------------------------------------------
sub app/src/main/java/com/example/gemini/ui/updater/AppUpdateDialog.kt \
    "https://github.com/santoshkurmi/antigem" \
    "https://github.com/$OWNER/$REPO"

# --- APK file names (must match the download URL above) ----------------------
sub scripts/build_all_apks.sh "antiGem-" "$SLUG-"
sub app/build.gradle.kts 'archivesName.set("antiGem")' "archivesName.set(\"$SLUG\")"

# --- analytics ---------------------------------------------------------------
# Upstream disables analytics on any APK not signed with its own key and shows a
# long "Unofficial build" toast on every launch. Featurestic sends nothing, and
# the toast goes away with the whole block.
python3 - <<'PY'
import re, pathlib
p = pathlib.Path("app/src/main/java/com/example/gemini/AntiGemApplication.kt")
s = p.read_text(encoding="utf-8")
if "Featurestic: analytics disabled" not in s:
    start = s.find("        // Forks build with their own key")
    end = s.find("    private fun isOfficialRelease()")
    if start == -1 or end == -1:
        raise SystemExit("  ! telemetry block not found in AntiGemApplication.kt")
    s = s[:start] + "        // Featurestic: analytics disabled. Nothing is sent from this build.\n    }\n\n" + s[end:]
    p.write_text(s, encoding="utf-8")
    print("  · analytics block removed")
PY

# --- attribution (GPL-3.0) ---------------------------------------------------
if [[ ! -f NOTICE ]]; then
    cat > NOTICE <<EOF
$NAME is a modified build of AntiGem.

  Original work: AntiGem — Copyright (C) 2026 Santosh Kurmi
  https://github.com/Santoshkurmi/antigem
  Licensed under the GNU General Public License v3.0 or later.

Changes in this repository: rebranding (name, icon, splash, links), the update
channel (GitHub releases of $OWNER/$REPO), analytics removed, and small UI fixes.
This is not an official AntiGem release and is not endorsed by its author.

Source code: https://github.com/$OWNER/$REPO
EOF
    echo "  · NOTICE written"
fi

# --- user-visible text -------------------------------------------------------
# Every "AntiGem" that is not a code identifier becomes "Featurestic". The
# lookahead keeps class names (AntiGemApplication, AntiGemTerminal, …) and the
# "Theme.AntiGem.FloatingTranslucent" style name untouched.
python3 - <<'PY'
import pathlib, re

WORD = re.compile(r"(?<![A-Za-z0-9_])AntiGem(?!\w)(?!\.[A-Za-z])")
files = list(pathlib.Path("app/src/main/java").rglob("*.kt"))
files += list(pathlib.Path("app/src/main/res").rglob("*.xml"))
files += list(pathlib.Path("app/src/main/assets/browser-runtime").rglob("*.mjs"))
files.append(pathlib.Path("app/src/main/AndroidManifest.xml"))

changed = 0
for p in files:
    if not p.exists():
        continue
    s = p.read_text(encoding="utf-8")
    n = WORD.sub("Featurestic", s)
    n = n.replace("antiGem-termux-shared-", "featurestic-termux-shared-")
    if n != s:
        p.write_text(n, encoding="utf-8")
        changed += 1
print(f"  · {changed} source file(s) rebranded")
PY

# --- icon + splash -----------------------------------------------------------
# Regenerated from scripts/brand/logo.jpg so an upstream merge can never bring
# back the AntiGem prism icon or splash.
if [[ -f scripts/brand/logo.jpg ]]; then
    python3 scripts/make_brand_assets.py > /dev/null
    echo "  · icon and splash regenerated"
fi

# --- README ------------------------------------------------------------------
python3 - <<'PY'
import pathlib

p = pathlib.Path("README.md")
if p.exists():
    s = p.read_text(encoding="utf-8")
    if "<!-- featurestic-banner -->" not in s:
        banner = (
            "<!-- featurestic-banner -->\n"
            "> **Featurestic** is a rebranded build of [AntiGem](https://github.com/Santoshkurmi/antigem)\n"
            "> by Santosh Kurmi, published under the GPL-3.0. It is not an official AntiGem release.\n"
            "> Downloads and updates for this build come from this repository.\n\n"
        )
        s = banner + s
        s = s.replace("# AntiGem\n", "# Featurestic\n", 1)
        s = s.replace("docs/readme/icon.svg", "docs/readme/featurestic.png")
        s = s.replace("alt=\"AntiGem app icon\"", "alt=\"Featurestic app icon\"")
    s = s.replace("santoshkurmi/antigem/releases", "ravipacharpro-jpg/Featurestic/releases")
    s = s.replace("github/v/release/santoshkurmi/antigem",
                  "github/v/release/ravipacharpro-jpg/Featurestic")
    s = s.replace("https://santoshkurmi.github.io/antigem/",
                  "https://github.com/ravipacharpro-jpg/Featurestic")
    s = s.replace("git clone https://github.com/santoshkurmi/antigem.git",
                  "git clone https://github.com/ravipacharpro-jpg/Featurestic.git")
    p.write_text(s, encoding="utf-8")
    print("  · README branded")
PY

# --- verify ------------------------------------------------------------------
require app/src/main/res/values/strings.xml ">$NAME<"
require app/src/main/java/com/example/gemini/data/updater/AppUpdateManager.kt "raw.githubusercontent.com/$OWNER/$REPO/"
require app/src/main/java/com/example/gemini/data/updater/AppUpdateManager.kt "github.com/$OWNER/$REPO/releases/download"
require app/src/main/java/com/example/gemini/ui/settings/SettingsDialog.kt "github.com/$OWNER/$REPO"
require scripts/build_all_apks.sh "$SLUG-termux"
require app/src/main/java/com/example/gemini/AntiGemApplication.kt "Featurestic: analytics disabled"

if [[ "$FAILED" -ne 0 ]]; then
    echo "✗ brand patch incomplete — upstream changed something, fix apply_brand.sh" >&2
    exit 1
fi

echo "✓ brand patch applied ($changed replacement(s))"
