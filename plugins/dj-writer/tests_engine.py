import random
import unittest
from dj_engine import DialogueEngine, CATEGORIES, MOODS, LENGTHS, load_content

class EngineTests(unittest.TestCase):
    def setUp(self): self.engine = DialogueEngine(load_content(), random.Random(34))
    def test_all_categories_lengths(self):
        for category in [c for c in CATEGORIES if c != 'Stories From the Commonwealth']:
            for length in LENGTHS:
                lines, warning = self.engine.generate_batch(category, 'Tal Conroy', 'Murkwater Blues', 'Mama Mire', mood='Any', length=length, quantity=1)
                self.assertEqual(len(lines), 1, (category,length,warning))
                self.assertNotIn('{', lines[0]); self.assertNotIn('}', lines[0])
    def test_mood_safety(self):
        for category in [c for c in CATEGORIES[:-1] if c != 'Stories From the Commonwealth']:
            for mood in MOODS[1:]:
                lines, warning = self.engine.generate_batch(category,'Tal Conroy',mood=mood, quantity=3)
                self.assertTrue(all(line.strip() for line in lines))
                self.assertLessEqual(len(lines),3)
    def test_no_identical_batch_results(self):
        lines, warning = self.engine.generate_batch('Random mix','Hattie “Mama Mire” Boggs',quantity=25,length='Long')
        self.assertEqual(len(lines),len(set(lines)))
        self.assertGreaterEqual(len(lines),15)
    def test_custom_ad_does_not_invent_claims(self):
        lines,_ = self.engine.generate_batch('Ad / promo','Tal Conroy', sponsor='Mr. Handy Repairs', quantity=1)
        self.assertIn('Mr. Handy Repairs',lines[0])
        self.assertNotIn('The Third Rail',lines[0])
    def test_empty_sponsor_neutral(self):
        lines,_=self.engine.generate_batch('Ad / promo','Tal Conroy',sponsor='Unknown',mood='Melancholy')
        self.assertEqual(lines,[])
    def test_plague_radio_ad(self):
        lines, _ = self.engine.generate_batch('Ad / promo', 'Mister The Plague', sponsor='Plague Radio', quantity=3)
        self.assertGreaterEqual(len(lines), 1)
        self.assertTrue(all('Plague Radio' in line for line in lines))

    def test_dj_name_variants(self):
        from dj_engine import DJ_NAME_VARIANTS, DJS
        self.assertEqual(DJS, ['Tal Conroy', 'Hattie Boggs', 'Mister The Plague'])
        self.assertIn('Mama Mire', DJ_NAME_VARIANTS['Hattie Boggs'])
        self.assertIn('The Plague', DJ_NAME_VARIANTS['Mister The Plague'])
        scene = next(s for s in self.engine.data['scenes'] if any('{dj}' in x for x in s['landing']))
        for dj, allowed in [('Hattie Boggs', DJ_NAME_VARIANTS['Hattie Boggs']), ('Mister The Plague', DJ_NAME_VARIANTS['Mister The Plague'])]:
            found = set()
            for _ in range(300):
                line = self.engine._render(scene, dj, '', '', 'Goodneighbor Blues', 'Short')
                found.update(v for v in allowed if v in line)
            self.assertTrue(any(v in found for v in allowed))

    def test_plague_and_blues_separate(self):
        for category in [c for c in CATEGORIES[:-1] if c != 'Stories From the Commonwealth']:
            lines,_=self.engine.generate_batch(category,'Mister The Plague',mood='Any',quantity=1,sponsor='Plague Radio')
            self.assertTrue(lines,category)
            self.assertNotIn('Goodneighbor Blues, 95.77', lines[0])
        lines,_=self.engine.generate_batch('Station ID','Tal Conroy',quantity=3)
        self.assertTrue(all('Plague Radio' not in line for line in lines))

    def test_history_respected(self):
        first,_=self.engine.generate_batch('Station ID','Tal Conroy',quantity=2)
        second,_=self.engine.generate_batch('Station ID','Tal Conroy',quantity=2,history=first)
        self.assertTrue(set(first).isdisjoint(second))


class ExpandedAdvertiserTests(unittest.TestCase):
    def setUp(self):
        self.engine = DialogueEngine(load_content(), random.Random(991))
    def test_ad_library_coverage(self):
        scenes = self.engine.data['scenes']
        self.assertGreaterEqual(sum(s['category'] == 'Ad / promo' for s in scenes), 40)
        for sponsor in ['Plague Radio','Goodneighbor Blues','The Third Rail','Memory Den', 'Daisy’s Discounts','KL-E-0’s Guns','Hotel Rexford']:
            for dj in ['Tal Conroy','Mister The Plague']:
                lines, warning = self.engine.generate_batch('Ad / promo', dj, sponsor=sponsor, mood='Any', quantity=2)
                self.assertEqual(len(lines),2,(sponsor,dj,warning))
                self.assertTrue(all(sponsor.casefold().removeprefix('the ') in line.casefold() for line in lines), (sponsor,dj,lines))
    def test_cross_station_styles_separated(self):
        blues,_ = self.engine.generate_batch('Ad / promo','Tal Conroy',sponsor='Plague Radio',quantity=3)
        plague,_ = self.engine.generate_batch('Ad / promo','Mister The Plague',sponsor='Goodneighbor Blues',quantity=3)
        self.assertTrue(all('Plague Radio' in s for s in blues))
        self.assertTrue(all('Goodneighbor Blues' in s for s in plague))
    def test_no_unfilled_placeholders_expanded(self):
        for dj in ['Hattie Boggs', 'Mister The Plague']:
            for sponsor in ['Daisy’s Discounts','KL-E-0’s Guns','Hotel Rexford']:
                for length in LENGTHS:
                    lines,_ = self.engine.generate_batch('Ad / promo',dj,sponsor=sponsor,length=length,quantity=4)
                    self.assertTrue(lines)
                    self.assertFalse(any('{' in line or '}' in line for line in lines))

class VersionFiveRegressionTests(unittest.TestCase):
    def setUp(self):
        from pathlib import Path
        self.engine = DialogueEngine(load_content(), random.Random(2026))
        self.new_sponsors = ['The Rusty Lantern', 'Mirelight Repairs', 'The Last Stop Diner',
          'Commonwealth Casket Company', 'Rad-Roach Exterminators', 'Ash & Ember Salvage',
          'The Midnight Courier', 'Vault-Tec Surplus Outlet', 'The Tin Can Clinic', 'The Red Rocket Wash']
    def test_new_sponsors_both_profiles(self):
        for sponsor in self.new_sponsors:
            for dj in ('Tal Conroy','Mister The Plague'):
                result, warning = self.engine.generate_batch('Ad / promo',dj,sponsor=sponsor,quantity=3)
                self.assertEqual(len(result),3,(sponsor,dj,warning))
                self.assertTrue(all(sponsor in x for x in result),(sponsor,dj,result))
                self.assertEqual(len(set(result)),len(result))
    def test_gui_output_has_no_numbering_and_has_blank_lines(self):
        from pathlib import Path
        source = Path(__file__).with_name('goodneighbor_dj.py').read_text(encoding='utf-8')
        self.assertIn('self.engine.generate_one(', source)
        self.assertNotIn('self.qty', source)
        self.assertNotIn('join(self.records[-25:])', source)
        self.assertNotIn("f'{i+1:02d}.",source)
    def test_all_new_ad_scenes_validate(self):
        from dj_engine import validate_content
        validate_content(self.engine.data)
        self.assertEqual(len([x for x in self.engine.data['scenes'] if x['id'].startswith('ad-v05-')]),74)

if __name__ == "__main__": unittest.main()

class AdManagerTests(unittest.TestCase):
    def test_custom_campaign_roundtrip_and_generation(self):
        import tempfile
        from pathlib import Path
        from ad_manager import new_campaign, save_campaigns, load_campaigns
        c = new_campaign('Moonlight Repair Shop')
        c['slogan'] = 'We fix what the Institute broke.'
        c['scripts'] = [{'profile': 'blues', 'length': 'Medium', 'mood': 'Wry',
                         'text': 'Moonlight Repair Shop. We fix what the Institute broke.'},
                        {'profile': 'plague', 'length': 'Medium', 'mood': 'Suspicious',
                         'text': 'Moonlight Repair Shop. Ask who broke it first.'}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ads.json'
            save_campaigns(path, [c])
            loaded = load_campaigns(path)
            self.assertEqual(loaded[0]['slogan'], c['slogan'])
            engine = DialogueEngine(campaigns=loaded)
            b, _ = engine.generate_batch('Ad / promo', 'Tal Conroy', sponsor=c['name'],
                                         mood='Wry', length='Medium', quantity=1)
            p, _ = engine.generate_batch('Ad / promo', 'Mister The Plague', sponsor=c['name'],
                                         mood='Suspicious', length='Medium', quantity=1)
            self.assertIn('We fix', b[0])
            self.assertIn('Ask who', p[0])
            unavailable, warning = engine.generate_batch('Ad / promo', 'Tal Conroy', sponsor=c['name'],
                                                          mood='Ominous', quantity=1)
            self.assertEqual(unavailable, [])
            self.assertIn('No enabled custom ad', warning)

    def test_disabled_campaign_and_invalid_script(self):
        from ad_manager import new_campaign, validate_campaigns, scripts_for
        c = new_campaign('Tin Roof')
        c['scripts'] = [{'profile':'blues', 'length':'Short', 'mood':'Wry', 'text':'Tin Roof.'}]
        c['enabled'] = False
        self.assertEqual(scripts_for([c], 'Tin Roof', 'blues', 'Any', 'Short'), [])
        c['scripts'][0]['text'] = '{unknown}'
        with self.assertRaises(ValueError): validate_campaigns([c])
