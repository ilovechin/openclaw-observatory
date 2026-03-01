#!/usr/bin/env python3
import json, subprocess, datetime, os, re
from pathlib import Path

BASE = '/root/.openclaw/workspace/openclaw-observatory'
WS = Path('/root/.openclaw/workspace')
CFG = Path('/root/.openclaw/openclaw.json')


def run(cmd, default=''):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return default


def run_json(cmd, default=None):
    if default is None:
        default = {}
    out = run(cmd, '')
    if not out:
        return default
    try:
        return json.loads(out)
    except Exception:
        return default


def parse_mem_mb():
    out = run('free -m')
    for line in out.splitlines():
        if line.startswith('Mem:'):
            p = re.split(r'\s+', line)
            if len(p) >= 7:
                t, u, f, a = int(p[1]), int(p[2]), int(p[3]), int(p[6])
                return {'totalMB': t, 'usedMB': u, 'freeMB': f, 'availableMB': a, 'usedPct': round((u / t) * 100, 1) if t else 0}
    return {}


def parse_disk_root():
    p = re.split(r'\s+', run('df -h / | tail -n 1'))
    if len(p) >= 6:
        return {'size': p[1], 'used': p[2], 'avail': p[3], 'usedPct': p[4], 'mount': p[5]}
    return {}


def parse_load():
    p = run('cat /proc/loadavg').split()
    if len(p) >= 3:
        return {'1m': p[0], '5m': p[1], '15m': p[2]}
    return {}




def read_safe_text(path, limit=4000):
    try:
        t = Path(path).read_text(encoding='utf-8')
        return t[:limit]
    except Exception:
        return ''


def ping_url(url):
    code = run(f"curl -L -s -o /dev/null -w '%{{http_code}}' --max-time 8 '{url}'", '000')
    return int(code) if code.isdigit() else 0


def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = k.lower()
            if any(s in lk for s in ['token', 'secret', 'password', 'api_key', 'apikey', 'authorization']):
                out[k] = '***REDACTED***'
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    return obj


def file_stats():
    total = int(run("cd /root/.openclaw/workspace && find . -type f | wc -l", '0') or 0)
    md = int(run("cd /root/.openclaw/workspace && find . -type f -name '*.md' | wc -l", '0') or 0)
    py = int(run("cd /root/.openclaw/workspace && find . -type f -name '*.py' | wc -l", '0') or 0)
    html = int(run("cd /root/.openclaw/workspace && find . -type f -name '*.html' | wc -l", '0') or 0)
    return {'totalFiles': total, 'markdownFiles': md, 'pythonFiles': py, 'htmlFiles': html}


def recent_commits(path):
    return run(f"cd {path} && git log --oneline -n 5", '')


def cron_recent_runs(job_id, limit=2):
    out = run_json(f"openclaw cron runs --id {job_id} --limit {limit}", {})
    return out.get("entries", []) if isinstance(out, dict) else []


def workspace_tree(depth=3):
    return run(f"cd /root/.openclaw/workspace && find . -maxdepth {depth} | sort", "")




def read_json(path):
    p=Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}

def read_text(path,limit=12000):
    p=Path(path)
    if not p.exists():
        return ''
    try:
        return p.read_text(encoding='utf-8')[:limit]
    except Exception:
        return ''

def load_clawd_index():
    p=Path('/root/.openclaw/workspace/openclaw-observatory/data/clawd_index.json')
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}


def main():
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    status = run_json('openclaw status --usage --json', {})
    mem = run_json('openclaw memory status --json', [])
    cron = run_json('openclaw cron list --json', {'jobs': []})
    provider = (status.get('usage', {}).get('providers') or [{}])[0]
    wins = provider.get('windows') or []
    w5 = wins[0]['usedPercent'] if len(wins) > 0 else None
    day = wins[1]['usedPercent'] if len(wins) > 1 else None

    cron_jobs = []
    for j in cron.get('jobs', []):
        st = j.get('state', {})
        cron_jobs.append({
            'id': j.get('id'), 'name': j.get('name'), 'status': st.get('lastStatus') or 'idle',
            'next': st.get('nextRunAtMs'), 'last': st.get('lastRunAtMs'), 'errors': st.get('consecutiveErrors', 0)
        })

    memory_ready = True
    for a in mem:
        if isinstance(a, dict) and a.get('status', {}).get('chunks', 0) <= 0:
            memory_ready = False
            break

    websites = {
        'personal': 'https://ilovechin.github.io/',
        'crysttao': 'https://ilovechin.github.io/crysttao-site/',
        'observatory': 'https://ilovechin.github.io/openclaw-observatory/'
    }

    cfg = {}
    if CFG.exists():
        try:
            cfg = redact(json.loads(CFG.read_text(encoding='utf-8')))
        except Exception:
            cfg = {}

    skills = run('cd /root/.openclaw/workspace && clawhub list', '')

    data = {
        'generatedAt': now,
        'identity': {
            'name': '锦的虾🦐',
            'model': status.get('agents', {}).get('defaultModel') or 'openai-codex/gpt-5.3-codex',
            'provider': provider.get('provider', 'unknown')
        },
        'usage': status.get('usage', {}),
        'usageQuick': {'fiveHourUsedPct': w5, 'dayUsedPct': day, 'plan': provider.get('plan')},
        'system': {
            'uptime': run('uptime -p', 'unknown'),
            'load': parse_load(),
            'memory': parse_mem_mb(),
            'diskRoot': parse_disk_root(),
            'processCounts': {
                'openclawGateway': int(run('pgrep -fc openclaw-gateway', '0') or 0),
                'arbWatcher': int(run('pgrep -fc arb_watcher.py', '0') or 0)
            }
        },
        'openclaw': {
            'gatewayOk': bool(status.get('gateway', {}).get('probe', {}).get('ok', True)) if isinstance(status.get('gateway'), dict) else True,
            'memoryReady': memory_ready,
            'agentCount': len(status.get('agents', {}).get('list', [])) if isinstance(status.get('agents'), dict) else 0,
            'cronJobs': cron_jobs,
            'channelSummary': status.get('channelSummary', []),
            'safeConfig': cfg,
            'skills': skills,
            'modelLibrary': {
                'primary': (((cfg.get('agents') or {}).get('defaults') or {}).get('model') or {}).get('primary') if isinstance(((cfg.get('agents') or {}).get('defaults') or {}).get('model'), dict) else ((cfg.get('agents') or {}).get('defaults') or {}).get('model'),
                'fallbacks': (((cfg.get('agents') or {}).get('defaults') or {}).get('model') or {}).get('fallbacks', []) if isinstance(((cfg.get('agents') or {}).get('defaults') or {}).get('model'), dict) else [],
                'registeredModels': list((((cfg.get('agents') or {}).get('defaults') or {}).get('models') or {}).keys())
            },
            'sessionPolicy': (cfg.get('session') or {}),
            'successRate': {
                'cronOk': (len([j for j in cron_jobs if str(j.get('status','')).lower()=='ok']) / max(1,len(cron_jobs))),
                'cronTotal': len(cron_jobs)
            }
        },
        'workspace': {
            'fileStats': file_stats(),
            'recentCommitsMain': recent_commits('/root/.openclaw/workspace'),
            'recentCommitsCrysttao': recent_commits('/root/.openclaw/workspace/crysttao-site'),
            'recentCommitsObservatory': recent_commits('/root/.openclaw/workspace/openclaw-observatory')
        },
        'persona': {
            'soul': read_safe_text('/root/.openclaw/workspace/SOUL.md', 5000),
            'identity': read_safe_text('/root/.openclaw/workspace/IDENTITY.md', 2000),
            'userProfile': read_safe_text('/root/.openclaw/workspace/USER.md', 3000)
        },
        'websites': {'urls': websites, 'httpStatus': {k: ping_url(v) for k, v in websites.items()}},
        'knowledgeBase': {
            'clawd': load_clawd_index()
        },
        'memuLite': {
            'documentsIndex': read_json('/root/.openclaw/workspace/memory/fs/resources/documents/index.json'),
            'conversationsIndex': read_json('/root/.openclaw/workspace/memory/fs/resources/conversations/index.json'),
            'syncReport': read_json('/root/.openclaw/workspace/memory/fs/links/sync-report.json'),
            'intentCandidates': read_text('/root/.openclaw/workspace/memory/fs/context/pending/intent-candidates.md', 8000),
            'graph': read_text('/root/.openclaw/workspace/memory/fs/links/graph.md', 12000)
        },
        'raw': {
            'statusUsageJson': status,
            'memoryStatusText': run('openclaw memory status', ''),
            'cronListJson': cron,
            'doctorText': run('openclaw doctor', ''),
            'healthText': run('openclaw health', ''),
            'gatewayStatusText': run('openclaw gateway status', ''),
            'sessionsText': run('openclaw sessions', ''),
            'pluginsWarnings': run("openclaw status --usage --json 2>&1 | grep -i '\[plugins\]'", ''),
            'workspaceTree': workspace_tree(3),
            'modelConfigRaw': ((cfg.get('agents') or {}).get('defaults') or {}).get('model'),
            'cronRecentRuns': {j.get('name','unknown'): cron_recent_runs(j.get('id'), 2) for j in cron.get('jobs', []) if j.get('id')}
        }
    }

    os.makedirs(BASE + '/data', exist_ok=True)
    with open(BASE + '/data/current.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    hp = BASE + '/data/history.json'
    hist = []
    if os.path.exists(hp):
        try:
            hist = json.loads(Path(hp).read_text(encoding='utf-8'))
        except Exception:
            hist = []
    hist.append({'generatedAt': now, 'model': data['identity']['model'], 'w5': w5, 'day': day,
                 'gatewayOk': data['openclaw']['gatewayOk'],
                 'memUsedPct': data['system']['memory'].get('usedPct'),
                 'diskUsedPct': data['system']['diskRoot'].get('usedPct')})
    hist = hist[-1000:]

    # derive lightweight alert/timeline from cron + health
    events=[]
    for j in cron_jobs[:40]:
        st=str(j.get('status','idle')).lower()
        level='info'
        if st not in ['ok','idle']: level='critical'
        elif (j.get('errors') or 0)>0: level='warn'
        events.append({
            'ts': j.get('last') or j.get('next'),
            'job': j.get('name'),
            'status': st,
            'level': level,
            'errors': j.get('errors',0)
        })
    data['alerts']={
        'critical': len([e for e in events if e['level']=='critical']),
        'warn': len([e for e in events if e['level']=='warn']),
        'info': len([e for e in events if e['level']=='info'])
    }
    data['eventsTimeline']=sorted(events, key=lambda x: (x.get('ts') or 0), reverse=True)[:60]
    with open(hp, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
