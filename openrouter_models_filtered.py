
#!/usr/bin/env python3
import argparse, csv, json, os, urllib.parse, urllib.request
from typing import Any, Dict, List, Optional, Tuple

API_BASE = "https://openrouter.ai/api/v1"

def http_get(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
        try:
            return json.loads(data.decode("utf-8"))
        except Exception:
            return {"raw": data.decode("utf-8", errors="replace")}

def get_models(raw_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    query = urllib.parse.urlencode({k: v for k, v in raw_params.items() if v is not None})
    url = f"{API_BASE}/models" + (f"?{query}" if query else "")
    headers = {}
    if os.getenv("OPENROUTER_API_KEY"):
        headers["Authorization"] = f"Bearer {os.getenv('OPENROUTER_API_KEY')}"
    data = http_get(url, headers=headers)
    return data.get("data", [])

def get_endpoints_for_model(model_id: str) -> Dict[str, Any]:
    try:
        author, slug = model_id.split("/", 1)
    except ValueError:
        return {"data": []}
    url = f"{API_BASE}/models/{author}/{slug}/endpoints"
    headers = {}
    if os.getenv("OPENROUTER_API_KEY"):
        headers["Authorization"] = f"Bearer {os.getenv('OPENROUTER_API_KEY')}"
    return http_get(url, headers=headers)

def price_per_1k(s: Optional[str]) -> Optional[float]:
    if s is None: return None
    try:
        return float(s) * 1000.0
    except Exception:
        return None

def meets_filters(m: Dict[str, Any], min_context: int, max_price_per_1k: float, require_text: bool, require_response_format: bool) -> bool:
    ctx = (m.get("top_provider") or {}).get("context_length") or m.get("context_length")
    if not isinstance(ctx, (int, float)) or int(ctx) < min_context: return False
    inmods = (m.get("architecture") or {}).get("input_modalities") or m.get("input_modalities") or []
    if require_text and "text" not in inmods: return False
    sp = m.get("supported_parameters") or []
    if require_response_format and not any(p in ("response_format", "structured_outputs") for p in sp): return False
    pr = m.get("pricing") or {}
    in_price = price_per_1k(pr.get("prompt"))
    if in_price is None or in_price > max_price_per_1k: return False
    return True

def flatten_model(m: Dict[str, Any]) -> Dict[str, Any]:
    arch = m.get("architecture") or {}
    tprov = m.get("top_provider") or {}
    pr = m.get("pricing") or {}
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "context_length": tprov.get("context_length", m.get("context_length")),
        "max_completion_tokens": tprov.get("max_completion_tokens"),
        "input_modalities": ",".join(arch.get("input_modalities") or m.get("input_modalities") or []),
        "supported_parameters": ",".join(m.get("supported_parameters") or []),
        "prompt_price_per_1k": price_per_1k(pr.get("prompt")),
        "completion_price_per_1k": price_per_1k(pr.get("completion")),
        "description": (m.get("description") or "").replace("\n", " ")[:200],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-context", type=int, default=32000)
    ap.add_argument("--max-price-per-1k", type=float, default=0.1)
    ap.add_argument("--require-text", action="store_true", default=True)
    ap.add_argument("--require-response-format", action="store_true", default=True)
    ap.add_argument("--verify-providers", action="store_true")
    ap.add_argument("--save-json", type=str)
    ap.add_argument("--save-csv", type=str)
    args = ap.parse_args()

    raw_params = {"supported_parameters": "response_format", "input_modalities": "text", "context": str(args.min_context), "max_price": str(args.max_price_per_1k)}
    models = get_models(raw_params)
    filtered = [m for m in models if meets_filters(m, args.min_context, args.max_price_per_1k, args.require_text, args.require_response_format)]
    flat = [flatten_model(m) for m in filtered]

    if args.verify_providers:
        verified = {}
        for row in flat:
            eps = get_endpoints_for_model(row["id"]).get("data", [])
            v = []
            for ep in eps:
                sp = ep.get("supported_parameters") or []
                v.append({
                    "provider": ep.get("provider"),
                    "supports_response_format": any(p in ("response_format", "structured_outputs") for p in sp),
                    "context_length": ep.get("context_length"),
                    "prompt_price_per_1k": price_per_1k((ep.get("pricing") or {}).get("prompt"))
                })
            row["providers"] = v

    if not flat:
        print("No models matched the filters."); return

    cols = ["id","prompt_price_per_1k","completion_price_per_1k","context_length","input_modalities","supported_parameters","name"]
    widths = {c: max(len(c), max(len(str(r.get(c,""))) for r in flat)) for c in cols}
    def fmt(row): return " | ".join(str(row.get(c,"")).ljust(widths[c]) for c in cols)
    print(fmt({c:c for c in cols}))
    print("-+-".join("-"*widths[c] for c in cols))
    for r in flat:
        print(fmt(r))
        if "providers" in r:
            for ep in r["providers"]:
                print(f"    - {ep['provider']}: response_format={ep['supports_response_format']} ctx={ep['context_length']} in=${ep['prompt_price_per_1k']} per 1k")

    if args.save_json:
        with open(args.save_json, "w", encoding="utf-8") as f:
            json.dump({"filters": vars(args), "data": flat}, f, indent=2)
        print(f"\nSaved JSON to {args.save_json}")
    if args.save_csv:
        import csv
        with open(args.save_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[k for k in flat[0].keys() if k != "providers"])
            w.writeheader(); w.writerows([{k:v for k,v in r.items() if k != "providers"} for r in flat])
        print(f"Saved CSV to {args.save_csv}")

if __name__ == "__main__":
    main()
