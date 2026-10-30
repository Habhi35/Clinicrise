import json

with open('ClinicRise_Complete_End_To_End_API_Flow.postman_collection.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print("Collection Name:", d['info']['name'])
print("Total Variables:", len(d['variable']))
print("Total Folders (Phases):", len(d['item']))
total_requests = 0
for folder in d['item']:
    items = folder['item']
    total_requests += len(items)
    print(f"  • {folder['name']}: {len(items)} requests")
print(f"Total Requests: {total_requests}")
