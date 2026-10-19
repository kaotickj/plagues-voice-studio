"""Static release-packaging regressions that need no Windows SDK/ML weights."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_slim_spec_excludes_all_model_weights_even_if_cached_in_checkout():
    spec = (ROOT / "ChatterboxStudio.spec").read_text(encoding="utf-8")
    assert "PVS_SLIM_BUILD" in spec
    assert "if os.environ.get('PVS_SLIM_BUILD') != '1':" in spec
    assert "for path in models.rglob('*')" in spec


def test_build_supports_slim_without_forcing_model_downloads():
    build = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "[switch]$Slim" in build
    assert "if (-not $SkipModels -and -not $Slim)" in build
    assert "$env:PVS_SLIM_BUILD = '1'" in build
    assert "Slim build accidentally included Chatterbox weight files" in build
    assert "if ($Slim -and ($FullOffline -or $SkipModels))" in build


def test_workflow_triggers_main_and_builds_slim_by_default():
    workflow = (ROOT / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
    assert "      - main\n" in workflow
    assert "      - develop\n" in workflow
    assert "      - 'release/**'\n" in workflow
    assert "run: ./scripts/build_windows.ps1 -Slim" in workflow
    assert "PlaguesVoiceStudio-Slim-Portable.zip" in workflow
    assert "publish_release:" in workflow
    assert "needs: [windows, installer_smoke]" in workflow
    assert "SHA256SUMS.txt" in workflow
