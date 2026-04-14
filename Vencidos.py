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

# Configuración de página
st.set_page_config(page_title="Control ESD Corporativo", layout="wide")

# Inicializar controlador de cookies
controller = CookieController()

# ==========================================
# SEGURIDAD Y ACCESO
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
            st.warning("👁️ Modo Consulta Activo")
        else:
            st.success(f"👤 Auditor: {st.session_state.usuario_nombre}")
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
    # VISTA: ALTA DE MOBILIARIO
    # ==========================================
    if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
        st.markdown("### 🆕 Registrar Nuevo Mobiliario")
        
        lineas_disponibles = sorted([str(x).strip() for x in df_mob_local['Línea'].unique() if pd.notna(x) and str(x).strip() != ''])
        tipos_disponibles = sorted([str(x).strip() for x in df_mob_local['Clasificación'].unique() if pd.notna(x) and str(x).strip() != ''])

        with st.form("form_alta_mobiliario"):
            col1, col2 = st.columns(2)
            nueva_linea = col1.selectbox("Línea (ubicación)", options=lineas_disponibles)
            nuevo_id = col2.text_input("ID de Producto (Ej: MOB-001)")
            nuevo_tipo = col1.selectbox("Tipo de Mobiliario (Clasificación)", options=tipos_disponibles)
            
            # Lógica de Fabricante
            fabricante_opc = col2.selectbox("Fabricante", options=["BCS", "Otro", "N/A"])
            fabricante_final = fabricante_opc
            if fabricante_opc == "Otro":
                fabricante_final = col2.text_input("Especifique Fabricante", help="Ingrese el nombre de la marca")

            col3, col4 = st.columns(2)
            nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e")
            limite_alta = col4.text_input("Límite S20.20 (Maximo)", value="1.00E+09")
            
            frecuencia_alta = col3.selectbox("Frecuencia de verificación", options=["Anual", "Semestral", "Trimestral", "Mensual"])
            valor_alta = col4.number_input("Valor de medición inicial (Opcional - Ohms)", value=0.0, format="%.2e")
            
            comentarios = st.text_area("Comentarios (Notas opcionales)")
            
            if st.form_submit_button("Registrar en Google Sheets", use_container_width=True):
                if not nuevo_id or (fabricante_opc == "Otro" and not fabricante_final):
                    st.error("Por favor complete los campos obligatorios (ID y Fabricante).")
                elif nuevo_id in df_mob_local['Id de producto'].values:
                    st.error(f"El ID {nuevo_id} ya existe.")
                else:
                    with st.spinner("Guardando registro..."):
                        import gspread
                        sec = dict(st.secrets["connections"]["gsheets"])
                        gc = gspread.service_account_from_dict(sec)
                        ws = gc.open_by_url(sec["spreadsheet"]).worksheet("MOBILIARIO")
                        
                        fecha_hoy = datetime.today().date()
                        dias_map = {"Anual": 360, "Semestral": 180, "Trimestral": 90, "Mensual": 30}
                        proxima = fecha_hoy + timedelta(days=dias_map.get(frecuencia_alta, 360))
                        
                        # Construcción de Fila A-R
                        nueva_fila = [
                            nueva_linea,                                     # A: Línea
                            nuevo_id,                                        # B: Id de producto
                            nuevo_tipo,                                      # C: Clasificación
                            "Aprobado",                                      # D: Etiquetado
                            fabricante_final,                                # E: Marca
                            float(nuevo_minimo),                             # F: Minimo
                            float(limite_alta) if "E" in limite_alta.upper() else limite_alta, # G: Maximo
                            "Ohms",                                          # H: Unidad de aceptabilidad
                            float(valor_alta) if valor_alta > 0 else "",      # I: Valor de verificación
                            "Ohms",                                          # J: Unidad verificada
                            "RTG",                                           # K: Método
                            fecha_hoy.strftime("%d-%b-%Y") if valor_alta > 0 else "", # L: Fecha de verificación
                            proxima.strftime("%d-%b-%Y") if valor_alta > 0 else "",   # M: Fecha de próxima
                            frecuencia_alta,                                 # N: Frecuencia de verificación
                            "Vigente" if valor_alta > 0 and fecha_hoy < proxima else "", # O: Estatus de verificación
                            "Operativo",                                     # P: Estatus operativo
                            comentarios,                                     # Q: Notas
                            st.session_state.usuario_nombre                  # R: Auditor
                        ]
                        
                        ws.append_row(nueva_fila, value_input_option="USER_ENTERED")
                        st.success(f"✅ {nuevo_id} registrado correctamente.")
                        st.cache_data.clear()
                        st.rerun()

    # ==========================================
    # VISTA 1: MAPA Y REPORTES
    # ==========================================
    elif st.session_state.vista_actual == "Mapa":
        df_piso_mapa = df_piso_local.copy()
        df_piso_mapa['Hoja Origen'] = 'PISO'
        df_mob_mapa = df_mob_local.copy()
        df_mob_mapa['Hoja Origen'] = 'MOBILIARIO'
        df_total = pd.concat([df_piso_mapa, df_mob_mapa], ignore_index=True)
        df_total['Estatus de verificación'] = df_total['Estatus de verificación'].astype(str).str.strip().str.upper()
        vencidos = df_total[df_total['Estatus de verificación'] == 'VENCIDO']
        
        if not vencidos.empty:
            conteo = vencidos.groupby(['Línea']).size().reset_index(name='Total')
            if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                img = Image.open(RUTA_MAPA)
                w, h = img.size
                df_c = pd.read_csv(RUTA_COORDENADAS)
                m_data = pd.merge(conteo, df_c, on='Línea')
                fig = px.scatter(m_data, x="X", y="Y", text="Total", size_max=30)
                fig.update_traces(marker=dict(symbol='square', size=26, color='red'))
                fig.update_layout(images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=w, sizey=h, sizing="stretch", layer="below")],
                                  xaxis=dict(visible=False, range=[0, w]), yaxis=dict(visible=False, range=[h, 0], scaleanchor="x"))
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(vencidos[['Línea', 'Id de producto', 'Clasificación']], use_container_width=True, hide_index=True)
        else:
            st.success("✅ Todo vigente.")

    # ==========================================
    # VISTA 2: ESCÁNER
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        if not id_escaneado_url:
            html_qr = """
            <script src="https://unpkg.com/html5-qrcode"></script>
            <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden;"></div>
            <script>
            function onScanSuccess(decodedText) {
                const url = new URL(window.parent.location.href);
                url.searchParams.set("qr_id", decodedText);
                window.parent.history.replaceState({}, "", url);
                window.parent.location.reload();
            }
            let scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
            scanner.render(onScanSuccess);
            </script> """
            components.html(html_qr, height=500)
        else:
            df_a = df_piso_local if id_escaneado_url in df_piso_local['Id de producto'].values else df_mob_local
            if id_escaneado_url in df_a['Id de producto'].values:
                eq = df_a[df_a['Id de producto'] == id_escaneado_url].iloc[0]
                st.metric("ID", id_escaneado_url)
                st.write(f"**Ubicación:** {eq['Línea']} | **Estatus:** {eq['Estatus de verificación']}")
                # Lógica de actualización similar a la implementación anterior...
