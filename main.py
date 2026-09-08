import json
import os
import httpx
from fastapi import FastAPI, Query, Response
import gradio as gr

# ── Config ──────────────────────────────────────────────────────────────
app = FastAPI(title="ICMR + HITEK Search API")

# Hugging Face Datasets Server API (Proxy)
HF_API = "https://datasets-server.huggingface.co/rows"
DATASET = "Kzr0xx/icrm-hitek-full-db-mixed"

# Search fields
SEARCH_FIELDS = [
    "name", "fathersName", "phoneNumber", "aadharNumber", "otherNumber",
    "address", "district", "pincode", "state", "town", "source",
]

def search_hf(q: str, limit: int = 10):
    """Search in all fields using HF API"""
    q = q.strip().lower()
    if not q:
        return {"query": q, "count": 0, "results": []}
    
    try:
        results = []
        offset = 0
        
        # Scan up to 1000 rows (adjustable)
        while len(results) < limit and offset < 1000:
            resp = httpx.get(
                HF_API,
                params={
                    "dataset": DATASET,
                    "config": "default",
                    "split": "train",
                    "offset": offset,
                    "length": 100
                },
                timeout=30
            )
            if resp.status_code != 200:
                break
                
            data = resp.json()
            rows = data.get("rows", [])
            if not rows:
                break
                
            # Filter rows where q matches any field
            for row in rows:
                row_data = row.get("row", {})
                search_str = json.dumps(row_data).lower()
                if q in search_str:
                    results.append(row_data)
                    if len(results) >= limit:
                        break
            
            offset += 100
            if data.get("partial", False):
                break
                
        return {"query": q, "count": len(results), "results": results[:limit]}
    except Exception as e:
        return {"query": q, "count": 0, "results": [], "error": str(e)}

# ── FastAPI Endpoints ──────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "records": 2_504_793_870,
        "columns": SEARCH_FIELDS,
        "docs": "/docs",
        "developer": "@SOCIALBANNERR | channel @modxpatel",
        "status": "active",
    

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/search")
async def search(
    q: str = Query(..., description="Phone, Aadhaar, name..."),
    limit: int = Query(10, ge=1, le=100)
):
    data = search_hf(q, limit)
    return Response(
        content=json.dumps(data, indent=2, default=str),
        media_type="application/json"
    )

@app.get("/search/fields")
async def search_field(
    field: str = Query(..., description="Field name"),
    q: str = Query(..., description="Search value"),
    limit: int = Query(10, ge=1, le=100)
):
    if field not in SEARCH_FIELDS:
        return {"error": f"Invalid field. Choose from: {SEARCH_FIELDS}"}
    
    data = search_hf(q, limit)
    # Filter results by field
    if data.get("results"):
        filtered_results = []
        for row in data["results"]:
            if field in row and q.lower() in str(row[field]).lower():
                filtered_results.append(row)
        data["results"] = filtered_results[:limit]
        data["count"] = len(filtered_results)
    return Response(
        content=json.dumps(data, indent=2, default=str),
        media_type="application/json"
    )

# ── Gradio UI ──────────────────────────────────────────────────────────
def search_ui(query, limit):
    if not query:
        return "⚠️ Kuch search karo — phone, aadhar, ya name daalo."
    
    data = search_hf(query, int(limit))
    if "error" in data:
        return f"❌ Error: {data['error']}"
    if not data.get("results"):
        return f"🔍 **Query:** `{query}`\n\n❌ **No data found**"
    
    out = f"🔍 **Query:** `{query}`  |  **Found:** {data['count']} results\n\n---\n\n"
    for i, row in enumerate(data["results"], 1):
        out += f"### Result {i}\n"
        for key in SEARCH_FIELDS:
            val = row.get(key, "")
            if val:
                out += f"**{key}:** {val}\n"
        out += "\n"
    return out

demo = gr.Interface(
    fn=search_ui,
    inputs=[
        gr.Textbox(label="🔍 Search", placeholder="Phone, Aadhaar, name..."),
        gr.Slider(1, 50, value=10, step=1, label="Max Results")
    ],
    outputs=gr.Markdown(),
    title="📡 ICMR + HITEK Search API",
    description="Search **2.5 billion records** | Built by @SOCIALBANNERR"
)

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
