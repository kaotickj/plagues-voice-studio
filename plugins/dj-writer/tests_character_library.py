import tempfile
import unittest
from character_library import CharacterLibrary
from build_lore_library import curate
class CharacterLibraryTests(unittest.TestCase):
 def test_candidates_require_acceptance_and_remain_host_specific(self):
  with tempfile.TemporaryDirectory() as d:
   c=CharacterLibrary(d)
   self.assertEqual(c.collect('Tal Conroy','I used to repair caravan radios. I prefer my coffee black.'),2)
   self.assertEqual(c.context('Tal Conroy'),'')
   row=c.load()[0];c.decide(row['id'],'accepted')
   self.assertIn('caravan radios',c.context('Tal Conroy'));self.assertEqual(c.context('Hattie Boggs'),'')
   self.assertNotIn('coffee',c.context('Tal Conroy'))
   c.decide(row['id'],'rejected');self.assertEqual(c.context('Tal Conroy'),'')
   self.assertEqual(c.collect('Tal Conroy','I used to repair caravan radios.'),0)
 def test_quoted_speech_is_not_host_backstory(self):
  with tempfile.TemporaryDirectory() as d:
   c=CharacterLibrary(d)
   self.assertEqual(c.collect('Tal Conroy','He said, "I always sleep late." I walked to the market.'),0)
   self.assertEqual(c.load(),[])
 def test_editor_notes_survive_reload_with_provenance(self):
  with tempfile.TemporaryDirectory() as d:
   c=CharacterLibrary(d);c.add('Hattie Boggs','Hattie repairs her own turntable.')
   again=CharacterLibrary(d)
   self.assertIn('turntable',again.context('Hattie Boggs'));self.assertEqual(again.load()[0]['source'],'editor')
class CurationTests(unittest.TestCase):
 def test_cross_game_and_conditional_outcomes_are_removed(self):
  page=dict(title='Example',ns=0,categories=[{'title':'Category:Fallout 4 locations'}],revisions=[{'revid':4}],extract='Example is a trading settlement in Fallout 4. It also appears in Fallout Shelter Online. If the player completes a quest, the mayor is killed. == Background == Traders barter scrap metal for food.')
  item,reasons=curate(page,'Example','locations',{'text':'CC BY-SA 4.0'})
  self.assertEqual(reasons,[]);self.assertNotIn('Shelter',item['text']);self.assertNotIn('killed',item['text'])
  self.assertIn('barter',item['text']);self.assertEqual(item['revision'],4)
 def test_ambiguous_or_wrong_game_results_are_held(self):
  page=dict(title='Different person',ns=0,extract='A trader living in the Mojave Desert in Fallout: New Vegas.',categories=[])
  item,reasons=curate(page,'Nick Valentine','people',{})
  self.assertTrue(any('scope' in r for r in reasons));self.assertTrue(any('title' in r for r in reasons))
if __name__=='__main__':unittest.main()
