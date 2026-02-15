"""Debug: test the ingredient fetch and swap system."""
import requests
import json

# 1. Direct API call to see what comes back
print("=== RAW API TEST ===")
api_url = "https://cosylab.iiitd.edu.in/recipe2-api/recipebyingredient/by-ingredients-categories-title"
r = requests.get(api_url, params={"title": "Butter Chicken"})
print(f"Status: {r.status_code}")
try:
    data = r.json()
    print(f"Type: {type(data).__name__}")
    if isinstance(data, dict):
        # Might be paginated
        print(f"Keys: {list(data.keys())[:10]}")
        content = data.get("content") or data.get("data") or data.get("results")
        if isinstance(content, list):
            data = content
        else:
            print(f"Sample: {json.dumps(data, indent=2)[:500]}")
    if isinstance(data, list):
        print(f"Results: {len(data)}")
        if data:
            print(f"First row keys: {list(data[0].keys())}")
            print(f"First row sample: {json.dumps(data[0], indent=2, default=str)[:800]}")
            for row in data[:3]:
                print(f"  id={row.get('Recipe_id')}, title={row.get('Recipe_title')}, ing={row.get('ingredient')}")
            first_id = str(data[0].get("Recipe_id", ""))
            matching = [row for row in data if str(row.get("Recipe_id","")) == first_id]
            print(f"\nAll ings for id={first_id}: {len(matching)}")
            for row in matching:
                print(f"  {row.get('ingredient')}")
except Exception as e:
    print(f"Parse error: {e}")
    print(f"Response text: {r.text[:300]}")

# 2. Full analysis
print("\n=== FULL ANALYSIS ===")
r2 = requests.post(
    "http://localhost:8000/analyze-full",
    json={"recipe_name": "Butter Chicken"},
    timeout=120,
)
d = r2.json()
print(f"Status: {r2.status_code}")
print(f"Ingredients ({len(d.get('ingredients', []))}): {d.get('ingredients', [])}")
print(f"Risky ({len(d.get('risky_ingredients', []))}): {[(ri['name'], ri['reason'][:50]) for ri in d.get('risky_ingredients', [])]}")
print(f"Swaps ({len(d.get('swap_suggestions', []))})")
for s in d.get("swap_suggestions", []):
    sub = s.get("substitute", {})
    print(f"  {s['original']} -> {sub.get('name')} (flavor:{sub.get('flavor_match',0):.0f}%)")
    for a in s.get("alternatives", [])[:3]:
        print(f"    alt: {a['name']} (mols:{a.get('shared_molecules',[])})")
print(f"Original: {d.get('original_health_score',{}).get('score')}")
print(f"Improved: {d.get('improved_health_score',{}).get('score') if d.get('improved_health_score') else 'N/A'}")
print(f"Improvement: {d.get('score_improvement')}")
