# MCP Meta Ads — conexión local y múltiples portfolios

El servidor puede ejecutarse localmente mediante el transporte MCP stdio.

Permite listar portfolios comerciales y cuentas propias o de clientes; consultar campañas, conjuntos, anuncios, creatividades, páginas, píxeles y rendimiento; y preparar/aplicar cambios de campañas, conjuntos, creatividades y anuncios.

## Alcance de los portfolios

Puede trabajar con todos los portfolios y cuentas autorizados por el token, el usuario y la app. No hay acceso global automático.

Un token de usuario del sistema suele limitarse a los activos que se le asignen. Cuentas de otros negocios/clientes pueden requerir asignación como socio, revisión de la app o permisos adicionales. Se admiten varios perfiles de autenticación para tokens con alcances distintos.

## Instalación

Con Python 3.11, ejecutá estos comandos desde la raíz del repositorio en Windows:

    py -3.11 -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Reemplazá las rutas de ejemplo por las de tu equipo.

## Autorización de Meta

Permisos habituales:

- ads_read: lectura e informes.
- ads_management: gestión publicitaria.
- business_management: portfolios y sus activos, cuando corresponda.
- pages_show_list: enumeración de páginas para elegir la identidad de anuncios.

Guardar un token autorizado sin escribirlo en el chat:

    $env:META_ADS_CONFIG_FILE = 'C:\Proyectos\MCP-META-ADS\private\config.json'
    .\.venv\Scripts\python.exe auth.py --profile principal

El comando pide el token sin eco. También acepta --token-file RUTA_PRIVADA. Usar otro --profile para añadir un token con distinto alcance.

Usá una app de Meta exclusiva para esta integración. El generador rápido de Marketing API puede revocar permisos anteriores de esa app cuando se solicita un token nuevo.

Las apps en desarrollo y los tokens de usuario pueden tener restricciones o caducidad. No afirmar acceso real hasta comprobar meta_ads_get_permissions y meta_ads_list_accounts.

## Configuración de Codex

Agregar a ~/.codex/config.toml sin reemplazar los otros MCP:

    [mcp_servers.meta_ads]
    command = 'C:\Proyectos\MCP-META-ADS\.venv\Scripts\python.exe'
    args = ['C:\Proyectos\MCP-META-ADS\server.py']
    startup_timeout_sec = 30
    tool_timeout_sec = 90

    [mcp_servers.meta_ads.env]
    MCP_TRANSPORT = "stdio"
    META_ADS_CONFIG_FILE = 'C:\Proyectos\MCP-META-ADS\private\config.json'

En Claude Code u OpenCode, configurar un MCP local stdio con ese Python, server.py y las mismas variables. No necesita Tailscale ni un servidor HTTP. Reiniciar el agente si no incorpora las herramientas nuevas.

## Flujo del agente

1. Consultar estado, permisos y cuentas del perfil.
2. Recorrer portfolios, cuentas propias y de clientes. Continuar usando paging.cursors.after mientras paging.has_next sea true.
3. Elegir explícitamente portfolio/perfil, cuenta y página/Instagram de cada campaña.
4. Leer configuración actual, moneda y presupuesto.
5. Preparar con meta_ads_prepare_change.
6. Mostrar toda la propuesta y pedir autorización específica antes de meta_ads_apply_proposal.

La preparación valida localmente la estructura y comprueba pertenencia de cuenta; **Meta valida los campos definitivamente al aplicar**. No confundir esa preparación con un borrador ya creado en Meta.

Las nuevas campaign/adset/ad quedan PAUSED si no se indica status. Activar o editar presupuestos requiere autorización adicional de gasto. Los importes se expresan en unidades mínimas según la moneda que exige Meta.

Las propuestas vencen en 30 minutos y solo se envían una vez. Tras timeout, consultar el estado antes de crear otra. No se modifican métodos de pago, roles o propietarios, no se borran recursos y no se suben listas de datos personales.

Los resultados de paginación eliminan URLs que pueden contener tokens y conservan los cursores.

## Pruebas

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

Prueban aislamiento de cuentas, limpieza de tokens, confirmaciones, propuestas, concurrencia y MCP. No publican anuncios ni generan gasto.

## Referencias

- https://developers.facebook.com/docs/marketing-api/
- https://developers.facebook.com/docs/marketing-api/overview/authorization/
- https://developers.facebook.com/docs/marketing-api/reference/ad-account/
