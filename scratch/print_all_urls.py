import json

data = json.load(open('scratch/comprehensive_test_results.json', encoding='utf-8'))
for i, d in enumerate(data, 1):
    print(f"[{i:02d}] P{d['phase']} {d['method']} {d['url']}")
    if d.get('request_body'):
        print(f"     Body: {json.dumps(d['request_body'])[:100]}...")
