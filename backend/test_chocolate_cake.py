import requests, json

# Test with Chocolate Cake (should have different swaps than Butter Chicken)
print("=== CHOCOLATE CAKE TEST ===")
r = requests.post(
    "http://localhost:8000/analyze-full",
    json={"recipe_name": "Chocolate Cake"},
    timeout=180,
)
d = r.json()
print(f"Status: {r.status_code}")
print(f"Ingredients ({len(d.get('ingredients', []))}): {d.get('ingredients', [])[:10]}")
print(f"Risky ({len(d.get('risky_ingredients', []))}): {[(ri['name'][:35], ri['category']) for ri in d.get('risky_ingredients', [])]}")
print(f"Swaps ({len(d.get('swap_suggestions', []))})")
for s in d.get("swap_suggestions", []):
    sub = s.get("substitute", {})
    alts = s.get("alternatives", [])
    print(f"  {s['original'][:40]} -> {sub.get('name')} (flavor:{sub.get('flavor_match',0):.0f}%)")
    print(f"    ({len(alts)} alternatives: {', '.join([a['name'] for a in alts[:4]])})")
print(f"\nOriginal: {d.get('original_health_score',{}).get('score')}")
print(f"Improved: {d.get('improved_health_score',{}).get('score') if d.get('improved_health_score') else 'N/A'}")
print(f"Improvement: +{d.get('score_improvement')} points")
