"""Guardar un token de Meta en un perfil local, sin enviarlo por chat."""
import argparse
import getpass
import json
import re
from meta_ads_api import CONFIG, MetaAds
from mcp_common import save_json

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="principal")
    parser.add_argument("--token-file", help="Archivo privado que contiene el token; si se omite, pedirlo sin eco.")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.profile): parser.error("Nombre de perfil inválido.")
    from pathlib import Path
    token = Path(args.token_file).read_text(encoding="utf-8-sig").strip() if args.token_file else getpass.getpass("Token de Meta Ads (no se muestra): ").strip()
    if not token or any(c.isspace() for c in token): raise ValueError("Token vacío o con espacios.")
    data = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {"profiles": {}}
    data.setdefault("profiles", {})[args.profile] = {"access_token": token, "note": args.note}
    save_json(CONFIG, data)
    print("Token guardado en perfil privado. Comprobar permisos y cuentas con las herramientas del MCP.")

if __name__ == "__main__": main()
