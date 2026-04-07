import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
from datetime import datetime
from dateutil.relativedelta import relativedelta
from streamlit_gsheets import GSheetsConnection # Librería necesaria
import streamlit.components.v1 as components

st.set_page_config(page_title="Control ESD Cloud", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2) # Cache de solo 2 segundos para ver cambios casi instantáneos
def cargar_datos_cloud():
    # Leer ambas hojas. El parámetro 'worksheet' indica el nombre de la pestaña
    df_piso = conn.read(worksheet="PISO", header=4)
    df_mob = conn.read(worksheet="MOBILIARIO", header=4)
    return df_piso, df_mob

def calcular_proxima_fecha(fecha_actual, frecuencia):
    frecuencia = str(frecuencia).strip().lower()
    if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
    elif 'semestral' in frecuencia or '6 meses' in frecuencia: return fecha_actual + relativedelta(months=6)
    else: return fecha_actual + relativedelta(years=1)

# --- INICIO ---
st.title("Sistema ESD en Tiempo Real (Google Cloud)")

df_piso_local, df_mob_local = cargar_datos_cloud()

tab1, tab2 = st.tabs(["🗺️ Mapa y Reportes", "📱 Escáner Automático"])

# ==========================================
# PESTAÑA 1: MAPA (Igual que antes, pero con datos de la nube)
# ==========================================
with tab1:
    # (Aquí va el mismo código del mapa que ya tienes, usando df_piso_local y df_mob_local)
    st.info("Los datos mostrados están sincronizados con la Google Sheet corporativa.")

# ==========================================
# PESTAÑA 2: ESCÁNER Y ACTUALIZACIÓN NUBE
# ==========================================
with tab2:
    id_escaneado = st.query_params.get("qr_id", "")

    if not id_escaneado:
        # (Aquí va el componente HTML5 de la cámara que insertamos antes)
        st.markdown("### 📷 Escaneo Automático")
        # [Insertar aquí el componente html_code del mensaje anterior]
        
    if id_escaneado:
        st.success(f"🔍 **ID Detectado:** {id_escaneado}")
        
        # Buscar en qué hoja está
        encontrado_piso = id_escaneado in df_piso_local['Id de producto'].values
        encontrado_mob = id_escaneado in df_mob_local['Id de producto'].values

        if encontrado_piso or encontrado_mob:
            hoja_activa = "PISO" if encontrado_piso else "MOBILIARIO"
            df_actual = df_piso_local if encontrado_piso else df_mob_local
            
            idx = df_actual[df_actual['Id de producto'] == id_escaneado].index[0]
            equipo = df_actual.iloc[idx]
            
            with st.form("update_form"):
                nuevo_valor = st.number_input("Valor Medido (Ohms)", value=float(equipo.get('Valor de verificación', 0)) or 0.0)
                nueva_fecha = st.date_input("Fecha Hoy", datetime.today())
                
                if st.form_submit_button("Sincronizar con Google Sheets"):
                    # 1. Realizar cálculos
                    frecuencia = str(equipo.get('Frecuencia de verificación', 'Anual'))
                    proxima = calcular_proxima_fecha(nueva_fecha, frecuencia)
                    
                    # 2. Actualizar el DataFrame local
                    df_actual.at[idx, 'Valor de verificación'] = nuevo_valor
                    df_actual.at[idx, 'Fecha de verificación'] = nueva_fecha.strftime("%Y-%m-%d")
                    df_actual.at[idx, 'Fecha de próxima verificación'] = proxima.strftime("%Y-%m-%d")
                    df_actual.at[idx, 'Estatus de verificación'] = 'VIGENTE'
                    
                    # 3. EMPUJAR A LA NUBE (Write)
                    # Esta función sobreescribe la hoja manteniendo la estructura
                    conn.update(worksheet=hoja_activa, data=df_actual)
                    
                    st.success("✅ ¡Actualizado en Google Sheets para todos los usuarios!")
                    st.cache_data.clear()
                    st.query_params.clear()
                    st.rerun()
        else:
            st.error("ID no encontrado.")
            if st.button("Reintentar Escaneo"):
                st.query_params.clear()
                st.rerun()
