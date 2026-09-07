import json,time,urllib.request
UA={"User-Agent":"Mozilla/5.0"}
def get(u):
    for a in range(10):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=30))
        except Exception: time.sleep(12)
    return None
ids=json.load(open("cg_ids.json"))
RH={"MU":"micron-technology-robinhood-tokenized-stock","MSTR":"strategy-inc-robinhood-tokenized-stock",
    "NVDA":"nvidia-robinhood-tokenized-stock","TSLA":"tesla-robinhood-tokenized-stock",
    "AAPL":"apple-robinhood-tokenized-stock","PLTR":"palantir-technologies-robinhood-tokenized-stock"}
NAME={"MU":"Micron","MSTR":"Strategy","NVDA":"NVIDIA","TSLA":"Tesla","AAPL":"Apple","PLTR":"Palantir"}
for s,rh in RH.items():
    if s in ids: continue
    ctrl=None
    for q in (f"{NAME[s]} xStock", f"{NAME[s]} Ondo"):
        d=get(f"https://api.coingecko.com/api/v3/search?query={q.replace(' ','%20')}")
        time.sleep(4)
        if not d: continue
        for c in d.get("coins",[]):
            n=c["name"].lower()
            if "wrapped" in n: continue
            if NAME[s].lower() not in n: continue
            if "xstock" in n or "ondo" in n:
                ctrl=c["id"]; break
        if ctrl: break
    if ctrl:
        ids[s]={"rh":rh,"ctrl":ctrl}
        print(f"  {s:6} ctrl={ctrl}")
    else:
        print(f"  {s:6} no control found")
json.dump(ids,open("cg_ids.json","w"),indent=1)
print(f"\ntotal with both legs: {len(ids)}")
