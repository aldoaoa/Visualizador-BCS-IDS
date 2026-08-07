from fastmcp import FastMCP
from supabase import create_client, Client
import os
import json

# Inicializamos el servidor
mcp = FastMCP("Sistema_Gestion_ESD_Cloud")

# Conexión a Supabase (Segura y por variables de entorno)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# HERRAMIENTAS DE SOLO LECTURA (READ-ONLY)
# ==========================================

@mcp.tool()
def consultar_estatus_alertas() -> str:
    """
    Obtiene los registros consolidados que están próximos a vencer o vencidos.
    Respeta la lógica de tu vista unificada 'v_equipos_por_vencer' 
    que alimenta el correo automático.
    """
    try:
        # Solo usamos .select()
        response = supabase.table('v_equipos_por_vencer').select('*').execute()
        if not response.data:
            return "No se encontraron equipos en riesgo de vencimiento."
        return json.dumps(response.data, indent=2)
    except Exception as e:
        return f"Error de lectura en base de datos: {str(e)}"

@mcp.tool()
def rastrear_activo_esd(id_busqueda: str) -> str:
    """
    Busca un ID de equipo en todas las tablas posibles respetando 
    el naming exacto de las columnas de tu sistema.
    """
    resultados = {}
    try:
        # 1. Búsqueda en Inventario General (Usa 'id_elemento')
        inv_resp = supabase.table('inventario_esd').select('*').eq('id_elemento', id_busqueda).execute()
        if inv_resp.data:
            resultados['inventario'] = inv_resp.data

        # 2. Búsqueda en Maquinaria (Usa 'id_maquinaria')
        maq_resp = supabase.table('mediciones_maquinaria').select('*').eq('id_maquinaria', id_busqueda).execute()
        if maq_resp.data:
            resultados['maquinaria'] = maq_resp.data

        # 3. Búsqueda en el Historial de Validaciones (Usa 'id_elemento')
        val_resp = supabase.table('validacion_esd').select('*').eq('id_elemento', id_busqueda).execute()
        if val_resp.data:
            resultados['historial_validaciones'] = val_resp.data
            
        if not resultados:
            return f"No se encontró información para el ID: {id_busqueda} en las tablas registradas."

        return json.dumps(resultados, indent=2)
    except Exception as e:
        return f"Error en la consulta de rastreo: {str(e)}"

if __name__ == "__main__":
    # Configuración para alojamiento en Render / Nube (SSE)
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
