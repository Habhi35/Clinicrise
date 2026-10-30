import json

data = json.load(open('scratch/comprehensive_test_results.json', encoding='utf-8'))
print(f"Total entries: {len(data)}")
for i, d in enumerate(data, 1):
    rb = d.get('request_body')
    rb_summary = "None" if rb is None else f"{len(rb)} fields"
    print(f"{i:02d}. [Phase {d['phase']}] {d['method']} {d['url']} - {d['step']} (Body: {rb_summary})")
