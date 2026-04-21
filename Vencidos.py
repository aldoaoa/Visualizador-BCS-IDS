import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import gc
import base64
import math
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# Configuración de página
st.set_page_config(page_title="Control ESD BCS-AIS", layout="wide")

# ==========================================
# FUNCIONES AUXILIARES DE URL Y SESIÓN
# ==========================================
def codificar_sesion(nombre):
    return base64.b64encode(nombre.encode('utf-8')).decode('utf-8')

def decodificar_sesion(token):
    try:
        return base64.b64decode(token.encode('utf-8')).decode('utf-8')
    except:
        return None

def limpiar_url_escaneo():
    if "qr_id" in st.query_params:
        del st.query_params["qr_id"]
    if "ocr_val" in st.query_params:
        del st.query_params["ocr_val"]
    if "qr_baja" in st.query_params:
        del st.query_params["qr_baja"]

# ==========================================
# SEGURIDAD Y ACCESO (POR URL)
# ==========================================
if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = None
if "modo_lectura" not in st.session_state:
    st.session_state.modo_lectura = False

token_actual = st.query_params.get("auth_token")

if token_actual:
    if token_actual == "consulta_mode":
        st.session_state.usuario_nombre = "Usuario de Consulta"
        st.session_state.modo_lectura = True
    else:
        usuario_decodificado = decodificar_sesion(token_actual)
        if usuario_decodificado:
            st.session_state.usuario_nombre = usuario_decodificado
            st.session_state.modo_lectura = False 

if st.session_state.usuario_nombre is None and not st.session_state.modo_lectura:
    st.markdown("<h2 style='text-align: center;'>🛡️ Sistema de Gestión ESD BCS-AIS</h2>", unsafe_allow_html=True)
    col_v1, col_c, col_v2 = st.columns([1, 1.2, 1])
    with col_c:
        tab_login, tab_monitor = st.tabs(["🔒 Ingreso de Auditor", "👁️ Modo Consulta"])
        with tab_login:
            with st.form("login_form"):
                user_input = st.text_input("Usuario (ID)")
                pwd_input = st.text_input("Contraseña", type="password")
                if st.form_submit_button("Ingresar y Editar", use_container_width=True):
                    try:
                        usuarios_db = st.secrets["usuarios"]
                        if user_input in usuarios_db and usuarios_db[user_input]["password"] == pwd_input:
                            nombre_real = usuarios_db[user_input]["nombre"]
                            st.query_params["auth_token"] = codificar_sesion(nombre_real)
                            st.rerun()
                        else:
                            st.error("❌ Credenciales incorrectas")
                    except KeyError:
                        st.error("⚠️ Error en configuración de usuarios.")
        with tab_monitor:
            st.info("El Modo Consulta es de solo lectura.")
            if st.button("👁️ Entrar en Modo Consulta", use_container_width=True):
                st.query_params["auth_token"] = "consulta_mode"
                st.rerun()
else:
    # ==========================================
    # APLICACIÓN PRINCIPAL
    # ==========================================
    RUTA_MAPA = "mapa.jpg" 
    RUTA_COORDENADAS = "coordenadas.csv"

    with st.sidebar:
        if st.session_state.modo_lectura:
            st.warning("👁️ Modo Consulta Activo")
        else:
            st.success(f"👤 Auditor: {st.session_state.usuario_nombre}")
        if st.button("Salir al Menú Principal", use_container_width=True):
            st.session_state.usuario_nombre = None
            st.session_state.modo_lectura = False
            st.query_params.clear() 
            st.rerun()

    conn = st.connection("gsheets", type=GSheetsConnection)

    @st.cache_data(ttl=2, max_entries=1) 
    def cargar_datos_cloud():
        df_piso, df_mob, df_ion = None, None, None
        try: df_piso = conn.read(worksheet="PISO", header=4)
        except: pass
        try: df_mob = conn.read(worksheet="MOBILIARIO", header=4)
        except: pass
        try: df_ion = conn.read(worksheet="IONIZADORES", header=4)
        except: pass
        return df_piso, df_mob, df_ion

    def calcular_proxima_fecha(fecha_actual, frecuencia):
        frecuencia = str(frecuencia).strip().lower()
        if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
        elif 'semestral' in frecuencia: return fecha_actual + relativedelta(months=6)
        elif 'trimestral' in frecuencia: return fecha_actual + relativedelta(months=3)
        elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
        else: return fecha_actual + relativedelta(years=1)

    st.title("Sistema de Gestión ESD BCS-AIS Querétaro")
    
    df_piso_local, df_mob_local, df_ion_local = cargar_datos_cloud()

    if df_mob_local is None:
        st.error("Falla al conectar con el servidor.")
        st.stop()
        
    if "vista_actual" not in st.session_state:
        st.session_state.vista_actual = "Escáner" 

    id_escaneado_url = st.query_params.get("qr_id", "")
    id_baja_url = st.query_params.get("qr_baja", "")
    
    if id_escaneado_url:
        st.session_state.vista_actual = "Escáner"
    elif id_baja_url:
        st.session_state.vista_actual = "Alta"

    if not st.session_state.modo_lectura:
        c_nav1, c_nav2, c_nav3 = st.columns(3)
        with c_nav1:
            if st.button("🗺️ Mapa y Reportes", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
                st.session_state.vista_actual = "Mapa"; limpiar_url_escaneo(); st.rerun()
        with c_nav2:
            if st.button("📱 Escáner / Auditoría", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
                st.session_state.vista_actual = "Escáner"; limpiar_url_escaneo(); st.rerun()
        with c_nav3:
            if st.button("🆕 Alta/Baja Equipos", use_container_width=True, type="primary" if st.session_state.vista_actual == "Alta" else "secondary"):
                st.session_state.vista_actual = "Alta"; limpiar_url_escaneo(); st.rerun()
    else:
        st.session_state.vista_actual = "Escáner"

    st.divider()

    # ==========================================
    # VISTA: ALTA Y BAJA DE EQUIPOS
    # ==========================================
    if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
        st.markdown("### Gestión de Inventario ESD")
        
        # --- SUB-VISTA: BAJA ---
        if id_baja_url:
            if st.button("❌ Cancelar Baja"): limpiar_url_escaneo(); st.rerun()
            id_limpio_baja = str(id_baja_url).strip().upper()
            es_mob_baja = id_limpio_baja in df_mob_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper().values
            es_ion_baja = id_limpio_baja in df_ion_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper().values if df_ion_local is not None else False

            if es_mob_baja or es_ion_baja:
                hoja = "MOBILIARIO" if es_mob_baja else "IONIZADORES"
                df = df_mob_local if es_mob_baja else df_ion_local
                idx = df[df['Id de producto'].astype(str).str.strip().str.upper() == id_limpio_baja].index[0]
                equipo = df.loc[idx]
                
                st.metric("Ubicación Detectada", str(equipo.get('Línea', 'N/A')))
                if st.button("🗑️ Confirmar Desactivación (No Operativo)"):
                    import gspread
                    sec = dict(st.secrets["connections"]["gsheets"])
                    gc = gspread.service_account_from_dict(sec)
                    ws = gc.open_by_url(sec["spreadsheet"]).worksheet(hoja)
                    r_idx = ws.col_values(df.columns.get_loc('Id de producto') + 1).index(id_limpio_baja) + 1
                    ws.update_cell(r_idx, df.columns.get_loc('Estatus operativo') + 1, "NO OPERATIVO")
                    ws.update_cell(r_idx, df.columns.get_loc('Estatus de verificación') + 1, "BAJA")
                    st.success("Equipo actualizado a No Operativo"); st.cache_data.clear(); limpiar_url_escaneo(); st.rerun()
            else:
                st.error("ID no encontrado en ninguna base de datos."); st.button("Volver", on_click=limpiar_url_escaneo)

        else:
            # Vista normal de Alta / Baja
            with st.expander("📋 Directorio de IDs Existentes"):
                tipo_dir = st.radio("Ver:", ["Mobiliario", "Ionizadores"], horizontal=True)
                df_dir = df_mob_local if tipo_dir == "Mobiliario" else df_ion_local
                if df_dir is not None:
                    st.dataframe(df_dir[df_dir['Estatus operativo'] != 'NO OPERATIVO'][['Línea', 'Id de producto', 'Clasificación']], use_container_width=True, hide_index=True)

            tab_alta, tab_baja = st.tabs(["🆕 Registrar Nuevo", "🗑️ Dar de Baja"])
            
            with tab_alta:
                # (Lógica de alta simplificada para este bloque)
                st.info("Completa el formulario de registro para nuevos activos.")
                # ... (resto de lógica de formulario de alta del checkpoint anterior) ...

            with tab_baja:
                st.markdown("#### Escanea el equipo a dar de baja")
                # ESCÁNER DE BAJA CON ZOOM
                html_code_baja = """
                <script src="https://unpkg.com/html5-qrcode"></script>
                <div id="reader_baja" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd;"></div>
                <div style="text-align:center; margin-top:10px;">
                    <button id="zoom_btn_baja" style="padding:10px 20px; background:#0052cc; color:white; border:none; border-radius:5px; font-weight:bold;">🔍 MODO RACK CURVO (ZOOM)</button>
                </div>
                <script>
                var isZoomed = false;
                Html5Qrcode.getCameras().then(devices => {
                    if (devices && devices.length) {
                        let selectedId = devices[0].id;
                        let back = devices.find(d => d.label.toLowerCase().includes('back') || d.label.toLowerCase().includes('trasera'));
                        if (back) selectedId = back.id;
                        const html5QrCode = new Html5Qrcode("reader_baja");
                        html5QrCode.start(selectedId, { fps: 15, qrbox: 250 }, (txt) => {
                            html5QrCode.stop();
                            const url = new URL(window.parent.location.href);
                            url.searchParams.set("qr_baja", txt);
                            window.parent.location.reload();
                        }).then(() => {
                            document.getElementById('zoom_btn_baja').addEventListener('click', () => {
                                const track = html5QrCode.getRunningTrack();
                                const capabilities = track.getCapabilities();
                                if (capabilities.zoom) {
                                    isZoomed = !isZoomed;
                                    track.applyConstraints({ advanced: [{ zoom: isZoomed ? capabilities.zoom.max / 2 : capabilities.zoom.min }] });
                                    document.getElementById('zoom_btn_baja').innerText = isZoomed ? "🔄 VOLVER A 1X" : "🔍 MODO RACK CURVO (ZOOM)";
                                    document.getElementById('zoom_btn_baja').style.background = isZoomed ? "#d9534f" : "#0052cc";
                                } else { alert("Tu cámara no soporta Zoom digital."); }
                            });
                        });
                    }
                });
                </script>
                """
                components.html(html_code_baja, height=650)
                man_b = st.text_input("O ingresa ID manual para baja:")
                if man_b: st.query_params["qr_baja"] = man_b; st.rerun()

    # ==========================================
    # VISTA: MAPA
    # ==========================================
    elif st.session_state.vista_actual == "Mapa":
        st.info("Visualización de cumplimiento por área.")
        # ... (lógica de mapa del checkpoint anterior) ...

    # ==========================================
    # VISTA: ESCÁNER / AUDITORÍA
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        if not id_escaneado_url:
            st.markdown("### 📷 Identificar Activo")
            # ESCÁNER PRINCIPAL CON ZOOM
            html_qr_zoom = """
            <script src="https://unpkg.com/html5-qrcode"></script>
            <div id="reader_main" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0052cc;"></div>
            <div style="text-align:center; margin-top:10px;">
                <button id="zoom_btn_main" style="padding:10px 20px; background:#0052cc; color:white; border:none; border-radius:5px; font-weight:bold;">🔍 MODO RACK CURVO (ZOOM)</button>
            </div>
            <script>
            var isZoomedMain = false;
            const html5QrCodeMain = new Html5Qrcode("reader_main");
            html5QrCodeMain.start({ facingMode: "environment" }, { fps: 15, qrbox: 250 }, (txt) => {
                html5QrCodeMain.stop();
                const url = new URL(window.parent.location.href);
                url.searchParams.set("qr_id", txt);
                window.parent.location.reload();
            }).then(() => {
                document.getElementById('zoom_btn_main').addEventListener('click', () => {
                    const track = html5QrCodeMain.getRunningTrack();
                    const capabilities = track.getCapabilities();
                    if (capabilities.zoom) {
                        isZoomedMain = !isZoomedMain;
                        track.applyConstraints({ advanced: [{ zoom: isZoomedMain ? capabilities.zoom.max / 2 : capabilities.zoom.min }] });
                        document.getElementById('zoom_btn_main').innerText = isZoomedMain ? "🔄 VOLVER A 1X" : "🔍 MODO RACK CURVO (ZOOM)";
                        document.getElementById('zoom_btn_main').style.background = isZoomedMain ? "#d9534f" : "#0052cc";
                    } else { alert("Tu cámara no soporta Zoom digital."); }
                });
            });
            </script>
            """
            components.html(html_qr_zoom, height=650)
            man_main = st.text_input("Ingresar ID manual:")
            if man_main: st.query_params["qr_id"] = man_main; st.rerun()
        else:
            # Lógica de actualización (Número x 10^Exp y selector de Línea)
            if st.button("❌ Cerrar Escaneo"): limpiar_url_escaneo(); st.rerun()
            # ... (Resto de la lógica de actualización con historial y columnas S que ya teníamos) ...
            st.success("Equipo identificado. Procede con la medición.")
            # (Aquí va el formulario form_upd que ya construimos antes)
