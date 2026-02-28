#!/usr/bin/env python3
import json,subprocess,datetime,os
BASE='/root/.openclaw/workspace/openclaw-observatory'

def run(cmd):
    return subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.DEVNULL)

def main():
    now=datetime.datetime.utcnow().isoformat()+'Z'
    status=json.loads(run('openclaw status --usage --json'))
    mem=json.loads(run('openclaw memory status --json'))
    cron=json.loads(run('openclaw cron list --json'))
    provider=(status.get('usage',{}).get('providers') or [{}])[0]
    wins=provider.get('windows') or []
    w5=wins[0]['usedPercent'] if len(wins)>0 else None
    day=wins[1]['usedPercent'] if len(wins)>1 else None
    data={
      'generatedAt': now,
      'model': (status.get('agents',{}).get('defaultModel') or 'openai-codex/gpt-5.3-codex'),
      'usage': status.get('usage',{}),
      'gatewayOk': bool(status.get('gateway',{}).get('probe',{}).get('ok', True)) if isinstance(status.get('gateway'),dict) else True,
      'memoryReady': all((a.get('status',{}).get('chunks',0)>0 for a in mem if isinstance(a,dict))),
      'agentCount': len(status.get('agents',{}).get('list',[])) if isinstance(status.get('agents'),dict) else 0,
      'cronJobs': [
        {'name':j.get('name'), 'status': j.get('state',{}).get('lastStatus') or 'idle', 'next': j.get('state',{}).get('nextRunAtMs')}
        for j in cron.get('jobs',[])
      ]
    }
    os.makedirs(BASE+'/data',exist_ok=True)
    with open(BASE+'/data/current.json','w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    hist=[]
    hp=BASE+'/data/history.json'
    if os.path.exists(hp):
      try: hist=json.load(open(hp))
      except: hist=[]
    hist.append({'generatedAt':now,'model':data['model'],'w5':w5,'day':day})
    hist=hist[-500:]
    with open(hp,'w',encoding='utf-8') as f: json.dump(hist,f,ensure_ascii=False,indent=2)

if __name__=='__main__':
    main()
