import pandas as pd
import base64
import time
from supabase import create_client, Client
import streamlit as st

# --- INTERFAZ BÁSICA ---
st.set_page_config(page_title="Migrador de Imágenes", page_icon="⚙️")
st.title("🛠️ Migrador de Imágenes Históricas a Supabase")
st.info("Este script leerá el archivo backup.csv, extraerá los códigos Base64, los convertirá en imágenes JPG, los subirá al Bucket y actualizará la base de datos SQL.")

# --- CREDENCIALES ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

def restaurar_desde_csv():
    nombre_archivo_csv = "backup.csv" 
    st.write(f"🚀 **Leyendo archivo:** `{nombre_archivo_csv}`...")
    
    try:
        df = pd.read_csv(nombre_archivo_csv)
    except FileNotFoundError:
        st.error(f"❌ No se encontró el archivo '{nombre_archivo_csv}'. Asegúrate de haberlo subido a GitHub en la misma carpeta que este script.")
        return

    # Validar que existan las columnas necesarias
    if 'ID_Elemento' not in df.columns or 'Imagen(Base64)' not in df.columns:
        st.error("❌ El CSV no tiene las columnas 'ID Elemento' o 'Imagen (Base64)'. Verifica los nombres en la primera fila de tu CSV.")
        return

    migrados = 0
    errores = 0

    # Contenedores visuales para no hacer la pantalla infinita
    estado_texto = st.empty()
    log_container = st.container()

    for index, row in df.iterrows():
        id_elemento = str(row.get('ID_Elemento', '')).strip().upper()
        img_data = str(row.get('Imagen(Base64)', '')).strip()

        # Solo procesamos si hay un ID válido y el texto parece un Base64 largo
        if id_elemento and id_elemento != 'NAN' and len(img_data) > 100:
            estado_texto.warning(f"🔄 Procesando imagen para el elemento: **{id_elemento}**...")
            
            try:
                # 1. Limpiar el string
                if "base64," in img_data:
                    img_data = img_data.split("base64,")[1]
                
                # Corregir el 'padding'
                img_data += "=" * ((4 - len(img_data) % 4) % 4)
                
                # 2. Decodificar
                img_bytes = base64.b64decode(img_data)
                
                # 3. Generar nombre
                timestamp = int(time.time())
                file_name = f"historico_{id_elemento}_{timestamp}.jpg"
                
                # 4. Subir a Supabase
                supabase.storage.from_("evidencias_esd").upload(
                    file=img_bytes,
                    path=file_name,
                    file_options={"content-type": "image/jpeg"}
                )
                
                # 5. Obtener URL
                url_publica = supabase.storage.from_("evidencias_esd").get_public_url(file_name)
                
                # 6. Actualizar SQL
                supabase.table("validacion_esd").update({"imagen_url": url_publica}).eq("id_elemento", id_elemento).execute()
                
                log_container.success(f"✅ {id_elemento}: Enlace guardado correctamente.")
                migrados += 1
                
                time.sleep(0.5)
                
            except Exception as e:
                log_container.error(f"❌ Error procesando {id_elemento}: {e}")
                errores += 1

    estado_texto.success("Proceso Finalizado.")
    st.balloons()
    st.success(f"🎉 **Restauración completada:** {migrados} imágenes subidas y vinculadas. {errores} errores.")

st.divider()
if st.button("▶️ INICIAR MIGRACIÓN", type="primary", use_container_width=True):
    restaurar_desde_csv()
