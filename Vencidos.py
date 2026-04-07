import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import gc
from datetime import datetime
from dateutil.relativedelta import relativedelta
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# Configuración horizontal (Wide) para aprovechar monitores y pantallas
st.set_page_config(page_title="Control de Cumplimiento ESD", layout="wide")

RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2, max_entries=1) 
def cargar_datos_cloud():
    try:
        # Cargamos los datos interpretando la fila 5 (índice 4) como encabezados
        df_piso = conn.read(worksheet="PISO", header=4)
        df_mob = conn.read(worksheet="MOBILIARIO", header=4)
        return df_piso, df_mob
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return None, None

def calcular_proxima_fecha(fecha_actual, frecuencia):
    frecuencia = str(frecuencia).strip().lower()
    if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
    elif 'semestral' in frecuencia or '6 meses' in frecuencia: return fecha_actual + relativedelta(months=6)
    elif 'trimestral' in frecuencia or '3 meses' in frecuencia: return fecha_actual + relativedelta(months=3)
    elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
    else: return fecha_actual + relativedelta(years=1)

# --- INICIO DE LA APLICACIÓN ---
st.title("Sistema ESD S20.20 en Tiempo Real")

df_piso_local, df_mob_local = cargar_datos_cloud()

if df_piso_local is None or df_mob_local is None:
    st.warning("⚠️ Asegúrate de haber compartido el Google Sheet con el correo de tu cuenta de servicio con permisos de Editor.")
    st.stop()

# --- PESTAÑAS ---
tab1, tab2 = st.tabs(["🗺️ Mapa y Reportes", "📱 Escáner Automático"])

# ==========================================
# PESTAÑA 1: MAPA Y REPORTES
# ==========================================
with tab1:
    st.info("☁️ Los datos mostrados están sincronizados en tiempo real con Google Sheets.")
    
    df_piso_mapa = df_piso_local.copy()
    df_piso_mapa['Hoja Origen'] = 'PISO'
    df_mob_mapa = df_mob_local.copy()
    df_mob_mapa['Hoja Origen'] = 'MOBILIARIO'
    
    df_total = pd.concat([df_piso_mapa, df_mob_mapa], ignore_index=True)
    df_total['Estatus de verificación'] = df_total['Estatus de verificación'].astype(str).str.strip().str.upper()
    
    if 'Estatus operativo' in df_total.columns:
        df_total['Estatus operativo'] = df_total['Estatus operativo'].astype(str).str.strip().str.upper()
    else:
        df_total['Estatus operativo'] = 'OPERATIVO'

    # Filtrar equipos vencidos que estén operativos
    vencidos = df_total[(df_total['Estatus de verificación'] == 'VENCIDO') & (df_total['Estatus operativo'] != 'NO OPERATIVO')]
    
    if not vencidos.empty:
        st.error(f"🚨 Se encontraron {len(vencidos)} equipos VENCIDOS en operación.")
        conteo_tipos = vencidos.groupby(['Línea', 'Hoja Origen']).size().unstack(fill_value=0).reset_index()
        if 'PISO' not in conteo_tipos.columns: conteo_tipos['PISO'] = 0
        if 'MOBILIARIO' not in conteo_tipos.columns: conteo_tipos['MOBILIARIO'] = 0
        
        conteo_tipos.rename(columns={'PISO': 'Equipos (Piso)', 'MOBILIARIO': 'Mobiliario'}, inplace=True)
        conteo_tipos['Total Vencidos'] = conteo_tipos['Equipos (Piso)'] + conteo_tipos['Mobiliario']
        conteo_tipos['Etiqueta'] = "P: " + conteo_tipos['Equipos (Piso)'].astype(str) + "<br>M: " + conteo_tipos['Mobiliario'].astype(str)
        
        st.markdown("### Mapa de Ubicaciones")
        if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
            img = Image.open(RUTA_MAPA)
            width, height = img.size
            df_coords = pd.read_csv(RUTA_COORDENADAS)
            mapa_data = pd.merge(conteo_tipos, df_coords, on='Línea', how='inner')
            
            if not mapa_data.empty:
                fig = px.scatter(
                    mapa_data, x="X", y="Y", color="Total Vencidos", text="Etiqueta", hover_name="Línea",
                    hover_data={"X": False, "Y": False, "Etiqueta": False, "Total Vencidos": True, "Equipos (Piso)": True, "Mobiliario": True},
                    color_continuous_scale="Reds"
                )
                fig.update_traces(
                    textposition='middle center', textfont=dict(color='white', size=12, weight='bold'),
                    marker=dict(symbol='square', size=50, opacity=0.9, line=dict(width=2, color='DarkSlateGrey'))
                )
                # Mantener proporción real 1:1 de la imagen
                fig.update_layout(
                    images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")],
                    xaxis=dict(showgrid=False, zeroline=False, range=[0, width], visible=False),
                    yaxis=dict(showgrid=False, zeroline=False, range=[height, 0], visible=False, scaleanchor="x", scaleratio=1),
                    margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No hay coincidencias con el archivo de coordenadas.")
            del img, df_coords, mapa_data, fig
            gc.collect()
        else:
            st.info(f"📌 Falta '{RUTA_MAPA}' o '{RUTA_COORDENADAS}'.")
            
        st.markdown("### Detalles de Equipos")
        columnas_mostrar = ['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación', 'Estatus operativo', 'Hoja Origen']
        st.dataframe(vencidos[[col for col in columnas_mostrar if col in vencidos.columns]], use_container_width=True, hide_index=True)
    else:
        st.success("✅ ¡Felicidades! No hay equipos operativos con estatus 'VENCIDO'.")
    
    del df_piso_mapa, df_mob_mapa, df_total, vencidos
    gc.collect()

# ==========================================
# PESTAÑA 2: ESCÁNER Y ACTUALIZACIÓN EN NUBE
# ==========================================
with tab2:
    # Verificamos si hay un ID escaneado en los parámetros de la URL
    id_escaneado = st.query_params.get("qr_id", "")
    
    if not id_escaneado:
        st.markdown("### 📷 Apunta al Código QR")
        st.write("Concede permiso a la cámara. El escaneo es automático y actualizará la base corporativa.")
        
        # Componente HTML5 nativo para leer QR usando la cámara del celular sin saturar el servidor
        html_code = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd;"></div>
        <script>
        function onScanSuccess(decodedText, decodedResult) {
            html5QrcodeScanner.clear(); // Detiene la cámara
            // Inyecta el ID en la URL de Streamlit y recarga la vista
            const url = new URL(window.parent.location.href);
            url.searchParams.set("qr_id", decodedText);
            window.parent.history.replaceState({}, "", url);
            window.parent.location.reload();
        }
        
        let html5QrcodeScanner = new Html5QrcodeScanner(
          "reader", 
          { fps: 15, qrbox: {width: 250, height: 250}, aspectRatio: 1.0 }, 
          false
        );
        html5QrcodeScanner.render(onScanSuccess);
        </script>
        """
        components.html(html_code, height=450)
        
        st.markdown("O ingresa el ID manualmente:")
        id_manual = st.text_input("Ingresar ID manual:", key="input_manual")
        if id_manual:
            st.query_params["qr_id"] = id_manual
            st.rerun()

    if id_escaneado:
        colA, colB = st.columns([0.8, 0.2])
        with colA:
            st.info(f"🔍 **ID Detectado:** {id_escaneado}")
        with colB:
            if st.button("❌ Cancelar"):
                st.query_params.clear()
                st.rerun()

        # Buscar en qué hoja está el equipo
        encontrado_piso = id_escaneado in df_piso_local['Id de producto'].values
        encontrado_mob = id_escaneado in df_mob_local['Id de producto'].values

        if encontrado_piso or encontrado_mob:
            hoja_activa = "PISO" if encontrado_piso else "MOBILIARIO"
            df_actual = df_piso_local if encontrado_piso else df_mob_local
            
            idx = df_actual[df_actual['Id de producto'] == id_escaneado].index[0]
            equipo = df_actual.iloc[idx]
            
            col1, col2 = st.columns(2)
            col1.metric("Estatus Actual", str(equipo.get('Estatus de verificación', 'N/A')))
            col2.metric("Última Fecha Validada", str(equipo.get('Fecha de verificación', 'N/A'))[:10])
            
            st.divider()

            with st.form("form_actualizacion"):
                nuevo_valor = st.number_input(
                    "Nuevo valor de medición (Ohms)", 
                    value=float(equipo.get('Valor de verificación', 0)) if pd.notna(equipo.get('Valor de verificación')) else 0.0,
                    format="%f"
                )
                
                fecha_hoy = datetime.today().date()
                nueva_fecha = st.date_input("Fecha de medición actual", fecha_hoy)
                
                submit = st.form_submit_button("Guardar en Google Sheets")
                
                if submit:
                    with st.spinner("Actualizando celdas directamente en la nube..."):
                        # 1. Calcular próxima fecha
                        frecuencia = str(equipo.get('Frecuencia de verificación', 'Anual'))
                        proxima_fecha = calcular_proxima_fecha(nueva_fecha, frecuencia)
                        
                        # 2. MÉTODO QUIRÚRGICO (Usando gspread nativo)
                        import gspread
                        
                        # Convertimos los secretos de Streamlit a un diccionario estándar
                        secretos_dict = dict(st.secrets["connections"]["gsheets"])
                        url_hoja = secretos_dict["spreadsheet"]
                        
                        # Nos conectamos a Google Sheets SIN el intermediario de Streamlit
                        gc_gspread = gspread.service_account_from_dict(secretos_dict)
                        doc = gc_gspread.open_by_url(url_hoja)
                        ws = doc.worksheet(hoja_activa)
                        
                        # Obtenemos la posición numérica de las columnas
                        id_col_idx = df_actual.columns.get_loc('Id de producto')
                        val_col_idx = df_actual.columns.get_loc('Valor de verificación')
                        fecha_col_idx = df_actual.columns.get_loc('Fecha de verificación')
                        prox_fecha_col_idx = df_actual.columns.get_loc('Fecha de próxima verificación')
                        status_col_idx = df_actual.columns.get_loc('Estatus de verificación')
                        
                        # Extraemos SÓLO la columna de IDs de Google Sheets (gspread cuenta desde 1)
                        columna_ids = ws.col_values(id_col_idx + 1)
                        
                        # Limpiamos los espacios en blanco invisibles para asegurar que siempre lo encuentre
                        columna_ids_limpia = [str(val).strip() for val in columna_ids]
                        
                        # Buscamos la fila exacta del ID escaneado
                        row_gspread = columna_ids_limpia.index(str(id_escaneado).strip()) + 1
                        
                        # 3. Actualizamos las 4 celdas específicas (fila, columna, valor)
                        ws.update_cell(row_gspread, val_col_idx + 1, float(nuevo_valor))
                        ws.update_cell(row_gspread, fecha_col_idx + 1, nueva_fecha.strftime("%Y-%m-%d"))
                        ws.update_cell(row_gspread, prox_fecha_col_idx + 1, proxima_fecha.strftime("%Y-%m-%d"))
                        ws.update_cell(row_gspread, status_col_idx + 1, 'VIGENTE')

                    st.success("💾 ¡Actualización exitosa! Las celdas se modificaron al instante en Google Sheets.")
                    st.cache_data.clear()
                    
                    # Limpiamos la URL para permitir un nuevo escaneo
                    st.query_params.clear()
                    st.rerun()

        else:
            st.error("❌ El ID escaneado no existe en el sistema.")
