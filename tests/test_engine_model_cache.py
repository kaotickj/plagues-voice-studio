"""Model-cache recovery with synthetic loaders; no ML runtime is imported."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from chatterbox_studio.engine import Engine


@pytest.fixture
def cuda_cache(monkeypatch):
    empty_cache = Mock()
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        cuda=SimpleNamespace(empty_cache=empty_cache)))
    return empty_cache


def test_failed_gpu_load_invalidates_old_cpu_key_and_conditioning(cuda_cache):
    old_builtin, old_reference, new_builtin = object(), object(), object()
    old_cpu = SimpleNamespace(conds=old_builtin)
    new_cpu = SimpleNamespace(conds=new_builtin)
    calls = []

    def load(model_id, device):
        # Replacement state must be invalid even while the loader is running.
        assert (engine.model_key, engine.model, engine.builtin_voice) == (None, None, None)
        calls.append((model_id, device))
        if device == "cuda":
            raise RuntimeError("synthetic GPU load failure")
        return old_cpu if len(calls) == 1 else new_cpu

    engine = Engine(model_loader=load)
    assert engine._get_model("english", "cpu", lambda _: None) is old_cpu
    old_cpu.conds = old_reference

    with pytest.raises(RuntimeError, match="synthetic GPU load failure"):
        engine._get_model("english", "cuda", lambda _: None)

    assert (engine.model_key, engine.model, engine.builtin_voice) == (None, None, None)
    assert calls == [("english", "cpu"), ("english", "cuda")]
    # Returning to CPU is an explicit request, not a silent retry by the engine.
    assert engine._get_model("english", "cpu", lambda _: None) is new_cpu
    assert engine.model_key == ("english", "cpu")
    assert engine.builtin_voice is new_builtin
    assert new_cpu.conds is new_builtin
    assert old_cpu.conds is old_reference
    assert calls == [("english", "cpu"), ("english", "cuda"), ("english", "cpu")]
    cuda_cache.assert_called_once_with()


def test_failed_gpu_load_can_retry_gpu_then_reuse_successful_cache(cuda_cache):
    builtin = object()
    model = SimpleNamespace(conds=builtin)
    loader = Mock(side_effect=[RuntimeError("first load failed"), model])
    engine = Engine(model_loader=loader)

    with pytest.raises(RuntimeError, match="first load failed"):
        engine._get_model("turbo", "cuda", lambda _: None)
    assert (engine.model_key, engine.model, engine.builtin_voice) == (None, None, None)

    assert engine._get_model("turbo", "cuda", lambda _: None) is model
    assert engine._get_model("turbo", "cuda", lambda _: None) is model
    assert engine.model_key == ("turbo", "cuda")
    assert engine.builtin_voice is builtin
    assert loader.call_args_list == [call("turbo", "cuda"), call("turbo", "cuda")]
    assert cuda_cache.call_count == 2


def test_gpu_cache_cleanup_failure_also_invalidates_previous_cpu_cache(cuda_cache):
    old_model = SimpleNamespace(conds=object())
    new_model = SimpleNamespace(conds=object())
    loader = Mock(side_effect=[old_model, new_model])
    engine = Engine(model_loader=loader)
    engine._get_model("english", "cpu", lambda _: None)
    cuda_cache.side_effect = RuntimeError("synthetic GPU cleanup failure")

    with pytest.raises(RuntimeError, match="synthetic GPU cleanup failure"):
        engine._get_model("english", "cuda", lambda _: None)
    assert (engine.model_key, engine.model, engine.builtin_voice) == (None, None, None)
    assert loader.call_count == 1

    assert engine._get_model("english", "cpu", lambda _: None) is new_model
    assert engine.builtin_voice is new_model.conds
    assert loader.call_args_list == [call("english", "cpu"), call("english", "cpu")]


def test_cache_hit_preserves_conditioning_but_model_switch_uses_new_builtin(cuda_cache):
    english_builtin, reference, nano_builtin = object(), object(), object()
    english = SimpleNamespace(conds=english_builtin)
    nano = SimpleNamespace(conds=nano_builtin)
    loader = Mock(side_effect=[english, nano])
    engine = Engine(model_loader=loader)

    assert engine._get_model("english", "cpu", lambda _: None) is english
    english.conds = reference
    assert engine._get_model("english", "cpu", lambda _: None) is english
    assert engine.builtin_voice is english_builtin
    assert english.conds is reference
    assert loader.call_count == 1

    assert engine._get_model("nano", "cpu", lambda _: None) is nano
    assert engine.model_key == ("nano", "cpu")
    assert engine.builtin_voice is nano_builtin
    assert nano.conds is nano_builtin
    assert loader.call_args_list == [call("english", "cpu"), call("nano", "cpu")]
    cuda_cache.assert_not_called()
