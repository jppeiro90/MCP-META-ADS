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

## Configurar Meta Ads y Marketing API

1. En [Meta Business Suite](https://business.facebook.com/), verificá que el usuario que generará el token tenga acceso a la cuenta publicitaria. Para crear o editar campañas, también necesita permiso para administrarla. Anotá el ID de la cuenta.
2. En [Meta for Developers](https://developers.facebook.com/apps/), abrí **Mis apps → Crear app**. Elegí **Crear y administrar anuncios con la API de marketing** y seleccioná el portfolio comercial que corresponda. Revisá el resumen y creá una app dedicada a esta integración. [Caso de uso Marketing API](https://developers.facebook.com/docs/development/create-an-app/marketing-api-use-cases/).
3. En el panel de la app, abrí **Casos de uso → Personalizar → Herramientas → Obtener token de acceso**. Seleccioná `ads_read` para consultas e informes. Si vas a crear o editar campañas, seleccioná también `ads_management`. Agregá `business_management` solo si vas a listar portfolios o sus activos y `pages_show_list` si necesitás consultar páginas para elegir la identidad de un anuncio.
4. Pulsá **Obtener token** y copiá el valor. Revisá el aviso del generador antes de usarlo: puede revocar permisos previamente concedidos a esa app. Los tokens de usuario pueden caducar. Para cuentas de terceros o usuarios que no tienen un rol en la app, revisá los requisitos de acceso y revisión de Meta. [Autorización de Marketing API](https://developers.facebook.com/docs/marketing-api/overview/authorization/).

Desde la raíz del repositorio, ejecutá:

```powershell
$env:META_ADS_CONFIG_FILE = Join-Path $PWD 'private/config.json'
.\.venv\Scripts\python.exe auth.py --profile principal
```

Pegá el token cuando lo pida la terminal. El script lo guarda en el perfil sin mostrarlo. Para usar credenciales diferentes, repetí el comando con otro nombre de perfil. Conservá el archivo fuera de Git.

Una vez registrado el servidor en el agente, ejecutá `meta_ads_get_permissions` para comprobar los permisos y `meta_ads_list_accounts` para identificar la cuenta. Consultá sus campañas con `meta_ads_list_resources` usando `resource_type="campaigns"`. Para incluir el portfolio en el listado de cuentas, usá `include_business=true` con un perfil que tenga `business_management`. Si la cuenta esperada no aparece, comprobá la asignación de activos al usuario y el perfil seleccionado.

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
