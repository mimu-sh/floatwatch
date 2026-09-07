#!/usr/bin/env python3
"""Resolve CoinGecko ids: Robinhood token + a non-Robinhood control per stock."""
import json,time,urllib.request
UA={"User-Agent":"Mozilla/5.0"}
def get(u):
    for a in range(10):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))
        except Exception: time.sleep(12)
    return None
STOCKS=["IBM","HIMS","MU","MSTR","NVDA","TSLA","AAPL","PLTR"]
out={}
for s in STOCKS:
    d=get(f"https://api.coingecko.com/api/v3/search?query={s}")
    if not d: print(s,"-> rate limited"); continue
    rh=ctrl=None
    for c in d.get("coins",[]):
        n=c["name"].lower()
        if c["symbol"].upper()!=s and s.lower() not in n: continue
        if "robinhood" in n and not rh: rh=c["id"]
        elif ("xstock" in n or "ondo" in n or "bstock" in n) and "wrapped" not in n and not ctrl:
            ctrl=c["id"]
    if rh and ctrl:
        out[s]={"rh":rh,"ctrl":ctrl}
        print(f"  {s:6} rh={rh[:46]:48} ctrl={ctrl}")
    else:
        print(f"  {s:6} INCOMPLETE rh={rh} ctrl={ctrl}")
    time.sleep(4)
json.dump(out,open("cg_ids.json","w"),indent=1)
print(f"\nresolved {len(out)}/{len(STOCKS)} stocks with both legs")
