import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import gc
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
from streamlit_cookies_controller import CookieController

# Configuración horizontal
st.set_page_config(page_title="Control ESD Corporativo", layout="wide")

controller = CookieController()

# ==========================================
# CAPA DE SEGURIDAD (COOKIES Y ROLES)
# ==========================================
if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = None
if "modo_lectura" not in st.session_state:
    st.session_state.modo_lectura = False

cookie_auditor = controller.get('auditor_esd_sesion')
if cookie_auditor:
    st.session_state.usuario_nombre = cookie_auditor
    st.session_state.modo_lectura = False 

if st.session_state.usuario_nombre is None and not st.session_state.modo_lectura:
    st.markdown("<h2 style='text-align: center;'>🛡️ Sistema de Gestión ESD S20.20</h2>", unsafe_allow_html=True)
    col_v1, col_c, col_v2 = st.columns([1, 1.2, 1])
    with col_c:
        tab_login, tab_monitor = st.tabs(["🔒 Ingreso de Auditores", "👁️ Modo Consulta"])
        with tab_login:
            with st.form("login_form"):
                user_input = st.text_input("Usuario (ID)")
                pwd_input = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Ingresar y Editar", use_container_width=True):
                    try:
                        usuarios_db = st.secrets["usuarios"]
                        if user_input in usuarios_db and usuarios_db[user_input]["password"] == pwd_input:
                            nombre_real = usuarios_db[user_input]["nombre"]
                            st.session_state.usuario_nombre = nombre_real
                            st.session_state.modo_lectura = False
                            expira = datetime.now() + timedelta(days=7)
                            controller.set('auditor_esd_sesion', nombre_real, expires=expira)
                            st.rerun()
                        else:
                            st.error("❌ Credenciales incorrectas")
                    except KeyError:
                        st.error("⚠️ Error en configuración de usuarios.")
        with tab_monitor:
            st.info("El Modo Consulta es de solo lectura.")
            if st.button("👁️ Entrar en Modo Consulta", use_container_width=True):
                st.session_state.modo_lectura = True
                st.session_state.usuario_nombre = "Usuario de Consulta"
                st.rerun()
else:
    # ==========================================
    # APLICACIÓN PRINCIPAL
    # ==========================================
    RUTA_MAPA = "mapa.jpg" 
    RUTA_COORDENADAS = "coordenadas.csv"

    with st.sidebar:
        if st.session_state.modo_lectura:
            st.warning("👁️ **Modo Consulta Activo**")
        else:
            st.success(f"👤 **Auditor:** {st.session_state.usuario_nombre}")
        if st.button("Salir al Menú Principal", use_container_width=True):
            st.session_state.usuario_nombre = None
            st.session_state.modo_lectura = False
            try: controller.remove('auditor_esd_sesion')
            except KeyError: pass
            st.rerun()

    conn = st.connection("gsheets", type=GSheetsConnection)

    @st.cache_data(ttl=2, max_entries=1) 
    def cargar_datos_cloud():
        try:
            df_piso = conn.read(worksheet="PISO", header=4)
            df_mob = conn.read(worksheet="MOBILIARIO", header=4)
            return df_piso, df_mob
        except Exception: return None, None

    def calcular_proxima_fecha(fecha_actual, frecuencia):
        frecuencia = str(frecuencia).strip().lower()
        if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
        elif 'semestral' in frecuencia: return fecha_actual + relativedelta(months=6)
        elif 'trimestral' in frecuencia: return fecha_actual + relativedelta(months=3)
        elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
        else: return fecha_actual + relativedelta(years=1)

    st.title("Sistema de Gestión ESD S20.20")
    df_piso_local, df_mob_local = cargar_datos_cloud()

    if df_piso_local is None or df_mob_local is None:
        st.error("Falla al conectar con Google Sheets.")
        st.stop()

    if "vista_actual" not in st.session_state:
        st.session_state.vista_actual = "Escáner" 

    id_escaneado_url = st.query_params.get("qr_id", "")
    valor_ocr_detectado = st.query_params.get("ocr_val", "")
    if id_escaneado_url or valor_ocr_detectado:
        st.session_state.vista_actual = "Escáner"

    # --- NAVEGACIÓN ACTUALIZADA (3 COLUMNAS PARA AUDITORES) ---
    if not st.session_state.modo_lectura:
        c_nav1, c_nav2, c_nav3 = st.columns(3)
        with c_nav1:
            if st.button("🗺️ Mapa y Reportes", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
                st.session_state.vista_actual = "Mapa"; st.query_params.clear(); st.rerun()
        with c_nav2:
            if st.button("📱 Escáner / Auditoría", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
                st.session_state.vista_actual = "Escáner"; st.rerun()
        with c_nav3:
            if st.button("🆕 Alta Mobiliario", use_container_width=True, type="primary" if st.session_state.vista_actual == "Alta" else "secondary"):
                st.session_state.vista_actual = "Alta"; st.query_params.clear(); st.rerun()
    else:
        st.session_state.vista_actual = "Escáner"

    st.divider()

    # ==========================================
    # VISTA: ALTA DE MOBILIARIO (NUEVA)
    # ==========================================
    if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
        st.markdown("### 🆕 Registrar Nuevo Mobiliario en el Sistema")
        st.write("Complete los datos para agregar un nuevo activo a la base de datos corporativa.")
        
        # Obtenemos las líneas existentes para el dropdown
        # Limpiamos vacíos (NaN) y aseguramos que todo sea texto antes de ordenar alfabéticamente
        lineas_disponibles = sorted([str(x).strip() for x in df_mob_local['Línea'].unique() if pd.notna(x) and str(x).strip() != ''])
        tipos_disponibles = sorted([str(x).strip() for x in df_mob_local['Clasificación'].unique() if pd.notna(x) and str(x).strip() != ''])

        with st.form("form_alta_mobiliario"):
            col1, col2 = st.columns(2)
            nueva_linea = col1.selectbox("Línea (Ubicación)", options=lineas_disponibles)
            nuevo_id = col2.text_input("ID de Producto (Ej: MOB-001)")
            
            nuevo_tipo = col1.selectbox("Tipo de Mobiliario (Clasificación)", options=tipos_disponibles)
            # Valor de medición opcional para el alta
            valor_alta = col2.number_input("Valor de medición inicial (Opcional - Ohms)", value=0.0, format="%.2e")
            
            frecuencia_alta = col1.selectbox("Frecuencia de verificación", options=["Anual", "Semestral", "Trimestral", "Mensual"], index=0)
            limite_alta = col2.text_input("Límite S20.20 (Maximo)", value="1.00E+09")
            
            submit_alta = st.form_submit_button("Registrar en Google Sheets", use_container_width=True)
            
            if submit_alta:
                if not nuevo_id:
                    st.error("El campo ID de Producto es obligatorio.")
                elif nuevo_id in df_mob_local['Id de producto'].values:
                    st.error(f"El ID {nuevo_id} ya existe en el sistema.")
                else:
                    with st.spinner("Creando nuevo registro corporativo..."):
                        import gspread
                        sec = dict(st.secrets["connections"]["gsheets"])
                        gc = gspread.service_account_from_dict(sec)
                        ws = gc.open_by_url(sec["spreadsheet"]).worksheet("MOBILIARIO")
                        
                        fecha_hoy = datetime.today().date()
                        proxima = calcular_proxima_fecha(fecha_hoy, frecuencia_alta)
                        
                        # Construimos la fila basándonos en el orden de las columnas de tu documento
                        # El orden estándar según tus formularios previos:
                        # Línea | Id | Clasificación | Frecuencia | Maximo | Valor | Unidad | Fecha | Proxima | Estatus | Auditor
                        # Nota: Ajusta el orden según las columnas exactas de tu Fila 5
                        nueva_fila = [
                            nueva_linea,            # Línea
                            nuevo_id,               # Id de producto
                            nuevo_tipo,             # Clasificación
                            "OPERATIVO",            # Estatus operativo (default)
                            frecuencia_alta,        # Frecuencia
                            "Ω",                    # Unidad
                            float(limite_alta) if "E" in limite_alta else limite_alta, # Maximo
                            float(valor_alta) if valor_alta > 0 else "", # Valor de verificación
                            fecha_hoy.strftime("%d-%b-%Y"), # Fecha de verificación
                            proxima.strftime("%d-%b-%Y"),   # Fecha de próxima
                            "VIGENTE" if valor_alta > 0 else "NUEVO", # Estatus de verificación
                            st.session_state.usuario_nombre # Auditor
                        ]
                        
                        ws.append_row(nueva_fila, value_input_option="USER_ENTERED")
                        
                    st.success(f"✅ ¡Activo {nuevo_id} registrado exitosamente en la línea {nueva_linea}!")
                    st.cache_data.clear()
                    st.balloons()

    # ==========================================
    # VISTA 1: MAPA Y REPORTES
    # ==========================================
    elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
        # (Lógica existente de Mapas y Reportes...)
        st.info("Visualizando reporte de cumplimiento corporativo.")
        # ... [Resto del código del mapa que ya tienes]

    # ==========================================
    # VISTA 2: ESCÁNER / AUDITORÍA
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        # (Lógica existente de Escaneo de QR y OCR...)
        # ... [Resto del código del escáner que ya tienes]
        if not id_escaneado_url:
            st.markdown("### 📷 Apunta al Código QR")
            # [Tu componente html_code_qr aquí...]
        else:
            # [Tu lógica de detalles y actualización aquí...]
            pass
