#!/usr/bin/env python3
import requests, xml.etree.ElementTree as ET, json, re
from urllib.parse import urlparse
OUT='/root/.openclaw/workspace/openclaw-observatory/data/clawd_index.json'
url='https://clawd.org.cn/sitemap.xml'
xml=requests.get(url,timeout=20).text
root=ET.fromstring(xml)
ns={'sm':'http://www.sitemaps.org/schemas/sitemap/0.9'}
items=[]
for u in root.findall('sm:url',ns):
    loc=(u.find('sm:loc',ns).text or '').strip()
    if not loc: continue
    p=urlparse(loc).path.strip('/')
    seg=p.split('/') if p else ['home']
    category=seg[0]
    title=seg[-1].replace('.html','') if seg[-1] else 'home'
    title=title.replace('-', ' ')
    items.append({'url':loc,'category':category,'title':title})
# dedupe
seen=set(); out=[]
for it in items:
    if it['url'] in seen: continue
    seen.add(it['url']); out.append(it)
summary={}
for it in out:
    summary[it['category']]=summary.get(it['category'],0)+1
payload={'source':'clawd.org.cn/sitemap.xml','total':len(out),'categories':summary,'items':out[:400]}
open(OUT,'w',encoding='utf-8').write(json.dumps(payload,ensure_ascii=False,indent=2))
print('written',OUT,'total',len(out))
