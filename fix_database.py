import streamlit as st
from supabase import create_client
from datetime import datetime

# Inicializar conexión
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

def recalcular_historico_maquinaria():
    print("🔄 Descargando registros de mediciones_maquinaria...")
    # Asegúrate de pedir la columna 'id' (Primary Key) y los campos de decisión
    response = supabase.table("mediciones_maquinaria").select("id, resistencia_tierra, fecha_proxima").execute()
    registros = response.data

    if not registros:
        print("⚠️ No se encontraron registros.")
        return

    hoy = datetime.today().date()
    contador = 0
    
    print(f"📦 Procesando {len(registros)} filas...")
    
    for reg in registros:
        id_reg = reg.get("id")
        resistencia = reg.get("resistencia_tierra")
        fecha_prox_str = reg.get("fecha_proxima")
        
        # 1. Por defecto, si no hay medición, queda PENDIENTE
        nuevo_estatus = "PENDIENTE"
        
        # 2. Si existe medición en resistencia_tierra, evaluamos fechas
        if resistencia is not None and str(resistencia).strip() != "":
            if fecha_prox_str:
                try:
                    # Extraer solo la parte de la fecha YYYY-MM-DD
                    fecha_prox = datetime.fromisoformat(fecha_prox_str.split("T")[0]).date()
                    if fecha_prox < hoy:
                        nuevo_estatus = "VENCIDO"
                    else:
                        nuevo_estatus = "VIGENTE"
                except Exception as e:
                    print(f"⚠️ Error al parsear fecha en ID {id_reg}: {e}. Se asignará VIGENTE preventivo.")
                    nuevo_estatus = "VIGENTE"
            else:
                nuevo_estatus = "VIGENTE"

        # 3. Actualizar fila en la base de datos
        try:
            supabase.table("mediciones_maquinaria").update({
                "resultado_estatus": nuevo_estatus,
                "frecuencia_verificacion": "Anual" # Aseguramos que quede fijo
            }).eq("id", id_reg).execute()
            contador += 1
        except Exception as e:
            print(f"❌ Error actualizando ID {id_reg}: {e}")

    print(f"🎉 ¡Éxito! Se recalcularon y actualizaron {contador} registros en SQL.")

if __name__ == "__main__":
    recalcular_historico_maquinaria()
