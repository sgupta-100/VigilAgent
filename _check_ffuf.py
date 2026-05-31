import json,sys
d = json.load(open("/tmp/_x_ffuf.json"))
print("records=", len(d.get("results", [])))
print("sample:", d.get("results", [])[:2])
