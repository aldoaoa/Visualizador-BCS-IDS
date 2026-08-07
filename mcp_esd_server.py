from mcp.server.fastmcp import FastMCP
from supabase import create_client, Client
import os
import json

# 1. Inicializamos FastMCP
mcp = FastMCP("Sistema_Gestion_ESD_Cloud")

# 2. Conexión a Supabase usando variables de entorno de la nube
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# DEFINICIÓN DE HERRAMIENTAS PARA LA IA
# ==========================================

@mcp.tool()
def consultar_equipos_vencidos() -> str:
    """Obtiene la lista de equipos ESD con medición vencida."""
    try:
        response = supabase.table('v_equipos_por_vencer').select('*').execute()
        if not response.data:
            return "No hay equipos con medición ESD vencida hoy."
        return json.dumps(response.data, indent=2)
    except Exception as e:
        return f"Error de base de datos: {str(e)}"

@mcp.tool()
def buscar_historial_equipo(id_activo: str) -> str:
    """Busca el historial completo de mediciones para un equipo (ej. SMT-01)."""
    try:
        resp_maq = supabase.table('mediciones_maquinaria').select('*').eq('id_activo', id_activo).execute()
        resp_inv = supabase.table('inventario_esd').select('*').eq('id_activo', id_activo).execute()
        
        resultados = {
            "maquinaria": resp_maq.data if resp_maq.data else [],
            "inventario": resp_inv.data if resp_inv.data else []
        }
        return json.dumps(resultados, indent=2)
    except Exception as e:
        return f"Error al buscar: {str(e)}"

if __name__ == "__main__":
    # IMPORTANTE: Configuramos el transporte web (SSE)
    # Render y otros servicios inyectan el puerto en la variable 'PORT'
    port = int(os.environ.get("PORT", 8000))
    
    # Arrancamos el servidor para que escuche peticiones externas
    mcp.run(transport="sse", host="0.0.0.0", port=port)
