"""Static release-packaging regressions that need no Windows SDK/ML weights."""
from pathlib import Path
import yaml

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


def test_windows_release_tags_and_manual_builds_keep_all_publication_gates():
    workflow = (ROOT / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
    # BaseLoader keeps GitHub's YAML 1.2 `on` key as text instead of treating it
    # as the YAML 1.1 boolean understood by SafeLoader.
    parsed = yaml.load(workflow, Loader=yaml.BaseLoader)
    assert set(parsed['on']) == {'workflow_dispatch', 'push'}
    assert parsed['on']['push'] == {'tags': ['v*']}
    assert set(parsed['jobs']) == {'windows', 'installer_acceptance', 'installer_smoke', 'publish_release'}
    assert parsed['jobs']['publish_release']['needs'] == ['windows', 'installer_acceptance', 'installer_smoke']
    assert parsed['jobs']['publish_release']['if'] == "startsWith(github.ref, 'refs/tags/v')"
    publish = next(step for step in parsed['jobs']['publish_release']['steps']
                   if step.get('uses', '').startswith('softprops/action-gh-release@'))
    assert publish['with']['draft'] == 'true'
    assert "run: ./scripts/build_windows.ps1 -Slim" in workflow
    assert "PlaguesVoiceStudio-Slim-Portable.zip" in workflow
    assert "publish_release:" in workflow
    assert "needs: [windows, installer_acceptance, installer_smoke]" in workflow
    assert "installer_acceptance:" in workflow
    assert "PlaguesVoiceStudio-Installer-Acceptance-Diagnostics" in workflow
    assert "SHA256SUMS.txt" in workflow


def test_promotional_writer_keeps_manual_and_pr_checks_without_duplicate_push_jobs():
    path = ROOT / '.github' / 'workflows' / 'promotional-writer-plugin.yml'
    parsed = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    assert set(parsed['on']) == {'workflow_dispatch', 'pull_request'}
    assert parsed['on']['pull_request']['paths']
    assert set(parsed['jobs']) == {'plugin'}
