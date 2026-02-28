#!/usr/bin/env python3
import json, subprocess, datetime, os, re
BASE='/root/.openclaw/workspace/openclaw-observatory'


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
    out = run("free -m")
    # Mem: total used free shared buff/cache available
    for line in out.splitlines():
        if line.startswith('Mem:'):
            p = re.split(r'\s+', line)
            if len(p) >= 7:
                total = int(p[1]); used = int(p[2]); free = int(p[3]); avail = int(p[6])
                used_pct = round((used / total) * 100, 1) if total else 0
                return {'totalMB': total, 'usedMB': used, 'freeMB': free, 'availableMB': avail, 'usedPct': used_pct}
    return {}


def parse_disk_root():
    out = run("df -h / | tail -n 1")
    p = re.split(r'\s+', out)
    # filesystem size used avail use% mount
    if len(p) >= 6:
        return {'size': p[1], 'used': p[2], 'avail': p[3], 'usedPct': p[4], 'mount': p[5]}
    return {}


def parse_uptime():
    return run("uptime -p", "unknown")


def parse_load():
    out = run("cat /proc/loadavg", "")
    p = out.split()
    if len(p) >= 3:
        return {'1m': p[0], '5m': p[1], '15m': p[2]}
    return {}


def ping_url(url):
    # lightweight status check
    code = run(f"curl -L -s -o /dev/null -w '%{{http_code}}' --max-time 8 '{url}'", "000")
    return int(code) if code.isdigit() else 0


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
            'id': j.get('id'),
            'name': j.get('name'),
            'status': st.get('lastStatus') or 'idle',
            'next': st.get('nextRunAtMs'),
            'last': st.get('lastRunAtMs'),
            'errors': st.get('consecutiveErrors', 0),
            'schedule': j.get('schedule', {})
        })

    gateway_probe_ok = True
    if isinstance(status.get('gateway'), dict):
        gateway_probe_ok = bool(status.get('gateway', {}).get('probe', {}).get('ok', True))

    memory_ready = True
    for a in mem:
        if isinstance(a, dict):
            if a.get('status', {}).get('chunks', 0) <= 0:
                memory_ready = False
                break

    websites = {
        'personal': 'https://ilovechin.github.io/',
        'crysttao': 'https://ilovechin.github.io/crysttao-site/',
        'observatory': 'https://ilovechin.github.io/openclaw-observatory/'
    }
    site_health = {k: ping_url(v) for k, v in websites.items()}

    data = {
        'generatedAt': now,
        'identity': {
            'name': '锦的虾🦐',
            'model': status.get('agents', {}).get('defaultModel') or 'openai-codex/gpt-5.3-codex',
            'provider': provider.get('provider', 'unknown')
        },
        'usage': status.get('usage', {}),
        'usageQuick': {
            'fiveHourUsedPct': w5,
            'dayUsedPct': day,
            'plan': provider.get('plan')
        },
        'system': {
            'uptime': parse_uptime(),
            'load': parse_load(),
            'memory': parse_mem_mb(),
            'diskRoot': parse_disk_root(),
            'processCounts': {
                'openclawGateway': int(run("pgrep -fc openclaw-gateway", "0") or 0),
                'arbWatcher': int(run("pgrep -fc arb_watcher.py", "0") or 0)
            }
        },
        'openclaw': {
            'gatewayOk': gateway_probe_ok,
            'memoryReady': memory_ready,
            'agentCount': len(status.get('agents', {}).get('list', [])) if isinstance(status.get('agents'), dict) else 0,
            'cronJobs': cron_jobs,
            'channelSummary': status.get('channelSummary', [])
        },
        'websites': {
            'urls': websites,
            'httpStatus': site_health
        }
    }

    os.makedirs(BASE + '/data', exist_ok=True)
    with open(BASE + '/data/current.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    hp = BASE + '/data/history.json'
    hist = []
    if os.path.exists(hp):
        try:
            with open(hp, 'r', encoding='utf-8') as f:
                hist = json.load(f)
        except Exception:
            hist = []

    hist.append({
        'generatedAt': now,
        'model': data['identity']['model'],
        'w5': w5,
        'day': day,
        'gatewayOk': gateway_probe_ok,
        'memUsedPct': data['system']['memory'].get('usedPct'),
        'diskUsedPct': data['system']['diskRoot'].get('usedPct')
    })
    hist = hist[-1000:]
    with open(hp, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
