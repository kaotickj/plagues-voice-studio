"""Per-host character candidates with source provenance and explicit editorial status."""
import hashlib
import json
from pathlib import Path
import re
import time

HOSTS=('Tal Conroy','Hattie Boggs','Mister The Plague')
class CharacterLibrary:
    def __init__(self,data_dir):self.path=Path(data_dir)/'ai_writer'/'dj_characters.json'
    def load(self):
        if not self.path.exists():return []
        data=json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data,list) or any(not isinstance(r,dict) or r.get('dj') not in HOSTS or r.get('status') not in ('candidate','accepted','rejected') or not isinstance(r.get('text'),str) for r in data):
            raise ValueError('Invalid character library; file left unchanged.')
        return data
    def save(self,rows):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(self.path)
    def add(self,dj,text,source='editor',status='accepted',source_id=''):
        if dj not in HOSTS:raise ValueError('Unknown DJ')
        text=' '.join(text.split())[:450]
        if not text:return False
        identity=hashlib.sha256((dj+' '+text.casefold()).encode()).hexdigest()
        rows=self.load()
        if any(r['id']==identity for r in rows):return False
        rows.append(dict(id=identity,dj=dj,text=text,status=status,source=source,source_id=source_id,created=time.time()))
        # Retain decisions; when full, stop collecting rather than erase accepted history.
        if len(rows)>1500:return False
        self.save(rows);return True
    def collect(self,dj,script):
        script_id=hashlib.sha256(script.encode()).hexdigest()
        count=0
        for sentence in re.split(r'(?<=[.!?])\s+',re.sub(r'\[[^\]]*\]','',script)):
            # Quoted dialogue belongs to its speaker, not automatically to the host.
            if any(q in sentence for q in ('"','“','”')):continue
            if re.search(r"\b(?:I (?:always|never|usually|prefer|love|hate|like|dislike|grew up|used to|can[’']t stand|collect|keep|remember my)|I[’']m (?:fond|afraid)|My (?:mother|father|brother|sister|parents|wife|husband))\b",sentence,re.I):
                count+=self.add(dj,sentence,'generated draft: candidate only','candidate',script_id)
            if count>=5:break
        return count
    def decide(self,identity,status):
        if status not in ('accepted','rejected','candidate'):raise ValueError('Invalid character-note status')
        rows=self.load()
        for row in rows:
            if row['id']==identity:row['status']=status;row['reviewed']=time.time()
        self.save(rows)
    def context(self,dj):
        chosen=[]
        for row in self.load():
            if row['dj']==dj and row['status']=='accepted':
                if len(json.dumps(chosen+[row['text']]))>1000:break
                chosen.append(row['text'])
                if len(chosen)>=4:break
        return json.dumps(chosen,ensure_ascii=False) if chosen else ''
