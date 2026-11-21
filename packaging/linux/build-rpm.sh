#!/usr/bin/env bash
# Byg en RPM af Ordhjælp:  packaging/linux/build-rpm.sh
# Kræver: rpm-build og uv. Resultatet lægges i build/rpm/.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
UV=${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)
WORK="$ROOT/build/rpm"
STAGE="$WORK/stage"
APP="$STAGE/opt/ordhjaelp"
APP_ID=dk.ordhjaelp.Ordhjaelp

STAGE_ONLY=${STAGE_ONLY:-0}  # 1 = saml kun filerne (til test), byg ikke RPM
# rpmbuild køres lokalt, hvis det findes – ellers i en Fedora-container med podman
if [ "$STAGE_ONLY" != 1 ] && ! command -v rpmbuild >/dev/null && ! command -v podman >/dev/null; then
    echo "Mangler rpmbuild (sudo dnf install rpm-build) eller podman" >&2
    exit 1
fi

echo "==> Ordhjælp $VERSION"
rm -rf "$WORK"
mkdir -p "$APP" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps"

echo "==> Kopierer Python 3.13 (uv-styret, flytbar)"
"$UV" python install 3.13 >/dev/null
PY_HOME=$("$UV" run --project "$ROOT" --python 3.13 python -c 'import sys; print(sys.base_prefix)')
cp -a "$PY_HOME" "$APP/python"
PY="$APP/python/bin/python3"
# Fjern dele af standardbiblioteket, som Ordhjælp ikke bruger
rm -rf "$APP"/python/lib/python3.13/{test,idlelib,tkinter,turtledemo,ensurepip,lib2to3} \
       "$APP"/python/lib/{libtcl,libtk}* "$APP"/python/lib/{tcl,tk}* 2>/dev/null || true
rm -f "$APP"/python/lib/python3.13/EXTERNALLY-MANAGED

echo "==> Installerer Ordhjælp og afhængigheder (låste versioner fra uv.lock)"
"$UV" export --project "$ROOT" --frozen --no-dev --no-hashes --no-emit-project \
    -o "$WORK/requirements.txt" >/dev/null
"$UV" pip install --python "$PY" --no-cache -q -r "$WORK/requirements.txt"
"$UV" pip install --python "$PY" --no-cache -q --no-deps "$ROOT"
"$PY" -m compileall -q -j0 "$APP/python/lib/python3.13/site-packages" >/dev/null || true

echo "==> Programstarter, menupunkt og ikon"
cat > "$STAGE/usr/bin/ordhjaelp" <<'SH'
#!/bin/sh
exec /opt/ordhjaelp/python/bin/python3 -m ordhjaelp "$@"
SH
chmod 755 "$STAGE/usr/bin/ordhjaelp"
sed 's|@EXEC@|/usr/bin/ordhjaelp|' \
    "$ROOT/src/ordhjaelp/platform/linux/data/$APP_ID.desktop" \
    > "$STAGE/usr/share/applications/$APP_ID.desktop"
cp "$ROOT/src/ordhjaelp/ui/icons/ordhjaelp.svg" \
   "$STAGE/usr/share/icons/hicolor/scalable/apps/$APP_ID.svg"

if [ "$STAGE_ONLY" = 1 ]; then
    echo "==> Filerne er samlet i $STAGE ($(du -sh "$STAGE" | cut -f1))"
    exit 0
fi

echo "==> Bygger RPM ($(du -sh "$STAGE" | cut -f1) ukomprimeret)"
RPMBUILD_ARGS=(-bb "$ROOT/packaging/linux/ordhjaelp.spec"
    --define "_topdir $WORK/rpmbuild"
    --define "stage $STAGE"
    --define "ordhjaelp_version $VERSION"
    --define "_binary_payload w19.zstdio"
    --quiet)
if command -v rpmbuild >/dev/null; then
    rpmbuild "${RPMBUILD_ARGS[@]}"
else
    FEDORA=$(rpm -E %fedora)
    echo "    (rpmbuild findes ikke – bruger en Fedora $FEDORA-container)"
    podman run --rm --security-opt label=disable -v "$ROOT:$ROOT" \
        "registry.fedoraproject.org/fedora:$FEDORA" \
        bash -c 'dnf -y -q install rpm-build >/dev/null && rpmbuild "$@"' rpmbuild "${RPMBUILD_ARGS[@]}"
fi
RPM=$(find "$WORK/rpmbuild/RPMS" -name '*.rpm' | head -1)
cp "$RPM" "$WORK/"
echo "==> Færdig: $WORK/$(basename "$RPM") ($(du -h "$RPM" | cut -f1))"
