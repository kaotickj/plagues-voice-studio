"""Bounded, attributed Commonwealth references; wiki prose is never instruction text."""
from __future__ import annotations
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

API = 'https://fallout.wiki/api.php'
ORIGIN = 'https://fallout.wiki'
TTL = 30 * 86400
# Original short factual notes, not copied article prose. Sources are supplied for review.
SEEDS = [
 ('Goodneighbor', ['Goodneighbor'], 'A settlement in downtown Boston. The Third Rail, Memory Den and Hotel Rexford are distinct establishments; do not exchange their services.'),
 ('The Third Rail', ['Third Rail', 'Magnolia'], 'A bar and music venue in Goodneighbor. Magnolia performs there. Do not invent a regional utility or lodging service for it.'),
 ('Memory Den', ['Memory Den', 'Irma', 'Doctor Amari'], 'A Goodneighbor establishment associated with reliving memories using memory loungers. It is not established as a bar.'),
 ('Hotel Rexford', ['Hotel Rexford', 'Rexford'], 'A hotel in Goodneighbor. Lodging does not establish a water monopoly, greenhouse, or other invented business.'),
 ('Diamond City', ['Diamond City', 'Fenway'], 'A settlement built inside Fenway Park in Boston. Do not invent a completed player quest or player-controlled political outcome.'),
 ('Brahmin (Fallout 4)', ['brahmin'], 'Brahmin are mutated two-headed cattle used as pack animals. Ordinary brahmin do not converse in human speech or operate vehicles.'),
 ('The Commonwealth', ['Commonwealth', 'Boston'], 'Fallout 4 takes place in the post-war Commonwealth around Boston. Player choices and quest outcomes are not established for this radio project.'),
 ('Bunker Hill', ['Bunker Hill', 'caravan'], 'Bunker Hill is a Commonwealth settlement associated with caravan trade. Do not assume a particular player-dependent faction outcome.'),
 ('Sanctuary Hills', ['Sanctuary', 'Sanctuary Hills'], 'Sanctuary Hills is a pre-war residential neighborhood and a possible player settlement. Its current population and development depend on the playthrough.'),
 ('Ghoul', ['ghoul', 'ghouls'], 'Ghouls include people capable of ordinary conversation as well as feral ghouls. Do not treat every ghoul as feral or assume ordinary humans remember pre-war adulthood.'),
]

def words(text):
    return set(re.findall(r"[a-z0-9]+", text.casefold())) - {"the", "a", "an", "of", "and", "in", "at", "to", "for", "from", "with", "about"}


def is_index_page(page):
    text=page.get('extract','')
    categories=' '.join(c.get('title','') for c in page.get('categories',[]))
    return ('disambiguation' in categories.casefold() or bool(re.search(
        r'may refer to|can refer to|name of several|several characters throughout|list of .*characters',text[:500],re.I)))

def reference_text(page):
    raw=re.split(r'==\s*(?:Gameplay|Quests|Appearances|Behind the scenes|Notes|Bugs|References|Gallery|Inventory|Interactions)\s*==',page.get('extract',''),flags=re.I)[0]
    raw=re.sub(r'==[^=]+==',' ',raw)
    raw=re.sub(r'\s+',' ',raw).strip()
    selected=[]
    for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',raw):
        if re.search(r'quest|player character|objective|Pip-Boy|Sole Survivor can|depending on|until the|will be called',sentence,re.I):continue
        if sentence.endswith('...'):continue
        if len(' '.join(selected+[sentence]))>1200:break
        selected.append(sentence)
        if len(selected)>=4:break
    return ' '.join(selected)

def license_link(rights):
    if 'Attribution-ShareAlike' in rights.get('text','') and '4.0' in rights.get('text',''):
        return 'https://creativecommons.org/licenses/by-sa/4.0/'
    url=rights.get('url','')
    return url if url.startswith('https://') and '/wiki/Http' not in url else ORIGIN

def seed_records():
    return [dict(title=t, aliases=a, text=s, url=ORIGIN+'/wiki/'+quote(t.replace(' ', '_')), kind='curated', fetched=0, revision=None) for t,a,s in SEEDS]

class LoreLibrary:
    def __init__(self, data_dir, opener=urlopen, starter=True):
        self.folder = Path(data_dir)/'ai_writer'/'lore_library'
        self.opener = opener
        self.starter = starter

    def records(self):
        result = seed_records()
        wiki = {}
        paths = [Path(__file__).with_name('lore_starter.json')] if self.starter else []
        if self.folder.exists():paths.extend(sorted(self.folder.glob('*.json')))
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if (isinstance(item, dict) and item.get('kind') == 'wiki'
                        and isinstance(item.get('title'), str) and len(item['title']) <= 150
                        and isinstance(item.get('text'), str) and len(item['text']) <= 1800
                        and isinstance(item.get('aliases'), list)
                        and all(isinstance(a, str) and len(a)<=150 for a in item['aliases'])
                        and isinstance(item.get('fetched'), (int, float))
                        and item.get('url', '').startswith(ORIGIN+'/wiki/') and not is_index_page({'extract':item['text']})):
                        item['rights_url']=license_link({'text':item.get('license',''),'url':item.get('rights_url','')})
                        key=item['title'].casefold()
                        # Earlier versions cached shallow intros. Do not let those mask the richer starter pack.
                        if key not in wiki or item.get('facts') or not wiki[key].get('facts'):
                            wiki[key] = item
            except (OSError, ValueError):continue
        try:disabled=json.loads((self.folder/'hidden.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):disabled=[]
        return result + [r for key,r in wiki.items() if key not in disabled]

    def remove(self,title):
        self.folder.mkdir(parents=True,exist_ok=True)
        hidden=self.folder/'hidden.json'
        try:disabled=json.loads(hidden.read_text(encoding='utf-8'))
        except (OSError,ValueError):disabled=[]
        disabled=list(set(disabled+[title.casefold()]))
        hidden.write_text(json.dumps(disabled),encoding='utf-8')
        (self.folder/(hashlib.sha256(title.casefold().encode()).hexdigest()+'.json')).unlink(missing_ok=True)

    def _api(self, **params):
        req = Request(API+'?'+urlencode(dict(action='query', format='json', **params)),
                      headers={'User-Agent': 'PlaguesDJWriter/0.9 (local lore reference; https://github.com/kaotickj/plagues-voice-studio)'})
        with self.opener(req, timeout=6) as response:
            if not response.geturl().startswith(ORIGIN+'/'):
                raise ValueError('Unexpected wiki redirect.')
            raw = response.read(512001)
        if len(raw)>512000:
            raise ValueError('Wiki response exceeds reference limit.')
        data = json.loads(raw)
        if not isinstance(data, dict) or not isinstance(data.get('query'), dict):
            raise ValueError('Malformed wiki response.')
        if 'error' in data:
            raise ValueError('Wiki API could not complete this lookup.')
        return data.get('query', {})

    def lookup(self, topic, refresh=False):
        topic = ' '.join(topic.split())[:100]
        if len(topic)<3:
            raise ValueError('Enter a topic of at least three characters.')
        for entry in self.records():
            if entry['kind']=='wiki' and topic.casefold() in [a.casefold() for a in entry['aliases']] and not refresh and time.time()-entry['fetched']<TTL:
                return entry
        rights = {}
        def fetch(title):
            query = self._api(titles=title, redirects=1, prop='extracts|info|revisions|categories',
                exchars=5000, explaintext=1, inprop='url', rvprop='ids|timestamp', meta='siteinfo', siprop='rightsinfo', cllimit=100)
            rights.update(query.get('rightsinfo', {}))
            return list(query.get('pages', {}).values())
        pages = fetch(topic)
        if pages and is_index_page(pages[0]) and '(Fallout 4)' not in topic:
            pages = fetch(topic+' (Fallout 4)')
        if not pages or 'missing' in pages[0] or not pages[0].get('extract'):
            hits = self._api(list='search', srsearch=topic+' "Fallout 4"', srnamespace=0, srlimit=1).get('search', [])
            if not hits:
                raise ValueError('No matching Fallout 4 wiki reference found.')
            pages = fetch(hits[0]['title'])
        page = pages[0]
        text = reference_text(page)
        if not text or page.get('ns') != 0 or is_index_page(page) or 'disambiguation' in text.casefold():
            raise ValueError('This page is not a usable article introduction.')
        # Cross-game articles are labeled as reference, never silently accepted as FO4 canon.
        title = page['title'][:150]
        rev = (page.get('revisions') or [{}])[0]
        item = dict(title=title, aliases=[topic, title], text=text, kind='wiki',
            url=ORIGIN+'/wiki/'+quote(title.replace(' ', '_')), revision=rev.get('revid'),
            revision_timestamp=rev.get('timestamp'), fetched=time.time(),
            license=rights.get('text', 'Consult source page license'), rights_url=license_link(rights),
            attribution='Independent Fallout Wiki contributors; see source page for license/history',
            scope='Wiki reference: may cover other games or conditional quest events; apply only supported Fallout 4 facts.')
        try:
            from lore_enrichment import fetch_details
            facts, _ = fetch_details(item, opener=self.opener)
            if facts:
                item['facts'] = facts
                item['text'] = ' '.join(facts)[:1800]
                item['curation'] = 'Narrative facts selected for roles, relationships, motives and setting details.'
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Keep the usable bounded extract if narrative sections are unavailable.
        self.folder.mkdir(parents=True, exist_ok=True)
        dest = self.folder/(hashlib.sha256(title.casefold().encode()).hexdigest()+'.json')
        temp = dest.with_suffix('.tmp')
        temp.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(dest)
        hidden=self.folder/'hidden.json'
        if hidden.exists():
            disabled=json.loads(hidden.read_text(encoding='utf-8'))
            hidden.write_text(json.dumps([t for t in disabled if t!=title.casefold()]),encoding='utf-8')
        for old in sorted((p for p in self.folder.glob('*.json') if p.name!='hidden.json'), key=lambda p:p.stat().st_mtime, reverse=True)[200:]:
            old.unlink()
        return item

    def topics(self, text):
        result=[]
        for title, aliases, _ in SEEDS:
            if any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',text,re.I) for a in aliases):
                result.append(title)
        for record in self.records():
            names=record.get('aliases',[])+[re.sub(r' \(Fallout 4\)$','',record['title'])]
            if any(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text,re.I) for name in names):
                if record['title'] not in result:result.append(record['title'])
        # Only topic names leave the machine, not complete briefs or profiles.
        for name in re.findall(r'\b[A-Z][a-z]+(?:\s+(?:[A-Z][a-z]+|[0-9]+)){1,3}\b',text):
            if name not in result and name not in ('Stories From', 'Ad Promo'):
                result.append(name)
        return result[:3]

    def context(self, text, online=False, status=lambda s:None, cancelled=lambda:None, budget=3200):
        if online:
            for topic in self.topics(text):
                cancelled()
                try:
                    status('Checking wiki reference: '+topic)
                    self.lookup(topic)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    status('Wiki unavailable for '+topic+'; using saved lore. '+str(exc)[:120])
        query=words(text)
        def relevance(row):
            names=row.get('aliases',[])+[row['title']]
            exact=sum(bool(re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',text,re.I)) for name in set(names))
            return (exact*5+len(query & words(' '.join(names))), row['kind']=='wiki')
        candidates={}
        for record in self.records():
            key=record['title'].casefold()
            if key not in candidates or record['kind']=='wiki':candidates[key]=record
        ranked=sorted(candidates.values(),key=relevance,reverse=True)
        chosen=[];seen=set()
        budget=max(300,min(3200,budget))
        for row in ranked:
            key=row['title'].casefold()
            if key in seen or not relevance(row)[0]:continue
            facts=row.get('facts') or re.split(r'(?<=[.!?])\s+(?=[A-Z])',row['text'])
            compact=[]
            for fact in facts:
                if len(' '.join(compact+[fact]))>750:continue
                compact.append(fact)
                if len(compact)>=3:break
            if not compact:continue
            item={'title':row['title'],'text':' '.join(compact),'revision':row.get('revision')}
            if len(json.dumps(chosen+[item],ensure_ascii=False))>budget:continue
            chosen.append(item);seen.add(key)
            if len(chosen)>=3:break
        return json.dumps(chosen,ensure_ascii=False) if chosen else ''
