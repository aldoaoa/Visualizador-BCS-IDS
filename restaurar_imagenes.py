import pandas as pd
import base64
import time
from supabase import create_client, Client
import streamlit as st
# --- 1. PON TUS CREDENCIALES AQUÍ ---
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(url, key)

def restaurar_desde_csv():
    nombre_archivo_csv = "backup.csv" # Cambia esto si tu archivo se llama distinto
    print(f"🚀 Leyendo archivo {nombre_archivo_csv}...")
    
    try:
        # Leemos el CSV de respaldo
        df = pd.read_csv(nombre_archivo_csv)
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo '{nombre_archivo_csv}'.")
        return

    # Validar que existan las columnas necesarias
    if 'ID Elemento' not in df.columns or 'Imagen (Base64)' not in df.columns:
        print("❌ El CSV no tiene las columnas 'ID Elemento' o 'Imagen (Base64)'. Verifica los nombres.")
        return

    migrados = 0
    errores = 0

    for index, row in df.iterrows():
        id_elemento = str(row.get('ID Elemento', '')).strip().upper()
        img_data = str(row.get('Imagen (Base64)', '')).strip()

        # Solo procesamos si hay un ID válido y el texto parece un Base64 largo
        if id_elemento and id_elemento != 'NAN' and len(img_data) > 100:
            print(f"Procesando imagen para el elemento: {id_elemento}...")
            
            try:
                # 1. Limpiar el string por si tiene prefijos de HTML
                if "base64," in img_data:
                    img_data = img_data.split("base64,")[1]
                
                # Corregir el 'padding' de Base64 por si el CSV recortó caracteres al final
                img_data += "=" * ((4 - len(img_data) % 4) % 4)
                
                # 2. Decodificar el texto a bytes de imagen
                img_bytes = base64.b64decode(img_data)
                
                # 3. Generar nombre único de archivo
                timestamp = int(time.time())
                file_name = f"historico_{id_elemento}_{timestamp}.jpg"
                
                # 4. Subir al bucket de Supabase
                supabase.storage.from_("evidencias_esd").upload(
                    file=img_bytes,
                    path=file_name,
                    file_options={"content-type": "image/jpeg"}
                )
                
                # 5. Obtener la URL pública real
                url_publica = supabase.storage.from_("evidencias_esd").get_public_url(file_name)
                
                # 6. Actualizar la fila en SQL cruzando por el ID del elemento
                # Nota: Si hay varios registros históricos para el mismo ID, actualizará el link en todos.
                supabase.table("validacion_esd").update({"imagen_url": url_publica}).eq("id_elemento", id_elemento).execute()
                
                print(f"  -> ✅ Éxito. Enlace guardado en BD: {url_publica}")
                migrados += 1
                
                # Pausa para no saturar la API
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  -> ❌ Error procesando {id_elemento}: {e}")
                errores += 1
        else:
            # Saltamos los vacíos o los que dicen "N/D"
            pass

    print(f"\n🎉 Restauración completada: {migrados} imágenes subidas y vinculadas. {errores} errores.")

if __name__ == "__main__":
    restaurar_desde_csv()
