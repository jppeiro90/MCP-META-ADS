"""Cliente Meta Marketing API. Cada perfil puede tener un token y activos distintos."""
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import requests
from mcp_common import numeric_id

CONFIG = Path(os.getenv("META_ADS_CONFIG_FILE", str(Path.home()/".config/mcp-meta-ads/config.json")))
VERSION = os.getenv("META_ADS_API_VERSION", "v25.0")
if not re.fullmatch(r"v[0-9]+\.[0-9]+", VERSION): raise ValueError("Versión de Graph inválida.")

def clean_result(value):
    # Graph suele incluir access_token en paging.next: devolver cursores, nunca ese URL.
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {"access_token", "appsecret_proof", "app_secret"}: continue
            if key == "paging":
                result[key] = {"cursors": item.get("cursors", {}), "has_next": bool(item.get("next"))}
            else: result[key] = clean_result(item)
        return result
    return [clean_result(x) for x in value] if isinstance(value, list) else value

def account_id(value):
    return "act_"+numeric_id(str(value).removeprefix("act_"))

class MetaAds:
    def __init__(self, path=CONFIG): self.path = Path(path)
    def config(self):
        if not self.path.exists(): raise RuntimeError("Meta Ads todavía no tiene un token. Completar auth.py con un token autorizado.")
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError): raise RuntimeError("Configuración local de Meta inválida.") from None
    def status(self):
        if not self.path.exists(): return {"configured": False, "profiles": [], "next_step": "Autorizar Marketing API y guardar el token con auth.py."}
        cfg = self.config()
        return {"configured": any(x.get("access_token") for x in cfg.get("profiles", {}).values()),
                "profiles": [{"name": name, "has_token": bool(data.get("access_token")), "note": data.get("note", "")}
                             for name, data in cfg.get("profiles", {}).items()], "api_version": VERSION,
                "note": "Cada perfil puede acceder solo a los portfolios/cuentas autorizados. Probar permissions y list_accounts."}
    def request(self, path, *, profile="principal", method="GET", params=None, body=None):
        if not re.fullmatch(r"(?:me(?:/(?:adaccounts|businesses|permissions|accounts))?|[0-9]+(?:/(?:owned_ad_accounts|client_ad_accounts|owned_pages|client_pages))?|act_[0-9]+(?:/(?:campaigns|adsets|ads|adcreatives|insights|adimages|adspixels|customaudiences))?)", path):
            raise ValueError("Endpoint no permitido.")
        cfg = self.config().get("profiles", {}).get(profile)
        if not cfg or not cfg.get("access_token"): raise ValueError("Perfil de Meta no configurado.")
        token = cfg["access_token"]
        query = dict(params or {})
        if cfg.get("app_secret"):
            query["appsecret_proof"] = hmac.new(cfg["app_secret"].encode(), token.encode(), hashlib.sha256).hexdigest()
        form = None
        if body is not None:
            if any(k in body for k in ("access_token", "appsecret_proof", "app_secret")):
                raise ValueError("No incluir credenciales en los campos del anuncio.")
            form = {key: json.dumps(value) if isinstance(value, (dict, list)) else value for key,value in body.items()}
        try:
            response = requests.request(method, "https://graph.facebook.com/"+VERSION+"/"+path,
                headers={"Authorization": "Bearer "+token}, params=query, data=form,
                timeout=45, allow_redirects=False)
            data = response.json()
        except (requests.RequestException, ValueError):
            raise RuntimeError("No se pudo contactar con Meta. No reintentar escrituras a ciegas.") from None
        if not response.ok or response.is_redirect or "error" in data:
            error = data.get("error", {})
            raise RuntimeError("Meta HTTP "+str(response.status_code)+"; código "+str(error.get("code"))+"; subcódigo "+str(error.get("error_subcode"))+". Revisar permisos, expiración del token y activos asignados.")
        return clean_result(data)

def prepare_payload(account, resource_type, fields, resource_id="", profile="principal"):
    edges = {"campaign": "campaigns", "adset": "adsets", "creative": "adcreatives", "ad": "ads"}
    if resource_type not in edges: raise ValueError("Usar campaign, adset, creative o ad.")
    if not isinstance(fields, dict) or not fields: raise ValueError("Se requieren campos para crear/actualizar.")
    allowed = {
        "campaign": {"name", "objective", "status", "special_ad_categories", "special_ad_category_country", "daily_budget", "lifetime_budget", "bid_strategy", "is_adset_budget_sharing_enabled", "buying_type"},
        "adset": {"name", "campaign_id", "status", "daily_budget", "lifetime_budget", "billing_event", "optimization_goal", "bid_amount", "bid_strategy", "targeting", "start_time", "end_time", "promoted_object", "attribution_spec", "destination_type", "is_dynamic_creative"},
        "creative": {"name", "object_story_spec", "object_story_id", "asset_feed_spec", "degrees_of_freedom_spec", "url_tags", "instagram_user_id", "instagram_actor_id", "actor_id"},
        "ad": {"name", "adset_id", "creative", "status", "tracking_specs", "conversion_specs"},
    }
    if set(fields) - allowed[resource_type]: raise ValueError("Hay campos no admitidos para "+resource_type+".")
    values = json.loads(json.dumps(fields))
    if values.get("status") not in (None, "ACTIVE", "PAUSED"): raise ValueError("Solo se permite ACTIVE o PAUSED; no borrado ni archivo.")
    for budget in ("daily_budget", "lifetime_budget", "bid_amount"):
        if budget in values:
            amount = str(values[budget])
            if not amount.isdigit() or int(amount) <= 0: raise ValueError("Presupuesto/puja debe ser un entero positivo en unidades mínimas de la moneda.")
    for linked in ("campaign_id", "adset_id"):
        if linked in values: values[linked] = numeric_id(values[linked])
    if not resource_id and resource_type in {"campaign", "adset", "ad"}:
        values.setdefault("status", "PAUSED")
    target = numeric_id(resource_id) if resource_id else account_id(account)+"/"+edges[resource_type]
    return {"account_id": account_id(account), "profile": profile, "resource_type": resource_type,
            "resource_id": str(resource_id), "path": target, "fields": values}
