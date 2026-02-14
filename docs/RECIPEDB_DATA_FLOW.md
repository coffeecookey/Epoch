# RecipeDB API – Data Flow (Simple Explanation)

## How the data flows (in simple words)

1. **Your app** (NutriTwin backend) needs recipe data (name, ingredients, nutrition).
2. It talks to **RecipeDB** – an external API hosted at CosyLab (cosylab.iiitd.edu.in) that has thousands of recipes.
3. **RecipeDBService** (`recipedb_service.py`) is the single place that does all RecipeDB calls:
   - Builds the URL (base URL + endpoint name).
   - Adds your API key (in headers).
   - Sends a GET request, parses JSON, returns data or `None` on failure.
4. **main.py** uses this service whenever it needs a recipe:
   - **Analyze recipe**: `fetch_recipe_by_name(recipe_name)` → then `fetch_nutrition_info(recipe_id)` and `fetch_micro_nutrition_info(recipe_id)`.
   - **Full analysis**: Same lookup by name, then nutrition.
   - **Recommendations**: `get_recipe_by_id`, `search_by_calories`, `search_by_cuisine`, etc.
   - **Quick meals**: `search_by_method`, `search_by_category`, `search_by_diet`, `search_by_cuisine`.
5. So the flow is: **HTTP request (with API key) → RecipeDB server → JSON response → parsed and returned to your endpoints**.

---

## Two API modes

The service supports two ways of talking to RecipeDB:

| Setting | Auth | Main endpoint | Used when |
|--------|------|----------------|-----------|
| **RECIPEDB_USE_BEARER_AUTH=false** (default) | Header `x-api-key` | `recipe_by_title`, `recipe_nutrition_info`, `recipe_by_id`, etc. | “Public” RecipeDB API style |
| **RECIPEDB_USE_BEARER_AUTH=true** | Header `Authorization: Bearer <key>` | `recipesinfo` (paginated list), then filter in code | “Org” API style |

So data can flow either via many small endpoints (by title, by id, nutrition, etc.) or via one `recipesinfo` endpoint that returns a list, which the service then filters (by title, id, etc.).

---

## Where RecipeDB can fail (trace map)

| Step | Where it happens | What can go wrong |
|------|------------------|-------------------|
| 1. Config | `config.py` | `RECIPEDB_BASE_URL` wrong, or `COSYLAB_API_KEY` missing / wrong. |
| 2. Build URL | `recipedb_service._make_request()` | URL = `{base_url}/{endpoint}`. If the real API uses a different path (e.g. no `search_recipedb` or different endpoint names), every request fails. |
| 3. Auth | `_make_request()` headers | No key → 401/403. Wrong key or wrong header (`x-api-key` vs `Bearer`) → same. |
| 4. HTTP request | `requests.get(...)` | **ConnectionError** (server down, DNS, firewall), **Timeout**, or **HTTPError** (4xx/5xx). |
| 5. Response handling | After `raise_for_status()` | 4xx (e.g. 401, 403, 404) → no retry, returns `None`. 5xx → retried up to `max_retries`. |
| 6. JSON parse | `response.json()` | Non-JSON or invalid JSON → **ValueError**, returns `None`. |
| 7. Shape of data | e.g. `_recipesinfo_request()`, `fetch_recipe_by_name()` | If API returns a different structure (e.g. no `payload.data` for org API, or list vs object for public API), code may get `None` or wrong data. |
| 8. Availability check | `check_availability()` in main → `recipedb_service.check_availability()` | Uses `recipe_by_id` with `id=1` (non-bearer) or `recipesinfo` (bearer). If that call fails, health check says RecipeDB is “not responding”. |

So “API not working” can be: wrong URL, wrong or missing API key, wrong auth type, server/network issue, or response format not matching what the code expects.

---

## How to find the exact failure

1. **Logs**  
   Look at backend logs when you call an endpoint that uses RecipeDB. You should see:
   - “Making API request to &lt;url&gt; with params: …”
   - “API Response Status: &lt;code&gt;”
   - On error: “HTTP error …”, “Connection error …”, “Client error (4xx) - likely API key issue …”, etc.

2. **Debug endpoint**  
   Call **GET /debug/cosylab-test**. It returns the exact URL, headers (key redacted), params, and the raw response (status, body preview). Compare with a working request (e.g. Postman).

3. **Health check**  
   **GET /health** includes `recipedb_available: true/false`. If false, RecipeDB is failing at the availability check (step 8 above).

4. **.env**  
   Ensure `COSYLAB_API_KEY` is set. If you use the org API, set `RECIPEDB_USE_BEARER_AUTH=true`.

Once you see the exact status code and response body (from logs or `/debug/cosylab-test`), you can match it to the step in the table above (e.g. 401 → auth; 404 → URL or endpoint; 5xx → server).
