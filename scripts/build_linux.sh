#!/usr/bin/env bash
# Native x86-64 Linux build. No model weights or optional Python runtimes.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo 'Build on x86-64 Linux with Python 3.12.' >&2
    exit 1
fi
python_bin="${PVS_BUILD_PYTHON:-python3.12}"
if [[ ! -x .venv-linux-build/bin/python ]]; then
    "$python_bin" -m venv .venv-linux-build
fi
python="$PWD/.venv-linux-build/bin/python"
export PATH="$PWD/.venv-linux-build/bin:$PATH"
"$python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'
"$python" -m pip install --no-deps pip==26.2.1 setuptools==84.0.0 wheel==0.48.0 packaging==26.3 uv_build==0.12.7
"$python" -m pip install --no-cache-dir --no-deps --no-build-isolation \
    --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-release.txt
"$python" -m pip install --no-deps --no-build-isolation -e '.[build,test]'
"$python" -m pip check
"$python" scripts/check_release_version.py
export QT_QPA_PLATFORM=offscreen
"$python" -m pytest -q
export PVS_SLIM_BUILD=1
# Separate paths preserve any Windows or previous release output in this checkout.
"$python" -m PyInstaller --clean --noconfirm --distpath dist/linux --workpath build/linux ChatterboxStudio.spec
app="$PWD/dist/linux/PlaguesVoiceStudio030Experimental"
mkdir -p build/linux/diagnostics
for mode in self-test ui-self-test; do
    timeout 180 "$app/PlaguesVoiceStudio030Experimental" "--$mode" "$PWD/build/linux/diagnostics/$mode.json"
done
"$python" scripts/verify_frozen_source.py --exe "$app/PlaguesVoiceStudio030Experimental" \
    --report build/linux/diagnostics/source-check.json
"$python" scripts/package_linux.py --app "$app" --output artifacts/linux
