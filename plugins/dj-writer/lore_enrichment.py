"""Extract descriptive wiki paragraphs, excluding navigation and game-system sections."""
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from lore_library import API, ORIGIN

EDITOR_NOTES={
'Nick Valentine': ['Nick Valentine is a synth private detective based at the Valentine Detective Agency in Diamond City. Ellie Perkins is his assistant.', 'His visibly mechanical appearance can draw suspicion, but he is generally respected in Diamond City.', 'He is skilled at investigation and hacking computers.', 'Do not assume the player has rescued or recruited him. His private memories and Institute history are not automatically public knowledge.'],
'The Third Rail': ['The Third Rail is a music club in Goodneighbor, inside the repurposed Scollay Square subway station.', 'Hancock owns the club. Whitechapel Charlie, a Mister Handy, manages it and operates the bar.', 'Magnolia sings on a small stage. Do not invent utilities, lodging or a regional business monopoly.'],
'Piper Wright': [
 'Piper Wright is an investigative reporter in Diamond City and publishes Publick Occurrences.',
 'Nat is her younger sister. Piper and Nat moved to Diamond City together.',
 'She persists in investigating wrongdoing despite threats and public criticism; she treats getting into trouble as part of pursuing the truth.',
 'She has a rapport with Nick Valentine because both investigate other people’s problems.',
 'She is sympathetic toward synths and critical of the Brotherhood of Steel’s self-interest, technology hoarding and anti-synth views.',
 'Her allegations about Mayor McDonough are allegations, not proof available to a radio host. Do not establish quest resolutions or a romance with the player.' ],
'Memory Den':[
 'The Memory Den is in Goodneighbor and uses memory loungers to let clients experience memories.',
 'Irma and Doctor Amari work there. Memory experiences, not an invented bar or water business, define its role.' ],
'Dogmeat (Fallout 4)':[
 'Dogmeat is a dog encountered at the Red Rocket truck stop southeast of Sanctuary Hills.',
 'He can accompany travelers, sniff trails and help find people or objects. He does not speak human dialogue.',
 'Do not assume the player has recruited him or completed the quests associated with him.' ],
'Mayor McDonough':[
 'McDonough is the mayor of Diamond City. His public authority and conflict with Piper can support stories about city politics and reporting.',
 'A radio host does not automatically know his hidden identity or Institute connections. Do not reveal secrets or establish a quest outcome without an editor brief.' ],
}

class NarrativeParser(HTMLParser):
    def __init__(self):
        super().__init__();self.skip=0;self.paragraph=None;self.heading='Introduction';self.h=None;self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('table','script','style','sup'):self.skip+=1
        if tag in ('h2','h3'):self.h=[]
        if tag=='p' and not self.skip:self.paragraph=[]
    def handle_endtag(self,tag):
        if tag in ('table','script','style','sup'):self.skip=max(0,self.skip-1)
        if tag in ('h2','h3') and self.h is not None:self.heading=''.join(self.h).strip();self.h=None
        if tag=='p' and self.paragraph is not None:
            text=re.sub(r'\s+',' ',''.join(self.paragraph)).strip();self.paragraph=None
            if text:self.rows.append((self.heading,text))
    def handle_data(self,data):
        if not self.skip:
            if self.h is not None:self.h.append(data)
            if self.paragraph is not None:self.paragraph.append(data)

def useful_sentences(rows):
    candidates=[]
    for heading,paragraph in rows:
        if not re.search(r'introduction|background|personality|relationship|history|overview|description',heading,re.I):continue
        if re.search(r'quest|gameplay|appearances|behind the scenes|references',heading,re.I):continue
        count=0
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z])',paragraph):
            if re.search(r'Fallout Shelter|Fallout: The Board Game|Fallout: Wasteland Warfare|also appears|player character|quest|gameplay|hit points|level \d|experience points|Sole Survivor can|depending on|if the player|can be recruited|objective|Pip-Boy',sentence,re.I):continue
            if len(sentence)<35 or len(sentence)>500:continue
            if sentence in [c[1] for c in candidates]:continue
            score=3*bool(re.search(r'personality|relationship',heading,re.I))
            score+=sum(bool(re.search(term,sentence,re.I)) for term in (
                r'works|runs|manages|operates|owns|trades',r'newspaper|Publick|reporter|journalist|investigat',
                r'sister|brother|friend|assistant|rapport',r'truth|sympathetic|dislike|prefers|enjoys|believes',
                r'bar|club|merchant|singer|caravan|repair|garden|lodging|customer'))
            score-=sum(bool(re.search(term,sentence,re.I)) for term in (r'murdered|experiments|prototype',r'originally|for years|before the Great War'))
            candidates.append((score,sentence))
            count+=1
            if count>=2:break
    chosen=[]
    for score,sentence in sorted(candidates,key=lambda row:row[0],reverse=True):
        if len(' '.join(chosen+[sentence]))>1600:continue
        chosen.append(sentence)
        if len(chosen)>=7:break
    return chosen

def fetch_details(entry,opener=urlopen):
    params=dict(action='parse',format='json',prop='text',disableeditsection=1,disabletoc=1)
    if entry.get('revision'):params['oldid']=entry['revision']
    else:params['page']=entry['title']
    req=Request(API+'?'+urlencode(params),headers={'User-Agent':'PlaguesDJWriter/0.9 (Fallout 4 reference curation; https://github.com/kaotickj/plagues-voice-studio)'})
    with opener(req,timeout=12) as r:
        if not r.geturl().startswith(ORIGIN+'/'):raise ValueError('Unexpected wiki redirect')
        raw=r.read(1500001)
    if len(raw)>1500000:raise ValueError('Article exceeds curation limit')
    data=json.loads(raw)
    if 'error' in data:raise ValueError(data['error'].get('info','Wiki parsing failed'))
    parser=NarrativeParser();parser.feed(data['parse']['text']['*'])
    facts=EDITOR_NOTES.get(entry['title'],useful_sentences(parser.rows))
    return facts,parser.rows
