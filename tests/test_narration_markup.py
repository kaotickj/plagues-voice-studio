import numpy as np
import pytest
import soundfile as sf

from chatterbox_studio.engine import Engine, apply_local_effects
from chatterbox_studio.jobs import NarrationJob
from chatterbox_studio.narration_markup import parse_script, plan_script, MarkupError


def test_native_tags_pass_unchanged():
    steps = parse_script('Hello [chuckle], there. [sigh]')
    assert len(steps) == 1
    assert steps[0].text == 'Hello [chuckle], there. [sigh]'


def test_nested_tags_restore_previous_values():
    script = '[rate:0.90]Hello [volume:0.85][emphasis]friend![/emphasis][/volume] Welcome.[/rate] Goodbye.'
    speech = [s for s in parse_script(script) if s.kind == 'speech']
    assert [s.text for s in speech] == ['Hello', 'friend!', 'Welcome.', 'Goodbye.']
    assert [(s.rate, s.volume, s.emphasis) for s in speech] == [
        (.9, 1., False), (.9, .85, True), (.9, 1., False), (1., 1., False)]


def test_explicit_pause_replaces_default_gap():
    steps = plan_script('Hello.[pause:800ms]World.', 220, 170)
    assert [x.kind for x in steps] == ['speech', 'pause', 'speech']
    assert steps[1].pause_ms == 800
    assert plan_script('Hello. World.', 60, 170)[-1].kind == 'speech'


def test_combined_pauses_and_multiline():
    steps = plan_script('First.[pause:0.2s][pause:150ms]Second.\nThird.', 60, 170)
    assert any(s.kind == 'pause' and s.pause_ms == 350 for s in steps)
    assert sum(s.kind == 'speech' for s in steps) == 3


@pytest.mark.parametrize('text', [
    '[pause:11s]x', '[pause:apple]x', '[volume:2.01]bad[/volume]',
    '[rate:0.01]bad[/rate]', '[volume:0.8]oops',
    'x[/rate]', '[rate:0.9][rate:1.1]bad[/rate][/rate]',
    '[rate:0.9][volume:0.8]bad[/rate][/volume]',
    '[emphasis:oh]x', '[pause:1]x', '[pause:1hour]x',
])
def test_reject_invalid_markup(text):
    with pytest.raises(MarkupError):
        parse_script(text)


def test_job_rejects_bad_markup():
    j = NarrationJob(text='hello [pause:unknown] there', model='english', device='cpu',
                     language='en', voice_path='', output_path='output.wav')
    with pytest.raises(MarkupError):
        j.validate()


class ConstantModel:
    sr = 8000
    conds = object()

    def __init__(self):
        self.calls = []

    def generate(self, text, **args):
        self.calls.append(text)
        return np.full((1, 800), 0.4, dtype=np.float32)


def test_render_pauses_gain_and_no_directives(tmp_path):
    model = ConstantModel()
    j = NarrationJob(text='Hello.[pause:0.8s][volume:0.5]World.[/volume]',
                     model='english', device='cpu', language='en', voice_path='',
                     output_path=str(tmp_path / 'demo.wav'), pause_ms=180, max_chars=220)
    file = Engine(model_loader=lambda *_: model).render(j, lambda *_: None, lambda *_: None, lambda: False)
    audio, rate = sf.read(file)
    assert model.calls == ['Hello.', 'World.']
    assert rate == 8000
    assert len(audio) == 800 + 6400 + 800
    assert abs(audio[0] - .4) < 1e-3
    assert not audio[800:7200].any()
    assert abs(audio[7200] - .2) < 1e-3


def test_rate_processor_changes_duration_preserving_basic_pitch():
    sr = 8000
    t = np.arange(8000) / sr
    tone = np.sin(2 * np.pi * 300 * t).astype('float32') * .25
    slowed = apply_local_effects(tone, sr, rate=.8)
    assert len(slowed) > len(tone)
    from numpy.fft import rfft, rfftfreq
    # FFT of an interior 0.4s window: frequency shift within 3%.
    center = slowed[len(slowed)//2-1600:len(slowed)//2+1600]
    peak = rfftfreq(len(center), 1 / sr)[np.abs(rfft(center)).argmax()]
    assert abs(peak - 300) < 9


def test_emphasis_is_volume_boost_not_tts_tag():
    samples = np.full(20, .5, dtype='float32')
    emphasized = apply_local_effects(samples, 8000, emphasis=True)
    assert np.allclose(emphasized, .575)


def test_opt_in_output_headroom_preserves_shape_without_clipping():
    import numpy as np
    source = np.array([-2., -1., 0., 1., 2.], dtype=np.float32)
    safe = apply_local_effects(source, 24000, peak_limit=0.891250938)
    np.testing.assert_allclose(safe, source * (0.891250938 / 2), rtol=1e-6)
    np.testing.assert_array_equal(apply_local_effects(source, 24000), [-1., -1., 0., 1., 1.])
