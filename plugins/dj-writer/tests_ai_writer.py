"""Protocol, editorial and actual Qt worker regressions. No weights downloaded."""
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
import ai_studio
from ai_writer import (Cancelled, LocalWriter, ScriptRequest, build_messages,
                       default_settings, download_verified, extract_runtime,
                       load_settings, save_settings, validate_script)
import goodneighbor_dj as gui
from ad_manager import validate_campaigns
from dj_engine import CATEGORIES, DJS
from script_prompts import (COMMONWEALTH_RULES, DEFAULT_WORDS, DJ_IDENTITIES,
                            FORMAT_PROMPTS, advertiser_context, format_prompt, station_for)


class PromptTests(unittest.TestCase):
    def test_host_lore_continuity_and_one_script_instruction(self):
        settings = default_settings()
        settings.update(model_preset='gemma-writer', context_size=8192)
        settings['continuity']['Mister The Plague'] = 'Disproven: the teddy bear did not transmit radio signals.'
        request = ScriptRequest('Mister The Plague', 'Stories From the Commonwealth', words=900,
                                brief='Find the owner of the bear.')
        messages = build_messages(request, settings, ['A previous opening.'])
        prompt = '\n'.join(m['content'] for m in messages)
        self.assertIn('exactly ONE script', prompt)
        self.assertIn('STATION: Plague Radio', prompt)
        self.assertIn('Disproven:', prompt)
        self.assertIn('"target_words": 900', prompt)
        self.assertIn('Find the owner', prompt)
        self.assertEqual([m['role'] for m in messages], ['user'])  # Gemma template
        self.assertEqual(settings['continuity']['Tal Conroy'], '')

    def test_ad_request_includes_slogan_and_product_notes(self):
        messages = build_messages(ScriptRequest('Hattie Boggs', 'Ad / promo', sponsor='Mirelight Repairs',
                                  advertiser_notes='Repairs radios. Required slogan: We keep the night talking.'), default_settings())
        prompt = '\n'.join(m['content'] for m in messages)
        self.assertIn('Mirelight Repairs', prompt)
        self.assertIn('We keep the night talking.', prompt)
        self.assertIn('one complete commercial', prompt)

    def test_smaller_qwen_gets_native_system_role(self):
        settings = default_settings(); settings['model_preset'] = 'qwen-small'
        self.assertEqual([m['role'] for m in build_messages(ScriptRequest('Tal Conroy', 'Station ID'), settings)], ['system', 'user'])

    def test_no_automatic_continuity_changes(self):
        settings = default_settings(); before = deepcopy(settings)
        build_messages(ScriptRequest('Tal Conroy', 'Station break'), settings)
        self.assertEqual(settings, before)

    def test_oversized_notes_are_actionable(self):
        with self.assertRaisesRegex(ValueError, 'Shorten'):
            build_messages(ScriptRequest('Tal Conroy', 'Station break', brief='x' * 4001), default_settings())

    def test_review_checks_truncation_wrong_station_missing_ad_and_repetition(self):
        req = ScriptRequest('Tal Conroy', 'Station ID', words=20)
        warnings = validate_script('This is Plague Radio. {host}', req, finish_reason='length')
        self.assertTrue(any('cut-off' in w for w in warnings))
        self.assertTrue(any('Plague Radio' in w for w in warnings))
        self.assertTrue(any('placeholders' in w for w in warnings))
        text = 'A previous result with a long enough sentence to compare for repetition.'
        self.assertTrue(any('similar' in w for w in validate_script(text, req, [text])))
        self.assertTrue(any('advertiser' in w for w in validate_script('Buy something today.', ScriptRequest('Tal Conroy', 'Ad / promo', sponsor='The Rusty Lantern'))))

    def test_changed_brand_slogan_is_flagged(self):
        request = ScriptRequest('Hattie Boggs', 'Ad / promo', sponsor='Mirelight Repairs',
                                advertiser_slogan='We keep the night talking.')
        self.assertTrue(any('slogan' in w for w in validate_script('Mirelight Repairs. They keep the night talking.', request)))
        self.assertFalse(any('slogan' in w for w in validate_script('Mirelight Repairs. We keep the night talking.', request)))

    def test_unicode_profile_and_continuity_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ai_studio.json'
            settings = default_settings(); settings['continuity']['Hattie Boggs'] = 'The café owner repaired the radio.'
            save_settings(path, settings)
            self.assertEqual(load_settings(path), settings)

    def test_invalid_ad_metadata_is_rejected_before_generation(self):
        with self.assertRaisesRegex(ValueError, 'slogan must be text'):
            validate_campaigns([{'name':'Bad metadata shop', 'slogan':42, 'scripts':[]}])


class BuiltInPromptTests(unittest.TestCase):
    def test_every_selectable_format_has_a_default(self):
        self.assertEqual(set(FORMAT_PROMPTS), set(CATEGORIES))
        self.assertEqual(set(DEFAULT_WORDS), set(CATEGORIES))

    def test_blank_brief_uses_defaults_for_every_host_and_format(self):
        for dj in DJS:
            for category in CATEGORIES:
                with self.subTest(dj=dj, category=category):
                    messages = build_messages(ScriptRequest(dj, category, words=DEFAULT_WORDS[category]), default_settings())
                    text = '\n'.join(m['content'] for m in messages)
                    self.assertIn(format_prompt(category, dj), text)
                    if category != 'Website Promo':
                        self.assertIn(COMMONWEALTH_RULES, text)
                    self.assertIn(DJ_IDENTITIES[dj], text)
                    self.assertIn('STATION: ' + ('Goodneighbor Blues / goodneighborblues.com' if category == 'Website Promo' else station_for(dj)), text)
                    self.assertIn('No additional direction', text)

    def test_custom_direction_keeps_the_built_in_story_prompt(self):
        request = ScriptRequest('Tal Conroy', 'Stories From the Commonwealth', brief='A scavenger must return a stolen lantern.')
        text = '\n'.join(m['content'] for m in build_messages(request, default_settings()))
        self.assertIn('A scavenger must return a stolen lantern.', text)
        self.assertIn('Dramatize choices', text)
        self.assertIn('resolve this episode', text)

    def test_story_recipe_reaches_every_selected_dj_with_either_source(self):
        for dj in DJS:
            for brief in ('I witnessed a caravan toll dispute.',
                          'A trader told me about a robot enforcing a nonsense rule.'):
                with self.subTest(dj=dj, brief=brief):
                    messages = build_messages(ScriptRequest(dj, 'Stories From the Commonwealth',
                                                            brief=brief), default_settings())
                    self.assertIn('STORY DELIVERY CONTRACT', messages[0]['content'])
                    text = messages[-1]['content']
                    self.assertIn(f'spoken by {dj}', text)
                    self.assertIn(brief, text)
                    for beat in ('HOOK AND SOURCE', 'SET THE SCENE', 'THE WASTELAND TURN',
                                 'SOURCE AND REACTION', 'PAYOFF AND BACK TO THE BROADCAST'):
                        self.assertIn(beat, text)
                    self.assertIn('FIRSTHAND', text)
                    self.assertIn('PASSED ALONG', text)
                    self.assertIn('first two sentences', text)
                    self.assertIn('no sign-off', text)

    def test_radio_story_contract_does_not_change_other_formats(self):
        for category in CATEGORIES:
            if category != 'Stories From the Commonwealth':
                with self.subTest(category=category):
                    text = '\n'.join(m['content'] for m in build_messages(
                        ScriptRequest('Tal Conroy', category), default_settings()))
                    self.assertNotIn('STORY DELIVERY CONTRACT', text)
                    self.assertNotIn('RADIO ANECDOTE RECIPE', text)

    def test_station_knowledge_also_reaches_existing_custom_profiles(self):
        settings = default_settings(); settings['profiles']['Hattie Boggs'] = 'Keep my edited personality. No whiskey jokes.'
        before = deepcopy(settings)
        text = '\n'.join(m['content'] for m in build_messages(ScriptRequest('Hattie Boggs', 'Station break'), settings))
        self.assertIn('Chicago, Delta, whiskey', text)
        self.assertIn('Hattie "Mama Mire" Boggs', text)
        self.assertIn('Keep my edited personality. No whiskey jokes.', text)
        self.assertEqual(settings, before)

    def test_blank_commercial_has_bundled_business_knowledge(self):
        text = '\n'.join(m['content'] for m in build_messages(ScriptRequest('Mister The Plague', 'Ad / promo', sponsor='The Tin Can Clinic'), default_settings()))
        self.assertIn('robot diagnostics', text)
        self.assertIn('does not imply a medical clinic', text)
        self.assertIn('one complete in-world radio commercial', text)

    def test_all_bundled_advertisers_have_context(self):
        for advertiser in gui.ADS:
            with self.subTest(advertiser=advertiser):
                self.assertNotIn('No bundled product', advertiser_context(advertiser, 'Tal Conroy'))

    def test_unknown_brand_is_not_given_invented_inventory(self):
        self.assertIn('general invitation without invented business facts', advertiser_context('Unspecified New Shop', 'Hattie Boggs'))

    def test_blank_advertiser_becomes_home_station_promo(self):
        text = '\n'.join(m['content'] for m in build_messages(ScriptRequest('Mister The Plague', 'Ad / promo'), default_settings()))
        self.assertIn('"advertiser": "Plague Radio"', text)
        self.assertIn('pirate, late-night Commonwealth metal', text)

    def test_cross_station_promo_preserves_host_and_target(self):
        request = ScriptRequest('Mister The Plague', 'Ad / promo', sponsor='Goodneighbor Blues')
        messages = build_messages(request, default_settings())
        self.assertIn('STATION: Plague Radio', messages[0]['content'])
        self.assertIn('95.77', messages[1]['content'])
        self.assertIn('Chicago, Delta', messages[1]['content'])
        self.assertFalse(any('Check 95.77' in w for w in validate_script('Goodneighbor Blues, 95.77. Back to Plague Radio.', request)))

    def test_frequency_mistakes_are_reviewed(self):
        warnings = validate_script('This is Plague Radio, 95.77.', ScriptRequest('Mister The Plague', 'Station ID', words=20))
        self.assertTrue(any('Check 95.77' in w for w in warnings))
        warnings = validate_script('You are tuned to Goodneighbor Blues.', ScriptRequest('Tal Conroy', 'Station ID', words=20))
        self.assertTrue(any('missing its 95.77' in w for w in warnings))

    def test_default_ad_does_not_need_an_invented_location(self):
        request = ScriptRequest('Mister The Plague', 'Ad / promo', sponsor='The Tin Can Clinic')
        prompt = '\n'.join(m['content'] for m in build_messages(request, default_settings()))
        self.assertIn('Ask about The Tin Can Clinic.', prompt)
        self.assertIn('No exact location, pickup time', prompt)

    def test_unsupported_ad_time_place_and_price_are_flagged(self):
        request = ScriptRequest('Mister The Plague', 'Ad / promo', sponsor='The Tin Can Clinic')
        warnings = validate_script('The Tin Can Clinic. Come by 8 p.m. at the Hotel Rexford back lot. Only 50 caps.', request)
        self.assertTrue(any('specific time' in w for w in warnings))
        self.assertTrue(any('Hotel Rexford' in w for w in warnings))
        self.assertTrue(any('caps price' in w for w in warnings))

    def test_supplied_ad_time_place_and_price_are_allowed(self):
        request = ScriptRequest('Hattie Boggs', 'Ad / promo', sponsor='Test repairer',
                                advertiser_notes='Drop-off at the Hotel Rexford, 8 p.m. Service price 50 caps.')
        warnings = validate_script('Test repairer. Drop off at the Hotel Rexford, 8 p.m. Service is 50 caps.', request)
        self.assertFalse(any('specific time' in w or 'ad location' in w or 'caps price' in w for w in warnings))

    def test_spoken_ad_markdown_is_flagged(self):
        warnings = validate_script('The Tin Can Clinic can fix your *robot*.', ScriptRequest('Mister The Plague', 'Ad / promo', sponsor='The Tin Can Clinic'))
        self.assertTrue(any('non-spoken formatting' in w for w in warnings))

    def test_a_changed_price_is_not_treated_as_supplied(self):
        request = ScriptRequest('Hattie Boggs', 'Ad / promo', sponsor='Test repairer', advertiser_notes='Service price: 150 caps.')
        warnings = validate_script('Test repairer. Service for 50 caps.', request)
        self.assertTrue(any('caps price' in w for w in warnings))

    def test_unapproved_history_does_not_become_prompt_lore(self):
        invented = 'The Tin Can Clinic opens behind the Hotel Rexford at 8 p.m.'
        prompt = '\n'.join(m['content'] for m in build_messages(ScriptRequest('Tal Conroy', 'Station break'), default_settings(), [invented]))
        self.assertNotIn(invented, prompt)
        self.assertIn('previous results for repetition', prompt)

    def test_brahmin_vehicle_confusion_is_reviewed(self):
        warnings = validate_script('Your brahmin’s engine needs repairing.', ScriptRequest('Tal Conroy', 'Station break'))
        self.assertTrue(any('living cattle' in w for w in warnings))


class Response(io.BytesIO):
    def __init__(self, content, status=200, headers=None):
        super().__init__(content); self.status = status; self.headers = headers or {}


class InstallerTests(unittest.TestCase):
    def test_partial_download_resumes_and_hashes_before_publication(self):
        content = b'A' * 100 + b'B' * 200
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / 'model.gguf'
            dest.with_name(dest.name + '.partial').write_bytes(content[:100])
            def response(req, timeout):
                self.assertEqual(req.get_header('Range'), 'bytes=100-')
                return Response(content[100:], 206, {'Content-Range': 'bytes 100-299/300'})
            with patch('ai_writer.urllib.request.urlopen', side_effect=response):
                download_verified('https://example.com/test', dest, len(content), hashlib.sha256(content).hexdigest(), threading.Event(), lambda *args: None)
            self.assertEqual(dest.read_bytes(), content)
            self.assertFalse(dest.with_name(dest.name + '.partial').exists())

    def test_bad_hash_never_publishes_model(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / 'model.gguf'
            with patch('ai_writer.urllib.request.urlopen', return_value=Response(b'wrong')):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    download_verified('https://example.com/test', dest, 5, '0' * 64, threading.Event(), lambda *args: None)
            self.assertFalse(dest.exists())

    def test_cancellation_keeps_partial_and_no_final(self):
        content = b'A' * (3 * 1024 * 1024)
        cancel = threading.Event()
        def report(done, total, message):
            if done:
                cancel.set()
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / 'model.gguf'
            with patch('ai_writer.urllib.request.urlopen', return_value=Response(content)):
                with self.assertRaises(Cancelled):
                    download_verified('https://example.com/test', dest, len(content), '0' * 64, cancel, report)
            self.assertFalse(dest.exists())
            self.assertTrue(dest.with_name(dest.name + '.partial').exists())

    def test_early_eof_keeps_download_for_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / 'model.gguf'
            with patch('ai_writer.urllib.request.urlopen', return_value=Response(b'partial')):
                with self.assertRaisesRegex(ConnectionError, 'resume'):
                    download_verified('https://example.com/test', dest, 200, '0' * 64, threading.Event(), lambda *args: None)
            self.assertFalse(dest.exists())
            self.assertEqual(dest.with_name(dest.name + '.partial').read_bytes(), b'partial')

    def test_archive_cannot_escape_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); archive = root / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('../escaped.exe', b'bad')
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                extract_runtime(archive, root / 'runtime', threading.Event())
            self.assertFalse((root / 'escaped.exe').exists())


class FakeProcess:
    def __init__(self):
        self.stopped = False; self.terminated = False
    def poll(self):
        return 0 if self.stopped else None
    def terminate(self):
        self.stopped = self.terminated = True
    def kill(self):
        self.stopped = True
    def wait(self, timeout):
        self.stopped = True


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        settings = default_settings()
        server = self.root / 'llama-server'; server.write_text('mock executable')
        model = self.root / 'model.gguf'; model.write_text('mock weights')
        settings.update(server_path=str(server), model_path=str(model))
        self.writer = LocalWriter(settings, self.root)
        self.process = FakeProcess()

    def tearDown(self):
        self.folder.cleanup()

    def reply(self, route, payload=None, timeout=5):
        if route == '/health':
            return Response(b'{"status":"ok"}')
        if route == '/v1/models':
            return Response(b'{"data":[{"id":"dj-writer"}]}')
        if route == '/apply-template':
            return Response(b'{"prompt":"formatted prompt"}')
        if route == '/tokenize':
            return Response(b'{"tokens":[1,2,3]}')
        if route == '/v1/chat/completions':
            self.assertEqual(payload['n'], 1)
            self.assertEqual(payload['model'], 'dj-writer')
            if not payload.get('stream', True):
                return Response(json.dumps({'choices': [{'finish_reason': 'stop',
                    'message': {'content': json.dumps({'text': 'One complete café script.'})}}]}).encode())
            content = 'data: ' + json.dumps({'choices': [{'delta': {'content': 'One complete café script.'}, 'finish_reason': None}]}) + '\n\n'
            content += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]}) + '\n\ndata: [DONE]\n\n'
            return Response(content.encode('utf-8'))
        raise AssertionError(route)

    def test_streaming_returns_one_script_and_unloads_owned_process(self):
        fragments = []
        with patch('ai_writer.subprocess.Popen', return_value=self.process) as start, patch.object(self.writer, '_request', side_effect=self.reply):
            result = self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20), on_text=fragments.append)
        self.assertEqual(result['text'], 'One complete café script.')
        self.assertEqual(''.join(fragments), result['text'])
        self.assertTrue(self.process.terminated)
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--host') + 1], '127.0.0.1')
        self.assertEqual(args[args.index('--device') + 1], 'none')
        self.assertIn('--api-key', args)
        self.assertIsNone(self.writer._process)

    def test_qwen_uses_its_published_sampling_defaults(self):
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=self.reply) as http:
            self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
        payload = next(call.args[1] for call in http.call_args_list if call.args[0] == '/v1/chat/completions')
        self.assertEqual((payload['temperature'],payload['top_p'],payload['top_k'],payload['min_p']), (.7,.8,20,0.0))

    def test_gemma_short_links_use_restrained_sampling(self):
        self.writer.settings['model_preset'] = 'gemma-writer'
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=self.reply) as http:
            self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
        payload = next(call.args[1] for call in http.call_args_list if call.args[0] == '/v1/chat/completions')
        self.assertEqual((payload['temperature'], payload['top_p']), (.45, .85))
        self.assertEqual(len([call for call in http.call_args_list if call.args[0] == '/v1/chat/completions']), 2)

    def test_failed_gemma_edit_does_not_return_a_completed_draft(self):
        self.writer.settings['model_preset'] = 'gemma-writer'
        original = self.reply
        def reply(route, payload=None, timeout=5):
            if route == '/v1/chat/completions' and not payload.get('stream', True):
                return Response(b'{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}')
            return original(route, payload, timeout)
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=reply):
            with self.assertRaisesRegex(ValueError, 'Radio editing did not finish'):
                self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
        self.assertTrue(self.process.terminated)

    def test_eof_is_failure_and_still_unloads(self):
        original = self.reply
        def incomplete(route, payload=None, timeout=5):
            return Response(b'data: {"choices":[{"delta":{"content":"Cut off"}}]}\n\n') if route == '/v1/chat/completions' else original(route, payload, timeout)
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=incomplete):
            with self.assertRaisesRegex(RuntimeError, 'before completion'):
                self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
        self.assertTrue(self.process.terminated)

    def test_vulkan_requests_a_vulkan_device(self):
        self.writer.settings['backend'] = 'Vulkan'
        with patch('ai_writer.subprocess.Popen', return_value=self.process) as start, patch.object(self.writer, '_request', side_effect=self.reply):
            self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
        args = start.call_args.args[0]
        self.assertEqual(args[args.index('--device') + 1], 'Vulkan0')
        self.assertEqual(args[args.index('--n-gpu-layers') + 1], '99')

    def test_cancel_stops_only_owned_process_and_no_generation(self):
        self.writer._process = self.process
        self.writer.cancel()
        self.assertTrue(self.process.terminated)
        with patch('ai_writer.subprocess.Popen') as start:
            with self.assertRaises(Cancelled):
                self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
            start.assert_not_called()

    def test_context_overflow_rejected_before_inference(self):
        original = self.reply
        def too_many(route, payload=None, timeout=5):
            return Response(json.dumps({'tokens': [1] * 16300}).encode()) if route == '/tokenize' else original(route, payload, timeout)
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=too_many) as http:
            with self.assertRaisesRegex(ValueError, 'Shorten'):
                self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
            self.assertFalse(any(call.args[0] == '/v1/chat/completions' for call in http.call_args_list))
        self.assertTrue(self.process.terminated)

    def test_native_context_limit_is_respected(self):
        original = self.reply
        def native_small(route, payload=None, timeout=5):
            return Response(b'{"data":[{"id":"dj-writer","meta":{"n_ctx_train":4096}}]}') if route == '/v1/models' else original(route, payload, timeout)
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=native_small):
            with self.assertRaisesRegex(ValueError, 'native context is 4,096'):
                self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
        self.assertTrue(self.process.terminated)

    def test_foreign_server_auth_failure_never_receives_prompt(self):
        original = self.reply
        def foreign(route, payload=None, timeout=5):
            if route == '/v1/models':
                raise urllib.error.HTTPError('http://127.0.0.1/v1/models', 401, 'Unauthorized', {}, None)
            return original(route, payload, timeout)
        with patch('ai_writer.subprocess.Popen', return_value=self.process), patch.object(self.writer, '_request', side_effect=foreign) as http:
            with self.assertRaisesRegex(RuntimeError, 'rejected startup'):
                self.writer.generate(ScriptRequest('Tal Conroy', 'Station ID', words=20))
            self.assertFalse(any(call.args[0] == '/v1/chat/completions' for call in http.call_args_list))
        self.assertTrue(self.process.terminated)


class ControlledWriter:
    def __init__(self, fail=False):
        self.stop = threading.Event(); self.started = threading.Event(); self.release = threading.Event()
        self.fail = fail
    def cancel(self):
        self.stop.set()
    def generate(self, request, recent, on_text, status):
        self.request = request
        status('Writing with test double'); on_text('Partial draft'); self.started.set()
        while not self.release.wait(.01):
            if self.stop.is_set():
                raise Cancelled()
        if self.fail:
            raise RuntimeError('Deliberate failure')
        return {'text': 'One completed AI draft.', 'warnings': [], 'elapsed_seconds': .1, 'backend': 'CPU'}


class AIWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); root = Path(self.folder.name)
        self.patch = patch.multiple(gui, DATA=root, HISTORY=root/'history.json', CAMPAIGNS=root/'advertisers.json')
        self.patch.start(); self.window = gui.Window()
        server = root/'server'; server.touch(); model = root/'model.gguf'; model.touch()
        self.window.ai.settings.update(server_path=str(server), model_path=str(model))

    def pump_until(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents(); threading.Event().wait(.01)
        self.assertTrue(predicate())

    def tearDown(self):
        if self.window.ai.busy:
            self.window.ai.cancel(); self.pump_until(lambda: not self.window.ai.busy)
        self.window.close(); self.window.deleteLater(); self.app.processEvents()
        self.patch.stop(); self.folder.cleanup()

    def start(self, writer):
        self.window.output.setPlainText('Previous complete script.')
        with patch.object(ai_studio, 'LocalWriter', return_value=writer):
            self.window.on_generate()
        self.pump_until(writer.started.is_set)

    def test_ai_is_default_and_streaming_disables_review_until_finished(self):
        w = self.window; writer = ControlledWriter()
        self.assertEqual(w.mode.currentText(), 'AI Studio')
        w.ai.words.setValue(1100)
        self.start(writer)
        self.assertFalse(w.generate_button.isEnabled())
        self.assertFalse(w.reviewed.isEnabled())
        self.assertTrue(w.cancel_button.isEnabled())
        self.assertTrue(w.output.isReadOnly())
        self.assertFalse(w.ai.view_prompt_button.isEnabled())
        writer.release.set(); self.pump_until(lambda: not w.ai.busy)
        self.assertEqual(w.output.toPlainText(), '[narration] One completed AI draft.')
        self.assertEqual(w.records, ['One completed AI draft.'])
        self.assertEqual(writer.request.words, 1100)
        self.assertEqual(w.ai.words.value(), 1100)
        self.assertFalse(w.reviewed.isChecked())
        self.assertFalse(w.save_button.isEnabled())
        self.assertTrue(w.generate_button.isEnabled())

    def test_cancel_restores_previous_script_and_does_not_add_history(self):
        w = self.window; writer = ControlledWriter(); self.start(writer)
        w.ai.cancel(); self.pump_until(lambda: not w.ai.busy)
        self.assertEqual(w.output.toPlainText(), 'Previous complete script.')
        self.assertEqual(w.records, [])
        self.assertFalse(w.reviewed.isChecked())

    def test_failed_job_restores_editor_and_allows_retry(self):
        w = self.window; writer = ControlledWriter(fail=True); self.start(writer)
        writer.release.set(); self.pump_until(lambda: not w.ai.busy)
        self.assertEqual(w.output.toPlainText(), 'Previous complete script.')
        self.assertIn('Deliberate failure', w.ai.state.text())
        self.assertTrue(w.generate_button.isEnabled())
        self.assertEqual(w.records, [])

    def test_close_waits_for_owned_worker_to_stop(self):
        w = self.window; writer = ControlledWriter(); self.start(writer)
        w.close(); self.assertTrue(writer.stop.is_set())
        self.pump_until(lambda: not w.ai.busy)
        self.assertEqual(w.records, [])

    def test_changing_model_preset_does_not_keep_incompatible_weights(self):
        w = self.window
        w.ai.settings.update(model_preset='gemma-writer', context_size=8192)
        dialog = ai_studio.SetupDialog(w.ai.settings, Path(self.folder.name), w)
        self.assertTrue(dialog.model.text())
        dialog.preset.setCurrentIndex(dialog.preset.findData('qwen-small'))
        self.assertEqual(dialog.context.value(), 16384)
        self.assertEqual(dialog.model.text(), '')
        dialog.close()

    def test_history_write_failure_is_visible_and_script_is_retained(self):
        w = self.window; writer = ControlledWriter(); self.start(writer)
        with patch.object(Path, 'write_text', side_effect=OSError('disk full')):
            writer.release.set(); self.pump_until(lambda: not w.ai.busy)
        self.assertEqual(w.output.toPlainText(), '[narration] One completed AI draft.')
        self.assertIn('History could not be saved', w.review_notes.text())
        self.assertIn('disk full', w.statusBar().currentMessage())

    def test_default_prompt_can_be_viewed_without_running_a_model(self):
        w = self.window; w.cat.setCurrentText('Stories From the Commonwealth')
        self.assertEqual(w.ai.brief.toPlainText(), '')
        with patch.object(ai_studio, 'LocalWriter') as writer:
            text = w.ai.active_prompt_text()
            writer.assert_not_called()
        self.assertIn('Stories From the Commonwealth', w.ai.prompt_label.text())
        self.assertIn('RADIO ANECDOTE RECIPE', text)
        self.assertIn('600-word', text)

    def test_switching_host_and_format_preserves_optional_direction(self):
        w = self.window; w.ai.brief.setPlainText('Keep this idea for me.')
        w.dj.setCurrentText('Mister The Plague'); w.cat.setCurrentText('Ad / promo')
        self.assertIn('Plague Radio', w.ai.prompt_label.text())
        self.assertIn('Ad / promo', w.ai.prompt_label.text())
        self.assertIn('Keep this idea for me.', w.ai.active_prompt_text())
        self.assertEqual(w.ai.brief.toPlainText(), 'Keep this idea for me.')

    def test_unused_large_ad_notes_do_not_block_a_story(self):
        w = self.window
        w.campaigns = [{'name':'Long-notes shop','enabled':True,'description':'x' * 2500,'scripts':[]}]
        w.refresh_advertisers(); w.sponsor.setCurrentText('Long-notes shop')
        w.cat.setCurrentText('Stories From the Commonwealth')
        self.assertEqual(w.ai.current_request().advertiser_notes, '')
        self.assertIn('Stories From the Commonwealth', w.ai.active_prompt_text())


if __name__ == '__main__':
    unittest.main()
