"""Release identity, immutable toolchain and install-isolation contracts."""
from pathlib import Path
import tomllib
import sys
import pytest
from chatterbox_studio import __version__

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from check_release_version import check_release_identity


@pytest.mark.parametrize('tag', ['v1.0.0', 'v0.3.0', 'v1.0.0rc2'])
def test_mislabeled_release_tags_are_blocked(tag):
    with pytest.raises(ValueError, match='Expected tag'):
        check_release_identity(ROOT, tag)


def test_matching_rc_tag_is_allowed():
    assert check_release_identity(ROOT, 'v1.0.0rc1') == '1.0.0rc1'


def test_rc_version_matches_package_installer_and_windows_metadata():
    package = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
    assert __version__ == '1.0.0rc1' == package['project']['version']
    assert f'#define AppVersion "{__version__}"' in (ROOT/'installer.iss').read_text()
    assert f"'ProductVersion', '{__version__}'" in (ROOT/'assets/version_info.txt').read_text()


def test_release_dependency_lock_uses_commit_refs_not_master_or_this_checkout():
    lock = (ROOT/'requirements-release.txt').read_text()
    assert '@master' not in lock and '\n-e ' not in lock
    assert 'torch==2.6.0+cpu' in lock
    assert 'chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2' in lock
    assert 'Perth.git@ff1c8ac55a976971245cdd53c18d6131ca00d993' in lock
    assert 'plagues-voice-studio.git' not in lock
    build = (ROOT/'scripts/build_windows.ps1').read_text()
    assert '--no-deps' in build and '-r requirements-release.txt' in build
    assert '-m pip check' in build and '-m pytest -q' in build


def test_installer_retains_upgrade_identity_and_isolates_acceptance_installs():
    installer = (ROOT/'installer.iss').read_text()
    assert '2CC3087C-D88B-47D6-AF68-A949593B7BF2' in installer
    assert 'BF786FC2-C388-4F32-B3E2-EFD9D0CE488C' in installer
    assert r"DefaultDirName={localappdata}\Programs\Plague's Voice Studio 0.3 Experimental" in installer
    assert '#ifndef AcceptanceBuild\n[InstallDelete]' in installer
    assert 'DestDir: "{app}"' in installer
    assert '[UninstallDelete]' not in installer
