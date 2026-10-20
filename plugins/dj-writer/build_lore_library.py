"""Build a reviewed-topic Fallout 4 reference pack; preserve source/revision/license."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import quote
from lore_library import LoreLibrary, ORIGIN, words, license_link

TOPICS = {
'locations': '''Goodneighbor|The Third Rail|Memory Den|Hotel Rexford|Diamond City|Diamond City market|Bunker Hill|Sanctuary Hills|Red Rocket truck stop|Concord|Museum of Freedom|Cambridge Police Station|Cambridge|Lexington|Corvega assembly plant|The Castle|Boston Common|Swan's Pond|Park Street station|Vault 114|Vault 81|Vault 111|Vault 95|Vault 75|Fort Hagen|Fort Strong|The Prydwen|Boston Airport|The Institute|Old North Church|Railroad HQ|The Glowing Sea|Crater of Atom|Salem|Museum of Witchcraft|Covenant|Med-Tek Research|Mass Fusion building|General Atomics Galleria|Robotics disposal ground|Saugus Ironworks|Finch farm|Abernathy farm|Greentop Nursery|Graygarden|The Slog|Warwick homestead|Sunshine Tidings co-op|Starlight Drive In|Hangman's Alley|Jamaica Plain|Egret Tours Marina|County crossing|Taffington boathouse|Oberland station|Tenpines Bluff|Somerville Place|Spectacle Island|Kingsport Lighthouse|Nordhagen Beach|Coastal cottage|Outpost Zimonja|Revere Beach station|Trinity Tower|Hubris Comics (Fallout 4)|Cabot House|Pickman Gallery|Faneuil Hall|University Point|Quincy|Quincy ruins|Atom Cats garage|Drumlin Diner (Fallout 4)|Easy City Downs|Combat Zone|Fiddler's Green Trailer Estates|Fort Independence|Hester's Consumer Robotics|Shamrock Taphouse''',
'people': '''Nick Valentine|Piper Wright|Hancock|Magnolia|Irma|Doctor Amari|Whitechapel Charlie|KL-E-0|Daisy (Fallout 4)|Rufus Rubins|Hotel Rexford staff|Bobbi No-Nose|Fahrenheit|Edward Deegan|Vadim Bobrov|Yefim Bobrov|Travis Miles|Ellie Perkins|Moe Cronin|Arturo Rodriguez|Myrna|Percy (Fallout 4)|Doctor Sun|Sheng Kawolski|Geneva|McDonough|Preston Garvey|Sturges|Mama Murphy|Jun Long|Marcy Long|Codsworth|Dogmeat (Fallout 4)|Cait|Curie|Paladin Danse|Deacon|Robert MacCready|Strong|X6-88|Proctor Teagan|Arthur Maxson|Desdemona|Tinker Tom|Deacon (Fallout 4)|Doctor Carrington|Glory|Trashcan Carla|Cricket|Lucas Miller|Doc Weathers|Deb|Kessler|Old Man Stockton|Honest Dan|Arlen Glass|Holly (Fallout 4)|Wiseman|Duke (Fallout 4)|Zeke (Fallout 4)|Rowdy''',
'factions': '''Commonwealth Minutemen|The Railroad|Brotherhood of Steel (Fallout 4)|Gunners|Triggermen|Forged|Atom Cats|Children of Atom|Raider (Fallout 4)''',
'creatures_and_daily_life': '''Brahmin (Fallout 4)|Radstag (Fallout 4)|Mirelurk (Fallout 4)|Deathclaw (Fallout 4)|Yao guai (Fallout 4)|Feral ghoul (Fallout 4)|Ghoul|Super mutant (Fallout 4)|Synth|Protectron (Fallout 4)|Mister Handy (Fallout 4)|Assaultron (Fallout 4)|Eyebot (Fallout 4)|Mole rat (Fallout 4)|Radroach (Fallout 4)|Bloatfly (Fallout 4)|Bloodbug (Fallout 4)|Stingwing (Fallout 4)|Mutfruit (Fallout 4)|Tato (Fallout 4)|Brahmin milk|Purified water (Fallout 4)|Nuka-Cola (Fallout 4)|Diamond City Radio|Radio Freedom|Bottlecap (Fallout 4)|Caravan|Radstorm|The Commonwealth|Great War|Radiation|Power armor (Fallout 4)'''
}

def curate(page, requested, group, rights):
    title=page.get('title','')
    raw = re.split(r'==\s*(?:Gameplay|Layout|Quests|Appearances|Behind the scenes|Notes|Bugs|References|Gallery|Inventory|Interactions|Related quests)\s*==', page.get('extract',''), flags=re.I)[0]
    raw = re.sub(r'==[^=]+==', ' ', raw)
    text=re.sub(r'\s+',' ',raw).strip()
    categories=[c['title'].removeprefix('Category:') for c in page.get('categories',[])]
    reasons=[]
    if 'missing' in page or page.get('ns')!=0 or not text:reasons.append('missing or empty article')
    if 'disambiguation' in ' '.join(categories).casefold() or 'may refer to' in text[:150].casefold():reasons.append('ambiguous topic')
    # A resolved search result is not sufficient: require matching identity.
    ignored={'fallout','4','the','of','a'}
    a=words(requested)-ignored;b=words(title)-ignored
    if not a or not a<=b:reasons.append('resolved title differs from requested topic')
    scoped=any('fallout 4' in c.casefold() for c in categories) or bool(re.search(r'\bFallout 4\b',text))
    if not scoped:reasons.append('Fallout 4 scope needs human review')
    # Avoid silently presenting conditional quests, game systems or later outcomes as radio history.
    sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z])',text)
    kept=[]
    for sentence in sentences:
        if re.search(r'\b(?:quest|questline|player can|can be killed|depending on|if the player|ending|kill(?:s|ed)?|dies|murdered)\b',sentence,re.I):continue
        if re.search(r'\b(?:Fallout 76|Fallout: New Vegas|Fallout 3|Fallout 2|Fallout Shelter|Fallout: The Board Game|Fallout: Wasteland Warfare|Fallout: The Roleplaying Game)\b',sentence):continue
        if re.search(r'\b(?:also appears|also a character|player character)\b',sentence,re.I):continue
        if sentence.endswith('...'):continue
        if len(' '.join(kept+[sentence]))>900:break
        kept.append(sentence)
        if len(kept)>=3:break
    excerpt=' '.join(kept).strip()
    if len(excerpt)<45:reasons.append('no useful non-quest introductory facts')
    revision=(page.get('revisions') or [{}])[0]
    item=dict(title=title,aliases=list(dict.fromkeys([requested,title])),text=excerpt,kind='wiki',
        url=ORIGIN+'/wiki/'+quote(title.replace(' ','_')),revision=revision.get('revid'),revision_timestamp=revision.get('timestamp'),
        fetched=time.time(),license=rights.get('text','Consult source license'),rights_url=license_link(rights),
        attribution='Independent Fallout Wiki contributors',category=group,categories=categories,
        scope='Fallout 4 reference. Quest/player outcomes are not established. Do not invent additional services, relationships or facts.',
        curation='Topic identity and Fallout 4 scope checked; quest/outcome and cross-game sentences filtered. Not an exhaustive factual audit.')
    return item,reasons

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--delay',type=float,default=1)
    parser.add_argument('--topics',type=Path,help='Optional JSON mapping of category to pipe-separated topics')
    parser.add_argument('--merge',action='store_true',help='Retain previously accepted entries in output')
    args=parser.parse_args()
    library=LoreLibrary(args.output.parent/'fetch-cache')
    catalogue=json.loads(args.topics.read_text(encoding='utf-8')) if args.topics else TOPICS
    accepted=json.loads(args.output.read_text(encoding='utf-8')) if args.merge and args.output.exists() else []
    held=[]
    for group,topics in catalogue.items():
        names=topics.split('|')
        for offset in range(0,len(names),10):
            chunk=names[offset:offset+10]
            query=library._api(titles='|'.join(chunk),redirects=1,prop='extracts|revisions|categories',
                exintro=1,explaintext=1,exlimit=20,rvprop='ids|timestamp',cllimit=500,meta='siteinfo',siprop='rightsinfo')
            pages=list(query.get('pages',{}).values())
            aliases={r['from']:r['to'] for r in query.get('redirects',[])}
            aliases.update({r['from']:r['to'] for r in query.get('normalized',[])})
            for name in chunk:
                canonical=name
                for _ in range(5):canonical=aliases.get(canonical,canonical)
                page=next((p for p in pages if p.get('title')==canonical),{})
                if page.get('extract') and 'missing' not in page:
                    try:
                        full=library._api(titles=page['title'],prop='extracts',explaintext=1,exchars=5000)
                        raw_page=next(iter(full.get('pages',{}).values()),{})
                        if raw_page.get('extract'):page['extract']=raw_page['extract']
                    except (OSError,ValueError):pass
                    time.sleep(max(.2,args.delay))
                item,reasons=curate(page,name,group,query.get('rightsinfo',{}))
                if reasons:held.append(dict(requested=name,resolved=item['title'],reasons=reasons,source=item['url'],text=page.get('extract','')[:1800]))
                elif not any(r['title']==item['title'] for r in accepted):accepted.append(item)
            print(f'{group}: {min(offset+10,len(names))}/{len(names)}; accepted {len(accepted)}, held {len(held)}',flush=True)
            time.sleep(max(.2,args.delay))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.report.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(accepted,ensure_ascii=False,indent=2),encoding='utf-8')
    report=dict(created=datetime.now(timezone.utc).isoformat(),requested=sum(len(v.split('|')) for v in catalogue.values()),
        accepted=len(accepted),held=held,groups={g:sum(r['category']==g for r in accepted) for g in TOPICS},
        method='Approved topic catalogue; automatic identity/scope/quest filtering followed by editorial review. Excerpts retain source revision and license.')
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='held'},indent=2))

if __name__=='__main__':main()
