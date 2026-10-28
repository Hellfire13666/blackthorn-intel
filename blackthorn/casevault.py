"""Offline case profiles for public research. No network or automatic personal-data collection."""
import datetime as dt
import json
import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def folder_for(out):
    root=Path(out).expanduser()/'Cases'
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    if root.is_symlink(): raise ValueError('Case folder cannot be a symlink')
    return root

def case_file(folder,case_id):
    if not re.fullmatch(r'BT-[0-9a-f]{12}',case_id):raise ValueError('Invalid case ID')
    p=folder/(case_id+'.json')
    if p.is_symlink():raise ValueError('Case file cannot be a symlink')
    return p

def read_case(folder,case_id):
    path=case_file(folder,case_id)
    if not path.is_file():raise ValueError('Case not found: '+case_id)
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('id')!=case_id:raise ValueError('Case ID mismatch')
    return data

def write_new(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False)

def update(path,data):
    if path.is_symlink():raise ValueError('Case file cannot be symlink')
    tmp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
    try:
        write_new(tmp,data)
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def run(command,out):
    command=command.strip()
    folder=folder_for(out)
    if command=='help':
        return {'module':11,'status':'local case commands','commands':[
            'create <case title>', 'list', 'show BT-<id>',
            'note BT-<id> | <research note>',
            'link BT-<id> | https://public.example/source | <description>'],
            'privacy':'Local research notes only. Avoid private personal details.'}
    if command=='list':
        cases=[]
        for p in sorted(folder.glob('BT-*.json'))[:250]:
            try:
                if p.is_symlink():continue
                item=read_case(folder,p.stem)
                cases.append({'id':item['id'],'title':item.get('title',''), 'updated_utc':item.get('updated_utc',''), 'entries':len(item.get('entries',[]))})
            except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError):continue
        return {'module':11,'status':'local cases listed','cases':cases,'count':len(cases)}
    if command.startswith('create '):
        title=command[7:].strip()
        if not 2<=len(title)<=120 or any(ord(c)<32 for c in title):raise ValueError('Case title must be 2-120 printable characters')
        ident='BT-'+secrets.token_hex(6); t=now()
        data={'id':ident,'title':title,'created_utc':t,'updated_utc':t,'entries':[],
              'notice':'User-supplied research; references are unverified until independently checked.'}
        write_new(case_file(folder,ident),data)
        return {'module':11,'status':'case created','case_id':ident,'title':title,'entries':0}
    parts=command.split(maxsplit=1)
    if len(parts)==2 and parts[0]=='show':
        data=read_case(folder,parts[1].strip())
        return {'module':11,'status':'case loaded','case':data}
    if len(parts)==2 and parts[0] in ('note','link'):
        pieces=[p.strip() for p in parts[1].split('|')]
        if parts[0]=='note':
            if len(pieces)!=2 or not 1<=len(pieces[1])<=3000:raise ValueError('Use: note BT-id | <text up to 3000 characters>')
            case_id,text=pieces
            entry={'type':'research note','text':text,'created_utc':now(),'verified':False}
        else:
            if len(pieces)!=3 or not 1<=len(pieces[2])<=500:raise ValueError('Use: link BT-id | https://source | <description>')
            case_id,url,description=pieces
            parsed=urlparse(url)
            if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password or len(url)>2048:\
                raise ValueError('Evidence source must be an HTTPS URL without credentials')
            entry={'type':'public source reference','url':url,'description':description,'created_utc':now(),'verified':False}
        data=read_case(folder,case_id)
        if len(data.get('entries',[]))>=500:raise ValueError('Case has reached its 500-entry limit')
        data['entries'].append(entry);data['updated_utc']=now()
        update(case_file(folder,case_id),data)
        return {'module':11,'status':'case updated','case_id':case_id,'entries':len(data['entries']),'latest_entry':entry}
    raise ValueError('CASEVAULT: use help, list, create <title>, show <id>, note <id> | <text>, link <id> | <URL> | <description>')
