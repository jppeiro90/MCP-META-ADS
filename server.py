import os
from pathlib import Path
from mcp_common import READ, WRITE, Proposals, make_mcp, numeric_id, run
from meta_ads_api import CONFIG, MetaAds, account_id, prepare_payload

api = MetaAds()
plans = Proposals(Path(os.getenv("MCP_PROPOSALS_DIR", str(CONFIG.parent/"proposals"))))
mcp = make_mcp("Meta Ads")

def limit(value):
    if not 1 <= value <= 100: raise ValueError("limit debe estar entre 1 y 100.")
    return value

@mcp.tool(annotations=READ)
def meta_ads_connection_status() -> dict:
    """Estado local y nombres de perfiles configurados, sin revelar tokens."""
    return {"service": "mcp-meta-ads", **api.status()}

@mcp.tool(annotations=READ)
def meta_ads_get_permissions(profile: str = "principal") -> dict:
    """Comprueba permisos concedidos. ads_read para informes, ads_management para anuncios; business_management para portfolios."""
    return api.request("me/permissions", profile=profile)

@mcp.tool(annotations=READ)
def meta_ads_list_accounts(profile: str = "principal", after: str = "", page_size: int = 100, include_business: bool = False) -> dict:
    """Lista cuentas accesibles. include_business requiere business_management. Para paginar usar paging.cursors.after mientras paging.has_next."""
    fields = "id,account_id,name,account_status,currency,timezone_name"
    if include_business:
        fields += ",business"
    return api.request("me/adaccounts", profile=profile, params={"fields": fields, "limit": limit(page_size), "after": after})

@mcp.tool(annotations=READ)
def meta_ads_list_businesses(profile: str = "principal", after: str = "") -> dict:
    """Lista portfolios del usuario; requiere business_management. Un token de sistema solo ve activos asignados."""
    return api.request("me/businesses", profile=profile, params={"fields": "id,name,verification_status", "limit": 100, "after": after})

@mcp.tool(annotations=READ)
def meta_ads_list_business_accounts(business_id: str, relationship: str = "owned", profile: str = "principal", after: str = "") -> dict:
    """Cuentas propias o de clientes de un portfolio. relationship=owned o client."""
    if relationship not in {"owned", "client"}: raise ValueError("relationship debe ser owned o client.")
    return api.request(numeric_id(business_id)+"/"+relationship+"_ad_accounts", profile=profile,
        params={"fields": "id,account_id,name,account_status,currency", "limit": 100, "after": after})

@mcp.tool(annotations=READ)
def meta_ads_list_resources(account: str, resource_type: str = "campaigns", profile: str = "principal", after: str = "", page_size: int = 50) -> dict:
    """Consulta campaigns, adsets, ads, adcreatives, adspixels o customaudiences de una cuenta."""
    fields = {"campaigns": "id,account_id,name,status,effective_status,objective,daily_budget,lifetime_budget",
        "adsets": "id,account_id,name,campaign_id,status,effective_status,daily_budget,lifetime_budget,targeting,optimization_goal,billing_event,start_time,end_time,promoted_object",
        "ads": "id,account_id,name,campaign_id,adset_id,status,effective_status,creative",
        "adcreatives": "id,account_id,name,object_story_spec,object_story_id,thumbnail_url",
        "adspixels": "id,name", "customaudiences": "id,name,subtype,approximate_count_lower_bound,approximate_count_upper_bound"}
    if resource_type not in fields: raise ValueError("Tipo de recurso de lectura no admitido.")
    return api.request(account_id(account)+"/"+resource_type, profile=profile,
        params={"fields": fields[resource_type], "limit": limit(page_size), "after": after})

@mcp.tool(annotations=READ)
def meta_ads_get_resource(resource_id: str, fields: list[str], profile: str = "principal") -> dict:
    """Lee un recurso por ID. Campos de Graph, sin modificar nada."""
    import re
    if not fields or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", x) for x in fields): raise ValueError("Usar nombres de campos simples.")
    return api.request(numeric_id(resource_id), profile=profile, params={"fields": ",".join(fields)})

@mcp.tool(annotations=READ)
def meta_ads_get_insights(account: str, since: str, until: str, level: str = "campaign", profile: str = "principal", after: str = "") -> dict:
    """Gasto, clics, impresiones y conversiones por cuenta/campaña/conjunto/anuncio. Fechas YYYY-MM-DD."""
    import json
    from datetime import date
    start,end = date.fromisoformat(since),date.fromisoformat(until)
    if start > end or level not in {"account","campaign","adset","ad"}: raise ValueError("Fechas o nivel inválidos.")
    return api.request(account_id(account)+"/insights", profile=profile,
        params={"fields": "account_id,account_name,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,spend,impressions,reach,clicks,cpc,cpm,ctr,actions,cost_per_action_type", "time_range": json.dumps({"since": since, "until": until}), "level": level, "limit": 100, "after": after})

@mcp.tool(annotations=READ)
def meta_ads_list_pages(profile: str = "principal", after: str = "") -> dict:
    """Páginas de Facebook autorizadas para creatividades. Puede requerir pages_show_list; nunca devuelve tokens de página."""
    return api.request("me/accounts", profile=profile, params={"fields": "id,name,instagram_business_account", "limit": 100, "after": after})

@mcp.tool(annotations=READ)
def meta_ads_prepare_change(account: str, resource_type: str, fields: dict, resource_id: str = "", profile: str = "principal") -> dict:
    """Prepara creación/edición de campaign, adset, creative o ad. Solo valida localmente: Meta validará al aplicar.

    Nuevas campañas, conjuntos y anuncios se crean PAUSED si no se indica otro estado.
    Presupuestos en unidades mínimas de la moneda, comprobando currency de la cuenta.
    Los fields siguen la Marketing API oficial. No se permiten cambios de acceso/facturación.
    """
    payload = prepare_payload(account, resource_type, fields, resource_id, profile)
    # Confirma que la cuenta existe y que un recurso a editar pertenece a esa cuenta.
    api.request(payload["account_id"], profile=profile, params={"fields": "id,account_id,name,currency,account_status"})
    if resource_id:
        existing = api.request(numeric_id(resource_id), profile=profile, params={"fields": "id,account_id"})
        if account_id(existing.get("account_id", "")) != payload["account_id"]: raise ValueError("El recurso pertenece a otra cuenta.")
    spend_change = payload["fields"].get("status") == "ACTIVE" or bool(resource_id and set(fields) & {"daily_budget", "lifetime_budget", "bid_amount", "bid_strategy"})
    return plans.prepare(payload, activation=spend_change, validation="local; Meta valida al aplicar")

@mcp.tool(annotations=WRITE)
def meta_ads_apply_proposal(proposal_id: str, confirm: bool = False, allow_activation: bool = False) -> dict:
    """Aplica una sola vez la propuesta revisada. Activar publicidad exige autorización de gasto y allow_activation=true."""
    plan = plans.load(proposal_id, confirm, allow_activation)
    payload = plan["payload"]
    # Revalidar pertenencia justo antes de escribir.
    if payload["resource_id"]:
        current = api.request(payload["path"], profile=payload["profile"], params={"fields": "account_id"})
        if account_id(current.get("account_id", "")) != payload["account_id"]: raise ValueError("Cuenta del recurso incompatible.")
    plans.claim(proposal_id, confirm, allow_activation)
    return api.request(payload["path"], profile=payload["profile"], method="POST", body=payload["fields"])

if __name__ == "__main__": run(mcp, "mcp-meta-ads")
