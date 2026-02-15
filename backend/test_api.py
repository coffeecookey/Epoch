import requests, json

# Quick full analysis test
print("=== FULL ANALYSIS ===")
r2 = requests.post(
    "http://localhost:8000/analyze-full",
    json={"recipe_name": "Butter Chicken"},
    timeout=180,
)
d = r2.json()
print(f"Status: {r2.status_code}")
print(f"Ingredients ({len(d.get('ingredients', []))}): {d.get('ingredients', [])}")
print(f"Risky ({len(d.get('risky_ingredients', []))}): {[(ri['name'], ri['reason'][:60]) for ri in d.get('risky_ingredients', [])]}")
print(f"Swaps ({len(d.get('swap_suggestions', []))})")
for s in d.get("swap_suggestions", []):
    sub = s.get("substitute", {})
    print(f"  {s['original']} -> {sub.get('name')} (flavor:{sub.get('flavor_match',0):.0f}%)")
    for a in s.get("alternatives", [])[:3]:
        print(f"    alt: {a['name']} mols={a.get('shared_molecules',[])}")
print(f"Original: {d.get('original_health_score',{}).get('score')}")
print(f"Improved: {d.get('improved_health_score',{}).get('score') if d.get('improved_health_score') else 'N/A'}")
print(f"Improvement: {d.get('score_improvement')}")
print(f"Explanation: {(d.get('explanation') or '')[:150]}")
