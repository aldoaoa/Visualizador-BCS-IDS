import os
import json
import uvicorn
from supabase import create_client, Client

# Importaciones Nativas de MCP
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport

# Importaciones del motor Web (Starlette) para el control de CORS
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import PlainTextResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# ==========================================
# 1. CONEXIÓN A BASE DE DATOS
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# 2. INICIALIZACIÓN DEL SERVIDOR MCP
# ==========================================
server = Server("Sistema_Gestion_ESD_Cloud")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Le dice a Gemini qué herramientas existen en el servidor."""
    return [
        types.Tool(
            name="consultar_estatus_alertas",
            description="Obtiene los registros consolidados que están próximos a vencer o vencidos.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="rastrear_activo_esd",
            description="Busca un ID de equipo en todas las tablas posibles de ESD (Inventario, Maquinaria, Historial).",
            inputSchema={
                "type": "object",
                "properties": {
                    "id_busqueda": {"type": "string", "description": "ID exacto del equipo (ej. SMT-01)"}
                },
                "required": ["id_busqueda"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Ejecuta la lógica de la herramienta solicitada por Gemini."""
    if name == "consultar_estatus_alertas":
        try:
            response = supabase.table('v_equipos_por_vencer').select('*').execute()
            data = "No hay equipos vencidos." if not response.data else json.dumps(response.data, indent=2)
            return [types.TextContent(type="text", text=data)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error BD: {e}")]
            
    elif name == "rastrear_activo_esd":
        id_busqueda = arguments.get("id_busqueda")
        resultados = {}
        try:
            inv = supabase.table('inventario_esd').select('*').eq('id_elemento', id_busqueda).execute()
            if inv.data: resultados['inventario'] = inv.data
            
            maq = supabase.table('mediciones_maquinaria').select('*').eq('id_maquinaria', id_busqueda).execute()
            if maq.data: resultados['maquinaria'] = maq.data
            
            val = supabase.table('validacion_esd').select('*').eq('id_elemento', id_busqueda).execute()
            if val.data: resultados['historial_validaciones'] = val.data
            
            data = f"No se encontró el ID {id_busqueda}" if not resultados else json.dumps(resultados, indent=2)
            return [types.TextContent(type="text", text=data)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error BD: {e}")]
            
    raise ValueError(f"Herramienta no reconocida: {name}")

# ==========================================
# 3. PUENTE WEB (CORS, RUTAS Y SSE)
# ==========================================
sse = SseServerTransport("/messages")

async def endpoint_sse(request):
    """Maneja la conexión en tiempo real con la IA."""
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

async def endpoint_messages(request):
    """Recibe los mensajes (preguntas) de la IA."""
    await sse.handle_post_message(request.scope, request.receive, request._send)

async def endpoint_health(request):
    """(CRÍTICO) Le demuestra a Gemini que el servidor está vivo y sano."""
    return PlainTextResponse("Servidor MCP de BCS-AIS funcionando perfectamente.")

# Construimos la App integrando todo y abriendo los permisos CORS al 100%
app = Starlette(
    routes=[
        Route("/", endpoint=endpoint_health, methods=["GET"]),
        Route("/sse", endpoint=endpoint_sse, methods=["GET"]),
        Route("/messages", endpoint=endpoint_messages, methods=["POST"])
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
