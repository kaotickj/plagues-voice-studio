"""GitHub update-checker tests. No network, Qt, downloads or model runtimes."""
import json
from pathlib import Path
import pytest

from chatterbox_studio.update_checker import (
    LATEST_RELEASE_API, UpdateCheckError, find_update,
    latest_stable_release, trusted_release_url, version_key,
)


class FakeResponse:
    def __init__(self, obj):
        self.data = json.dumps(obj).encode('utf-8')
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size=-1):
        return self.data[:size]


def fake_opener(version='v1.0.1', *, url=None, prerelease=False):
    calls = []
    def open_fn(req, *, timeout):
        calls.append((req.full_url, timeout))
        return FakeResponse({
            'tag_name': version,
            'html_url': url or ('https://github.com/kaotickj/plagues-voice-studio/releases/tag/' + version),
            'name': 'Release 1.0.1',
            'draft': False, 'prerelease': prerelease,
        })
    return open_fn, calls


@pytest.mark.parametrize('older,newer', [
    ('0.3.0a4','0.3.0rc1'),
    ('0.3.0rc1','0.3.0'),
    ('0.3.0','1.0.0'),
    ('1.0.0','1.0.1'),
    ('1.2.8','1.3.0'),
])
def test_version_sort(older,newer):
    assert version_key(older) < version_key(newer)


def test_same_version_and_older_rejected():
    opener, requests = fake_opener('v1.0.0')
    assert find_update('1.0.0', opener=opener) is None
    assert find_update('1.1.0', opener=opener) is None
    assert requests and all(url == LATEST_RELEASE_API for url, _ in requests)


def test_new_release_is_opened_only_through_official_link():
    opener, calls = fake_opener()
    info = find_update('0.3.0', opener=opener)
    assert info.version == '1.0.1'
    assert info.url == 'https://github.com/kaotickj/plagues-voice-studio/releases/tag/v1.0.1'
    assert calls == [(LATEST_RELEASE_API, 8.0)]


def test_prerelease_never_offered_as_stable():
    opener, _ = fake_opener('v2.0.0rc1', prerelease=True)
    assert latest_stable_release(opener=opener) is None


@pytest.mark.parametrize('url', [
    'http://github.com/kaotickj/plagues-voice-studio/releases/tag/v1.0.1',
    'https://evil.example/releases/tag/v1.0.1',
    'https://github.com/kaotickj/plagues-voice-studio/releases/tag/v1.0.1?token=a',
    'https://github.com/kaotickj/other-app/releases/tag/v1.0.1',
    'https://github.com/kaotickj/plagues-voice-studio/releases/tag/v1.0.1/../../other',
])
def test_untrusted_urls_refused(url):
    assert not trusted_release_url(url, 'v1.0.1')
    opener, _ = fake_opener(url=url)
    with pytest.raises(UpdateCheckError, match='unexpected release link'):
        find_update('0.3.0', opener=opener)


def test_no_stable_release_is_normal():
    from urllib.error import HTTPError
    def not_yet(req, *, timeout):
        raise HTTPError(req.full_url, 404, 'Not Found', None, None)
    assert latest_stable_release(opener=not_yet) is None


def test_empty_or_bad_release_rejected():
    for obj in ([], {}, {'tag_name':'v1.0.0','html_url':'javascript:evil()'}):
        with pytest.raises(UpdateCheckError):
            latest_stable_release(opener=lambda req,timeout: FakeResponse(obj))


def test_update_button_is_wired_but_not_automatic_by_default():
    root = Path(__file__).resolve().parents[1]
    app = (root/'src/chatterbox_studio/app.py').read_text(encoding='utf8')
    dialog = (root/'src/chatterbox_studio/update_dialog.py').read_text(encoding='utf8')
    assert 'updates_button.clicked.connect(self._show_updates)' in app
    assert 'QTimer.singleShot(1500, self._check_updates_on_start)' in app
    assert 'host.settings.value(self.SETTING, False)' in dialog
    assert 'find_update(__version__)' in dialog
    assert 'QDesktopServices.openUrl(QUrl(release.url))' in dialog
    assert 'trusted_release_url(release.url, release.tag)' in dialog
    assert 'QThread(self)' in dialog
    assert 'subprocess' not in dialog
