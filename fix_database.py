import streamlit as st
from supabase import create_client

# 1. Inicializar conexión usando tus secretos de Streamlit
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

def corregir_tabla_maquinaria():
    print("🔄 Iniciando descarga de registros de mediciones_maquinaria...")
    # Traemos el ID primario de la tabla (usualmente es 'id', cámbialo si tu llave primaria se llama distinto)
    # y las dos columnas involucradas
    response = supabase.table("mediciones_maquinaria").select("id, frecuencia_verificacion").execute()
    registros = response.data

    if not registros:
        print("⚠️ No se encontraron registros o la tabla está vacía.")
        return

    print(f"📦 Se encontraron {len(registros)} registros a procesar.")
    
    contador = 0
    for reg in registros:
        id_registro = reg.get("id")
        # El valor que se guardó por error (ej: "PASA" o "FALLA")
        valor_erroneo = reg.get("frecuencia_verificacion") 
        
        # Actualizamos la fila: movemos el valor al destino correcto y seteamos "Anual"
        try:
            supabase.table("mediciones_maquinaria").update({
                "resultado_estatus": valor_erroneo,
                "frecuencia_verificacion": "Anual"
            }).eq("id", id_registro).execute()
            
            contador += 1
        except Exception as e:
            print(f"❌ Error al actualizar el ID {id_registro}: {e}")

    print(f"🎉 ¡Proceso terminado! Se actualizaron con éxito {contador} registros.")

if __name__ == "__main__":
    corregir_tabla_maquinaria()
