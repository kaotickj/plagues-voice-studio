"""Memory-friendly llama.cpp launch regressions, no GUI dependencies."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, MagicMock

from ai_writer import (LocalWriter, KVCacheAllocationError, context_retry_sizes,
                       default_settings, save_settings, load_settings, validate_settings)


class TestMemoryLaunch(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.data = Path(self.folder.name)
        self.server = self.data / 'llama-server.exe'
        self.model = self.data / 'gemma.gguf'
        self.server.touch()
        self.model.touch()
        self.settings = default_settings()
        self.settings.update(server_path=str(self.server), model_path=str(self.model), model_preset='gemma-writer', context_size=8192)
        self.writer = LocalWriter(self.settings, self.data)

    def tearDown(self):
        self.folder.cleanup()

    def test_defaults_disable_extra_repacking(self):
        self.assertIs(self.settings['disable_repack'], True)
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        args = start.call_args.args[0]
        self.assertIn('--no-repack', args)
        self.assertEqual(args[args.index('--threads') + 1], str(self.settings['cpu_threads']))
        self.assertEqual(args[args.index('--n-gpu-layers') + 1], '0')

    def test_can_opt_in_to_repacking(self):
        self.writer.settings['disable_repack'] = False
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        self.assertNotIn('--no-repack', start.call_args.args[0])

    def test_vulkan_still_uses_memory_compatibility(self):
        self.writer.settings['backend'] = 'Vulkan'
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        args = start.call_args.args[0]
        self.assertIn('--no-repack', args)
        self.assertEqual(args[args.index('--device') + 1], 'Vulkan0')

    def test_older_settings_without_key_remain_valid(self):
        old_settings = deepcopy(self.settings)
        del old_settings['disable_repack']
        validate_settings(old_settings)
        self.writer.settings = old_settings
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        self.assertIn('--no-repack', start.call_args.args[0])

    def test_setting_roundtrip_and_validation(self):
        config = self.data / 'config.json'
        self.settings['disable_repack'] = False
        save_settings(config, self.settings)
        self.assertIs(load_settings(config)['disable_repack'], False)
        self.settings['disable_repack'] = 'false'
        with self.assertRaisesRegex(ValueError, 'weight repacking'):
            validate_settings(self.settings)

    def test_startup_raises_specific_repack_diagnostic(self):
        self.writer.log_path = self.data / 'log.txt'
        self.writer.log_path.write_text('ggml_backend_cpu_buffer_type_alloc_buffer: failed to allocate buffer\n'
                                        'unable to allocate CPU_REPACK buffer\n')
        class FailedProcess:
            def poll(self): return 1
        self.writer._process = FailedProcess()
        self.writer._key = 'local-test'
        self.writer._base = 'http://127.0.0.1:1234'
        with self.assertRaisesRegex(RuntimeError, 'Disable weight repacking'):
            self.writer._wait_ready(lambda _: None)

    def test_default_balanced_cache_reduces_k_but_keeps_v_compatible(self):
        self.assertEqual(self.settings['kv_cache_mode'], 'balanced')
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--cache-type-k') + 1], 'q8_0')
        self.assertEqual(args[args.index('--cache-type-v') + 1], 'f16')
        self.assertNotIn('--flash-attn', args)

    def test_compact_cache_enables_flash_attention(self):
        self.writer.settings['kv_cache_mode'] = 'compact'
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--cache-type-v') + 1], 'q8_0')
        self.assertEqual(args[args.index('--flash-attn') + 1], 'on')

    def test_older_configuration_can_load_new_defaults(self):
        old = deepcopy(self.settings)
        for field in ('kv_cache_mode', 'auto_memory_recovery'):
            old.pop(field)
        config = self.data / 'old.json'
        save_settings(config, old)
        self.assertEqual(load_settings(config), old)
        self.writer.settings = old
        with patch('ai_writer.subprocess.Popen') as start:
            self.writer._start(self.server, self.model)
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--cache-type-k') + 1], 'q8_0')

    def test_context_retries_are_decreasing_and_do_not_modify_config(self):
        self.settings['context_size'] = 16384
        self.writer.settings['context_size'] = 16384
        attempts = []
        messages = []
        def start(server, model, context_size=None):
            attempts.append(context_size)
        def ready(status):
            if len(attempts) < 3:
                raise KVCacheAllocationError('KV allocation failed')
        with patch.object(self.writer, '_start', side_effect=start), \
             patch.object(self.writer, '_wait_ready', side_effect=ready), \
             patch.object(self.writer, '_stop_server') as stop:
            actual = self.writer._load_with_memory_recovery(self.server, self.model, messages.append)
        self.assertEqual(actual, 4096)
        self.assertEqual(attempts, [16384, 8192, 4096])
        self.assertEqual(stop.call_count, 2)
        self.assertEqual(self.writer.settings['context_size'], 16384)
        self.assertTrue(any('Retrying' in m for m in messages))

    def test_retries_disabled_never_change_context(self):
        self.writer.settings.update(context_size=8192, auto_memory_recovery=False)
        attempts = []
        def fail(server, model, context_size=None):
            attempts.append(context_size)
        with patch.object(self.writer, '_start', side_effect=fail), \
             patch.object(self.writer, '_wait_ready', side_effect=KVCacheAllocationError('allocation')), \
             patch.object(self.writer, '_stop_server'):
            with self.assertRaises(KVCacheAllocationError):
                self.writer._load_with_memory_recovery(self.server, self.model, lambda _: None)
        self.assertEqual(attempts, [8192])

    def test_small_context_accepted_and_invalid_cache_settings_rejected(self):
        self.settings.update(context_size=2048)
        validate_settings(self.settings)
        self.settings['kv_cache_mode'] = 'unrecognized'
        with self.assertRaisesRegex(ValueError, 'KV-cache'):
            validate_settings(self.settings)
        self.settings['kv_cache_mode'] = 'balanced'
        self.settings['auto_memory_recovery'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'memory recovery'):
            validate_settings(self.settings)

    def test_real_kv_log_diagnosed(self):
        # From the user's Qwen3 4B crash: model loads, context allocation then fails.
        self.writer.log_path = self.data / 'qwen.txt'
        self.writer.log_path.write_text('failed to allocate CPU buffer of size 2415919104\n'
                                         'llama_init_from_model: failed to initialize the context: '
                                         'failed to allocate buffer for kv cache\n')
        process = MagicMock()
        process.poll.return_value = 1
        self.writer._process = process
        self.writer._active_context = 16384
        with self.assertRaisesRegex(KVCacheAllocationError, '16,384'):
            self.writer._wait_ready(lambda _: None)

    def test_retry_sizes_allow_1024_as_last_resort(self):
        self.assertEqual(context_retry_sizes(8192), [8192, 4096, 2048, 1024])

if __name__ == '__main__':
    unittest.main()
