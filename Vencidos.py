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
import fitz  # PyMuPDF
import re
import io
import pytesseract

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
        df_piso, df_mob, df_ion, df_em = None, None, None, None
        try: df_piso = conn.read(worksheet="PISO", header=4)
        except: pass
        try: df_mob = conn.read(worksheet="MOBILIARIO", header=4)
        except: pass
        try: df_ion = conn.read(worksheet="IONIZADORES", header=4)
        except: pass
        try: df_em = conn.read(worksheet="EVENT_METER") # Cambia el header=4 si tus encabezados no están en la fila 1
        except: pass
        return df_piso, df_mob, df_ion, df_em

    def calcular_proxima_fecha(fecha_actual, frecuencia):
        frecuencia = str(frecuencia).strip().lower()
        if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
        elif 'semestral' in frecuencia: return fecha_actual + relativedelta(months=6)
        elif 'trimestral' in frecuencia: return fecha_actual + relativedelta(months=3)
        elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
        else: return fecha_actual + relativedelta(years=1)

    st.title("Sistema de Gestión ESD BCS-AIS Querétaro")
    
    df_piso_local, df_mob_local, df_ion_local, df_em_local = cargar_datos_cloud()
    
    # Fallback de seguridad por si la pestaña está vacía al inicio
    if df_em_local is None:
        df_em_local = pd.DataFrame(columns=['Línea', 'Id de Operación'])

    if df_mob_local is None:
        st.error("Falla al conectar con el servidor.")
        st.stop()
        
    if df_ion_local is None:
        st.warning("⚠️ No se encontró la DB 'IONIZADORES'.")
        df_ion_local = pd.DataFrame(columns=df_mob_local.columns.tolist() + ['Balance'])

    if "vista_actual" not in st.session_state:
        st.session_state.vista_actual = "Escáner" 

    id_escaneado_url = st.query_params.get("qr_id", "")
    valor_ocr_detectado = st.query_params.get("ocr_val", "")
    id_baja_url = st.query_params.get("qr_baja", "")
    
    if id_escaneado_url or valor_ocr_detectado:
        st.session_state.vista_actual = "Escáner"
    elif id_baja_url:
        st.session_state.vista_actual = "Alta"

    if not st.session_state.modo_lectura:
        c_nav1, c_nav2, c_nav3, c_nav4, c_nav5 = st.columns(5)
        with c_nav1:
            if st.button("🗺️ Mapa y Reportes", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
                st.session_state.vista_actual = "Mapa"
                limpiar_url_escaneo() 
                st.rerun()
        with c_nav2:
            if st.button("📱 Escáner / Auditoría", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
                st.session_state.vista_actual = "Escáner"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav3:
            if st.button("🆕 Alta/Baja", use_container_width=True, type="primary" if st.session_state.vista_actual == "Alta" else "secondary"):
                st.session_state.vista_actual = "Alta"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav4:
            if st.button("⚡ Event Meter", use_container_width=True, type="primary" if st.session_state.vista_actual == "Event Meter" else "secondary"):
                st.session_state.vista_actual = "Event Meter"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav5:
            if st.button("🚶‍♂️ Walking Test", use_container_width=True, type="primary" if st.session_state.vista_actual == "Walking Test" else "secondary"):
                st.session_state.vista_actual = "Walking Test"
                limpiar_url_escaneo()
                st.rerun()
    else:
        st.session_state.vista_actual = "Escáner"

    st.divider()

    # ==========================================
    # VISTA: ALTA Y BAJA DE EQUIPOS
    # ==========================================
    if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
        st.markdown("### Gestión de Inventario ESD")
        
        with st.expander("📋 Directorio de IDs Existentes (Click para abrir/cerrar)", expanded=False):
            tipo_dir = st.radio("Ver directorio de:", ["Mobiliario", "Ionizadores"], horizontal=True)
            df_dir = df_mob_local if tipo_dir == "Mobiliario" else df_ion_local
            
            st.info("💡 **Tip:** Haz clic en el título de una columna para ordenar (A-Z) o usa la lupa (🔍) para buscar un ID específico.")
            if not df_dir.empty and 'Id de producto' in df_dir.columns and 'Línea' in df_dir.columns:
                if 'Estatus operativo' in df_dir.columns:
                    df_clean = df_dir[df_dir['Estatus operativo'].astype(str).str.strip().str.upper() != 'NO OPERATIVO']
                else:
                    df_clean = df_dir.copy()
                    
                df_clean = df_clean[['Línea', 'Id de producto', 'Clasificación']].dropna(subset=['Id de producto'])
                df_clean = df_clean[df_clean['Id de producto'].astype(str).str.strip() != '']
                st.dataframe(df_clean, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay datos disponibles aún en esta categoría.")
        
        st.divider()
        
        if "radio_alta_baja" not in st.session_state:
            st.session_state.radio_alta_baja = "🆕 Registrar Nuevo"
            
        if id_baja_url:
            st.session_state.radio_alta_baja = "🗑️ Dar de Baja"

        accion_seleccionada = st.radio(
            "Selecciona la acción a realizar:",
            ["🆕 Registrar Nuevo", "🗑️ Dar de Baja"],
            horizontal=True,
            label_visibility="collapsed",
            key="radio_alta_baja"
        )
        
        # --- SUB-VISTA 1: ALTA ---
        if accion_seleccionada == "🆕 Registrar Nuevo":
            
            tipo_alta = st.radio("Categoría del Equipo a Registrar:", ["Mobiliario", "Ionizador"], horizontal=True)
            df_target_alta = df_mob_local if tipo_alta == "Mobiliario" else df_ion_local
            
            todas_lineas = set()
            for df_temp in [df_piso_local, df_mob_local, df_ion_local]:
                if df_temp is not None and 'Línea' in df_temp.columns:
                    todas_lineas.update([str(x).strip() for x in df_temp['Línea'].dropna() if str(x).strip() != ''])
            lineas_disponibles = sorted(list(todas_lineas))

            with st.form("form_alta_equipo"):
                col1, col2 = st.columns(2)
                nueva_linea = col1.selectbox("Línea (Ubicación)", options=lineas_disponibles if lineas_disponibles else ["SMT", "Ensamble"])
                nuevo_id = col2.text_input("ID de Producto (Ej: " + ("MOB-001" if tipo_alta=="Mobiliario" else "ION-001") + ")")
                
                if tipo_alta == "Mobiliario":
                    tipos_disponibles = sorted([str(x).strip() for x in df_target_alta.get('Clasificación', pd.Series()).unique() if pd.notna(x) and str(x).strip() != ''])
                    nuevo_tipo = col1.selectbox("Tipo / Clasificación", options=tipos_disponibles if tipos_disponibles else ["Mesa", "Silla"])
                    
                    with col2:
                        st.caption("Valor de medición inicial (Opcional - Ohms)")
                        c_b, c_x, c_e = st.columns([2, 1, 2])
                        base_alta = c_b.number_input("Número", value=0.0, format="%.2f")
                        c_x.markdown("<div style='text-align: center; margin-top: 30px; font-weight: bold; font-size: 18px;'>x 10^</div>", unsafe_allow_html=True)
                        exp_alta = c_e.number_input("Exponente", value=0, step=1, format="%d")
                        valor_alta = base_alta * (10 ** exp_alta) if base_alta != 0 else 0.0
                    
                    fabricante_opc = col1.selectbox("Fabricante", options=["BCS", "Otro", "N/A"])
                    fabricante_final = fabricante_opc
                    if fabricante_opc == "Otro":
                        fabricante_final = col1.text_input("Especifique Fabricante")
                        
                    frecuencia_alta = col2.selectbox("Frecuencia de verificación", options=["Anual", "Semestral", "Trimestral", "Mensual"], index=0)
                    col3, col4 = st.columns(2)
                    nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e")
                    limite_alta = col4.text_input("Límite S20.20 (Maximo)", value="1.00E+09")
                    
                else:
                    nuevo_tipo = col1.selectbox("Tipo / Clasificación", options=["Ventilador", "Barra", "Pistola"])
                    valor_alta = col2.number_input("Tiempo de descarga inicial (Seg)", value=0.0, format="%.2f")
                    
                    fabricante_opc = col1.selectbox("Fabricante", options=["SMC", "Panasonic", "Keyence", "SIMCO", "Otro"])
                    fabricante_final = fabricante_opc
                    if fabricante_opc == "Otro":
                        fabricante_final = col1.text_input("Especifique Fabricante")
                        
                    balance_alta = col2.number_input("Balance Inicial (V)", value=0.0, format="%.2f")
                    frecuencia_alta = "Trimestral"
                    nuevo_minimo = 0.00
                    limite_alta = "10.00"

                comentarios = st.text_area("Comentarios (Notas opcionales)")
                submit_alta = st.form_submit_button("Registrar en sistema", use_container_width=True)
                
                if submit_alta:
                    if not nuevo_id or (fabricante_opc == "Otro" and not fabricante_final):
                        st.error("Por favor complete los campos obligatorios (ID y Fabricante).")
                    else:
                        id_limpio_alta = str(nuevo_id).strip().upper()
                        ids_existentes = df_target_alta.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper().values
                        
                        if id_limpio_alta in ids_existentes:
                            st.error(f"El ID {nuevo_id} ya existe en la base de datos de {tipo_alta}.")
                        else:
                            with st.spinner("Creando nuevo registro..."):
                                import gspread
                                sec = dict(st.secrets["connections"]["gsheets"])
                                gc_client = gspread.service_account_from_dict(sec)
                                nombre_hoja = "MOBILIARIO" if tipo_alta == "Mobiliario" else "IONIZADORES"
                                ws = gc_client.open_by_url(sec["spreadsheet"]).worksheet(nombre_hoja)
                                
                                fecha_hoy = datetime.today().date()
                                dias_map = {"Anual": 360, "Semestral": 180, "Trimestral": 90, "Mensual": 30}
                                proxima = fecha_hoy + timedelta(days=dias_map.get(frecuencia_alta, 360))
                                
                                unidad_medida = "Segundos" if tipo_alta == "Ionizador" else "Ohms"
                                metodo = "CPM" if tipo_alta == "Ionizador" else "RTG"
                                
                                nueva_fila = [
                                    nueva_linea,                                     
                                    nuevo_id,                                        
                                    nuevo_tipo,                                      
                                    "Aprobado",                                      
                                    fabricante_final,                                
                                    float(nuevo_minimo),                             
                                    float(limite_alta) if "E" in limite_alta.upper() else limite_alta, 
                                    unidad_medida,                                          
                                    float(valor_alta) if valor_alta > 0 else "",      
                                    unidad_medida,                                          
                                    metodo,                                           
                                    fecha_hoy.strftime("%d-%b-%Y") if valor_alta > 0 else "", 
                                    proxima.strftime("%d-%b-%Y") if valor_alta > 0 else "",   
                                    frecuencia_alta,                                 
                                    "Vigente" if valor_alta > 0 and fecha_hoy < proxima else "", 
                                    "Operativo",                                     
                                    comentarios,                                     
                                    st.session_state.usuario_nombre                  
                                ]
                                
                                if tipo_alta == "Ionizador":
                                    if 'Balance' in df_target_alta.columns:
                                        bal_idx = df_target_alta.columns.get_loc('Balance')
                                        while len(nueva_fila) <= bal_idx:
                                            nueva_fila.append("")
                                        nueva_fila[bal_idx] = float(balance_alta)
                                    else:
                                        nueva_fila.append(float(balance_alta))
                                
                                ws.append_row(nueva_fila, value_input_option="USER_ENTERED")
                                
                            st.success(f"✅ ¡Activo {nuevo_id} registrado exitosamente en {nombre_hoja}!")
                            st.cache_data.clear()
                            st.balloons()
                            
        # --- SUB-VISTA 2: BAJA (SOFT DELETE) ---
        elif accion_seleccionada == "🗑️ Dar de Baja":
            st.markdown("#### 🗑️ Dar de Baja (Desactivar Equipo)")
            st.info("Esta acción cambiará el estatus del equipo a **NO OPERATIVO**, conservando su historial pero eliminándolo de los reportes y mapas activos.")
            
            if not id_baja_url:
                st.write("Escanea el QR o ingresa manualmente el ID del equipo a dar de baja.")
                html_code_baja = """
                <script src="https://unpkg.com/html5-qrcode"></script>
                <div id="reader_baja" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
                
                <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px; flex-wrap:wrap;">
                    <button type="button" id="cam_wide_baja" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">📸 LENTE ESTÁNDAR</button>
                    <button type="button" id="cam_cycle_baja" style="padding:10px; background:#555; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔄 OTRA CÁMARA</button>
                </div>
                <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px;">
                    <button type="button" id="zoom_1x_baja" style="padding:10px 20px; background:#0052cc; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 1X (NORMAL)</button>
                    <button type="button" id="zoom_3x_baja" style="padding:10px 20px; background:#666; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 3X (CURVO)</button>
                </div>
                <p id="cam-status-baja" style="text-align:center; color:#666; font-size: 14px; margin-top: 10px;">Buscando cámaras...</p>
                
                <script>
                let html5QrCodeBaja;
                let rearCamsBaja = [];
                let currentIdxBaja = 0;
                let wideIdBaja = null;

                function applyZoomBaja(scale) {
                    const vid = document.querySelector("#reader_baja video");
                    if (vid) {
                        vid.style.transform = `scale(${scale})`;
                        vid.style.transformOrigin = "center center";
                    }
                    document.getElementById('zoom_1x_baja').style.background = (scale === 1) ? "#0052cc" : "#666";
                    document.getElementById('zoom_3x_baja').style.background = (scale === 3) ? "#0052cc" : "#666";
                }

                function startScannerBaja(camId) {
                    if(!html5QrCodeBaja) html5QrCodeBaja = new Html5Qrcode("reader_baja");
                    if (html5QrCodeBaja.isScanning) {
                        html5QrCodeBaja.stop().then(() => { runScanBaja(camId); }).catch(e => console.log(e));
                    } else {
                        runScanBaja(camId);
                    }
                }

                function runScanBaja(camId) {
                    html5QrCodeBaja.start(
                        camId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                        (decodedText) => {
                            html5QrCodeBaja.stop();
                            const url = new URL(window.parent.location.href);
                            url.searchParams.set("qr_baja", decodedText);
                            window.parent.history.replaceState({}, "", url);
                            window.parent.location.reload();
                        }, (err) => {} 
                    ).then(() => { 
                        let activeCam = rearCamsBaja.find(c => c.id === camId);
                        document.getElementById("cam-status-baja").innerText = "Lente activo: " + (activeCam ? activeCam.label : "Cámara");
                        applyZoomBaja(1);
                    }).catch(err => {
                        document.getElementById("cam-status-baja").innerText = "Error iniciando lente. Intenta 'Otra Cámara'.";
                    });
                }

                Html5Qrcode.getCameras().then(devices => {
                    if (devices && devices.length) {
                        rearCamsBaja = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera') || c.label.toLowerCase().includes('environment'));
                        if(rearCamsBaja.length === 0) rearCamsBaja = devices;

                        // Buscar la cámara WIDE original (evitar la ULTRAWIDE)
                        wideIdBaja = rearCamsBaja[0].id;
                        for (let c of rearCamsBaja) {
                            let lbl = c.label.toLowerCase();
                            if (lbl.includes('wide') && !lbl.includes('ultra')) {
                                wideIdBaja = c.id; break;
                            }
                        }

                        currentIdxBaja = rearCamsBaja.findIndex(c => c.id === wideIdBaja);
                        if(currentIdxBaja === -1) currentIdxBaja = 0;

                        startScannerBaja(wideIdBaja);

                        document.getElementById('cam_wide_baja').addEventListener('click', () => {
                            currentIdxBaja = rearCamsBaja.findIndex(c => c.id === wideIdBaja);
                            startScannerBaja(wideIdBaja);
                        });

                        document.getElementById('cam_cycle_baja').addEventListener('click', () => {
                            currentIdxBaja = (currentIdxBaja + 1) % rearCamsBaja.length;
                            startScannerBaja(rearCamsBaja[currentIdxBaja].id);
                        });

                        document.getElementById('zoom_1x_baja').addEventListener('click', () => applyZoomBaja(1));
                        document.getElementById('zoom_3x_baja').addEventListener('click', () => applyZoomBaja(3));
                    }
                }).catch(err => { document.getElementById("cam-status-baja").innerText = "Permisos de cámara denegados."; });
                </script>
                """
                components.html(html_code_baja, height=750) 
                
                id_manual_baja = st.text_input("Ingresa el ID manual a eliminar:", key="input_manual_baja")
                if id_manual_baja:
                    st.query_params["qr_baja"] = id_manual_baja
                    st.rerun()
            else:
                colA, colB = st.columns([0.8, 0.2])
                with colA:
                    st.error(f"🗑️ **ID a Procesar:** {id_baja_url}")
                with colB:
                    if st.button("❌ Cancelar"):
                        limpiar_url_escaneo()
                        st.rerun()

                id_limpio_baja = str(id_baja_url).strip().upper()
                mob_ids = df_mob_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()
                ion_ids = df_ion_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()

                es_mob_baja = id_limpio_baja in mob_ids.values
                es_ion_baja = id_limpio_baja in ion_ids.values

                if es_mob_baja or es_ion_baja:
                    hoja_activa_baja = "MOBILIARIO" if es_mob_baja else "IONIZADORES"
                    df_actual_baja = df_mob_local if es_mob_baja else df_ion_local
                    serie_busqueda_baja = mob_ids if es_mob_baja else ion_ids
                    
                    idx_baja = serie_busqueda_baja[serie_busqueda_baja == id_limpio_baja].index[0]
                    equipo_baja = df_actual_baja.loc[idx_baja]
                    
                    estatus_actual_op = str(equipo_baja.get('Estatus operativo', '')).strip().upper()
                    if estatus_actual_op == "NO OPERATIVO":
                        st.warning("⚠️ Este equipo ya se encuentra dado de BAJA (No Operativo).")
                    
                    st.markdown("### Verificación del Equipo")
                    col1_b, col2_b, col3_b = st.columns(3)
                    col1_b.metric("Ubicación", str(equipo_baja.get('Línea', 'N/A')))
                    col2_b.metric("Tipo (Clasificación)", str(equipo_baja.get('Clasificación', 'N/A')))
                    col3_b.metric("Base de Datos", hoja_activa_baja)

                    with st.form("form_confirmacion_baja"):
                        if st.form_submit_button("🗑️ Confirmar Baja (Soft Delete)"):
                            with st.spinner("Actualizando estatus en el servidor..."):
                                import gspread
                                sec = dict(st.secrets["connections"]["gsheets"])
                                gc_gspread = gspread.service_account_from_dict(sec)
                                ws_baja = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet(hoja_activa_baja)
                                
                                try:
                                    id_idx_baja = df_actual_baja.columns.get_loc('Id de producto')
                                    est_op_idx = df_actual_baja.columns.get_loc('Estatus operativo')
                                    est_verif_idx = df_actual_baja.columns.get_loc('Estatus de verificación')
                                except KeyError as e:
                                    st.error(f"Falta columna {e} en Google Sheets.")
                                    st.stop()
                                
                                ids_gsheets_baja = ws_baja.col_values(id_idx_baja + 1)
                                ids_gsheets_limpios_baja = [str(v).strip().upper() for v in ids_gsheets_baja]
                                
                                try:
                                    r_idx_baja = ids_gsheets_limpios_baja.index(id_limpio_baja) + 1
                                except ValueError:
                                    st.error("No se pudo encontrar la fila exacta en el servidor para modificarla.")
                                    st.stop()
                                
                                ws_baja.update_cell(r_idx_baja, est_op_idx + 1, "NO OPERATIVO")
                                ws_baja.update_cell(r_idx_baja, est_verif_idx + 1, "BAJA")
                                
                            st.success(f"✅ ¡Equipo {id_baja_url} desactivado correctamente en {hoja_activa_baja}!")
                            st.cache_data.clear()
                            limpiar_url_escaneo()
                            st.rerun()
                else:
                    st.error(f"❌ El ID '{id_baja_url}' no se encontró en Mobiliario ni en Ionizadores.")

    # ==========================================
    # VISTA 1: MAPA Y REPORTES ESD
    # ==========================================
    elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
        st.markdown("### Mapa y Cumplimiento ESD")
        
        tipo_mapa = st.radio("Selecciona la categoría a visualizar en el mapa:", ["Mobiliario", "Ionizadores"], horizontal=True)
        st.info("☁️ Los datos mostrados están sincronizados en tiempo real con el servidor.")
        
        df_total = df_mob_local.copy() if tipo_mapa == "Mobiliario" else df_ion_local.copy()
        
        if df_total.empty:
            st.warning(f"No hay datos registrados en la base de datos de {tipo_mapa}.")
        elif 'Estatus de verificación' not in df_total.columns:
            st.warning(f"⚠️ La pestaña de {tipo_mapa} no tiene los encabezados correctos.")
        else:
            df_total['Estatus de verificación'] = df_total['Estatus de verificación'].astype(str).str.strip().str.upper()
            if 'Estatus operativo' in df_total.columns:
                df_total['Estatus operativo'] = df_total['Estatus operativo'].astype(str).str.strip().str.upper()
            else:
                df_total['Estatus operativo'] = 'OPERATIVO'

            equipos_activos = df_total[df_total['Estatus operativo'] != 'NO OPERATIVO']
            total_equipos = len(equipos_activos)

            vencidos = equipos_activos[equipos_activos['Estatus de verificación'] == 'VENCIDO']
            total_vencidos = len(vencidos)
            
            if total_equipos > 0:
                porcentaje_cumplimiento = ((total_equipos - total_vencidos) / total_equipos) * 100
            else:
                porcentaje_cumplimiento = 100.0

            if not vencidos.empty:
                st.error(f"🚨 **Cumplimiento {tipo_mapa}:** {porcentaje_cumplimiento:.1f}% | **Equipos Vencidos:** {total_vencidos} de {total_equipos} activos.")
                conteo_tipos = vencidos.groupby(['Línea']).size().reset_index(name='Total Vencidos')
                conteo_tipos['Etiqueta'] = ("M: " if tipo_mapa == "Mobiliario" else "I: ") + conteo_tipos['Total Vencidos'].astype(str)
                
                if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                    img = Image.open(RUTA_MAPA)
                    width, height = img.size
                    df_coords = pd.read_csv(RUTA_COORDENADAS)
                    mapa_data = pd.merge(conteo_tipos, df_coords, on='Línea', how='inner')
                    if not mapa_data.empty:
                        fig = px.scatter(
                            mapa_data, x="X", y="Y", color="Total Vencidos", text="Etiqueta", hover_name="Línea",
                            hover_data={"X": False, "Y": False, "Etiqueta": False, "Total Vencidos": True},
                            color_continuous_scale="Reds"
                        )
                        
                        # --- ICONOS GRANDES ---
                        fig.update_traces(
                            textposition='middle center', 
                            textfont=dict(color='white', size=14, weight='bold'), 
                            marker=dict(symbol='circle', size=45, opacity=0.9, line=dict(width=2, color='black'))
                        )
                        
                        # --- CÁLCULO DE PROPORCIÓN PARA EVITAR APLASTAMIENTO ---
                        aspect_ratio = height / width
                        plot_height = max(500, int(1200 * aspect_ratio))
                        
                        fig.update_layout(
                            height=plot_height,
                            images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")], 
                            xaxis=dict(visible=False, range=[0, width]), 
                            yaxis=dict(visible=False, range=[height, 0], scaleanchor="x"), 
                            margin=dict(l=0, r=0, t=0, b=0),
                            coloraxis_showscale=False
                        )
                        st.plotly_chart(fig, use_container_width=True)
                st.dataframe(vencidos[['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación']], use_container_width=True, hide_index=True)
            else:
                st.success(f"✅ **¡Felicidades! 100% de Cumplimiento en {tipo_mapa}.** No hay equipos operativos VENCIDOS (0 de {total_equipos} activos).")

    # ==========================================
    # VISTA 2: ESCÁNER Y DETALLES
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        
        if not id_escaneado_url:
            st.markdown("### 📷 Apunta al Código QR")
            html_code_qr = """
            <script src="https://unpkg.com/html5-qrcode"></script>
            <div id="reader_main" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0052cc; background-color: #f9f9f9;"></div>
            
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px; flex-wrap:wrap;">
                <button type="button" id="cam_wide_main" style="padding:10px; background:#28a745; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">📸 LENTE ESTÁNDAR</button>
                <button type="button" id="cam_cycle_main" style="padding:10px; background:#555; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔄 OTRA CÁMARA</button>
            </div>
            <div style="text-align:center; margin-top:10px; display:flex; justify-content:center; gap:5px;">
                <button type="button" id="zoom_1x_main" style="padding:10px 20px; background:#0052cc; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 1X (NORMAL)</button>
                <button type="button" id="zoom_3x_main" style="padding:10px 20px; background:#666; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">🔍 3X (CURVO)</button>
            </div>
            <p id="cam-status-main" style="text-align:center; color:#666; font-size: 14px; margin-top: 10px;">Buscando cámaras...</p>
            
            <script>
            let html5QrCodeMain;
            let rearCamsMain = [];
            let currentIdxMain = 0;
            let wideIdMain = null;

            function applyZoomMain(scale) {
                const vid = document.querySelector("#reader_main video");
                if (vid) {
                    vid.style.transform = `scale(${scale})`;
                    vid.style.transformOrigin = "center center";
                }
                document.getElementById('zoom_1x_main').style.background = (scale === 1) ? "#0052cc" : "#666";
                document.getElementById('zoom_3x_main').style.background = (scale === 3) ? "#0052cc" : "#666";
            }

            function startScannerMain(camId) {
                if(!html5QrCodeMain) html5QrCodeMain = new Html5Qrcode("reader_main");
                if (html5QrCodeMain.isScanning) {
                    html5QrCodeMain.stop().then(() => { runScanMain(camId); }).catch(e => console.log(e));
                } else {
                    runScanMain(camId);
                }
            }

            function runScanMain(camId) {
                html5QrCodeMain.start(
                    camId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    (decodedText) => {
                        html5QrCodeMain.stop();
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set("qr_id", decodedText);
                        window.parent.history.replaceState({}, "", url);
                        window.parent.location.reload();
                    }, (err) => {} 
                ).then(() => { 
                    let activeCam = rearCamsMain.find(c => c.id === camId);
                    document.getElementById("cam-status-main").innerText = "Lente activo: " + (activeCam ? activeCam.label : "Cámara");
                    applyZoomMain(1);
                }).catch(err => {
                    document.getElementById("cam-status-main").innerText = "Error iniciando lente. Intenta 'Otra Cámara'.";
                });
            }

            Html5Qrcode.getCameras().then(devices => {
                if (devices && devices.length) {
                    rearCamsMain = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera') || c.label.toLowerCase().includes('environment'));
                    if(rearCamsMain.length === 0) rearCamsMain = devices;

                    // Buscar la cámara WIDE original
                    wideIdMain = rearCamsMain[0].id;
                    for (let c of rearCamsMain) {
                        let lbl = c.label.toLowerCase();
                        if (lbl.includes('wide') && !lbl.includes('ultra')) {
                            wideIdMain = c.id; break;
                        }
                    }

                    currentIdxMain = rearCamsMain.findIndex(c => c.id === wideIdMain);
                    if(currentIdxMain === -1) currentIdxMain = 0;

                    startScannerMain(wideIdMain);

                    document.getElementById('cam_wide_main').addEventListener('click', () => {
                        currentIdxMain = rearCamsMain.findIndex(c => c.id === wideIdMain);
                        startScannerMain(wideIdMain);
                    });

                    document.getElementById('cam_cycle_main').addEventListener('click', () => {
                        currentIdxMain = (currentIdxMain + 1) % rearCamsMain.length;
                        startScannerMain(rearCamsMain[currentIdxMain].id);
                    });

                    document.getElementById('zoom_1x_main').addEventListener('click', () => applyZoomMain(1));
                    document.getElementById('zoom_3x_main').addEventListener('click', () => applyZoomMain(3));
                }
            }).catch(err => { document.getElementById("cam-status-main").innerText = "Permisos de cámara denegados."; });
            </script>
            """
            components.html(html_code_qr, height=750) 
            
            id_manual = st.text_input("O ingresa el ID manual:", key="input_manual")
            if id_manual:
                st.query_params["qr_id"] = id_manual
                st.rerun()

        if id_escaneado_url:
            colA, colB = st.columns([0.8, 0.2])
            with colA:
                st.info(f"🔍 **ID Detectado:** {id_escaneado_url}")
            with colB:
                if st.button("❌ Cerrar Escaneo"):
                    limpiar_url_escaneo()
                    st.rerun()

            id_limpio = str(id_escaneado_url).strip().upper()
            
            mob_ids_limpios = df_mob_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()
            ion_ids_limpios = df_ion_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()

            es_mob = id_limpio in mob_ids_limpios.values
            es_ion = id_limpio in ion_ids_limpios.values

            if es_mob or es_ion:
                hoja_activa = "MOBILIARIO" if es_mob else "IONIZADORES"
                df_actual = df_mob_local if es_mob else df_ion_local
                serie_busqueda = mob_ids_limpios if es_mob else ion_ids_limpios
                
                idx = serie_busqueda[serie_busqueda == id_limpio].index[0]
                equipo = df_actual.loc[idx]
                
                estatus_actual_op = str(equipo.get('Estatus operativo', '')).strip().upper()
                
                # --- REACTIVACIÓN LÓGICA DE INTERFAZ ---
                if estatus_actual_op == "NO OPERATIVO":
                    st.warning("⚠️ EQUIPO DADO DE BAJA. Al ingresar una nueva medición, el equipo se REACTIVARÁ automáticamente.")
                    texto_checkbox = "✅ REACTIVAR equipo y registrar nueva medición"
                else:
                    texto_checkbox = "✅ Realizar nueva medición y actualizar"
                
                st.markdown(f"### 📊 Detalles del Equipo ({hoja_activa})")
                
                c_linea, c_tipo, c_estatus = st.columns(3)
                c_linea.metric("Ubicación (Línea)", str(equipo.get('Línea', 'N/A')))
                c_tipo.metric("Tipo (Clasificación)", str(equipo.get('Clasificación', 'N/A')))
                
                estatus_actual = str(equipo.get('Estatus de verificación', 'N/A')).strip().upper()
                color_estatus = "🟢" if estatus_actual == "VIGENTE" else "🔴"
                c_estatus.metric("Estatus Actual", f"{color_estatus} {estatus_actual}")
                
                c_fecha_ult, c_fecha_prox, c_val = st.columns(3)
                
                fecha_ult_str = str(equipo.get('Fecha de verificación', 'N/A')).strip()
                fecha_prox_str = str(equipo.get('Fecha de próxima verificación', 'N/A')).strip()
                
                c_fecha_ult.metric("Última Medición", fecha_ult_str)
                c_fecha_prox.metric("Próxima Medición", fecha_prox_str)
                
                val_previo = equipo.get('Valor de verificación', 0)
                
                if es_ion:
                    if pd.notna(val_previo) and val_previo != 0 and str(val_previo).strip() != '':
                        try: c_val.metric("Tiempo de Descarga", f"{float(val_previo):.2f} s")
                        except ValueError: c_val.metric("Tiempo de Descarga", str(val_previo))
                    else:
                        c_val.metric("Tiempo de Descarga", "N/A")
                        
                    c_bal, _, _ = st.columns(3)
                    bal_previo = equipo.get('Balance', 0)
                    if pd.notna(bal_previo) and str(bal_previo).strip() != '':
                        try: c_bal.metric("Balance Registrado", f"{float(bal_previo):.2f} V")
                        except ValueError: c_bal.metric("Balance Registrado", str(bal_previo))
                    else:
                        c_bal.metric("Balance Registrado", "N/A")
                else:
                    if pd.notna(val_previo) and val_previo != 0 and str(val_previo).strip() != '':
                        try: c_val.metric("Resistencia Registrada", f"{float(val_previo):.2E} Ω")
                        except ValueError: c_val.metric("Resistencia Registrada", str(val_previo))
                    else:
                        c_val.metric("Resistencia Registrada", "N/A")
                
                limite_raw = equipo.get('Maximo', 'N/A')
                if pd.notna(limite_raw) and str(limite_raw).strip() != 'N/A' and str(limite_raw).strip() != '':
                    try:
                        limite_str = f"{float(limite_raw):.2f} V/s" if es_ion else f"{float(limite_raw):.2E} Ω"
                    except ValueError:
                        limite_str = str(limite_raw)
                else:
                    limite_str = "N/A"
                    
                st.markdown(f"**Límite S20.20-2021 Permitido:** {limite_str}")
                st.divider()

                if st.session_state.modo_lectura:
                    st.warning("👁️ **Estás en Modo Consulta.** No tienes permisos para actualizar los registros.")
                else:
                    hacer_medicion = st.checkbox(texto_checkbox, value=bool(valor_ocr_detectado))
                    
                    if hacer_medicion:
                        with st.form("form_actualizacion"):
                            # --- SELECCIÓN DE LÍNEA ---
                            todas_lineas_escaner = set()
                            for df_temp in [df_piso_local, df_mob_local, df_ion_local]:
                                if df_temp is not None and 'Línea' in df_temp.columns:
                                    todas_lineas_escaner.update([str(x).strip() for x in df_temp['Línea'].dropna() if str(x).strip() != ''])
                            lineas_disponibles_escaner = sorted(list(todas_lineas_escaner))
                            
                            linea_actual = str(equipo.get('Línea', '')).strip()
                            idx_linea_def = lineas_disponibles_escaner.index(linea_actual) if linea_actual in lineas_disponibles_escaner else 0
                            
                            nueva_linea_upd = st.selectbox("Línea / Ubicación (Modificar si el equipo fue reubicado)", options=lineas_disponibles_escaner, index=idx_linea_def)
                            
                            if es_ion:
                                st.markdown("#### Captura de Mediciones Ionizador")
                                c_form1, c_form2 = st.columns(2)
    
                                v_act = c_form1.number_input("Tiempo de Descarga (Segundos)", value=None, format="%.2f", placeholder="0.00")
                                v_act = v_act if v_act is not None else 0.0
    
                                bal_def = equipo.get('Balance', 0.0)
                                try: bal_def = float(bal_def)
                                except: bal_def = 0.0
    
                                # Usamos el bal_def como placeholder para que el usuario sepa cuál era el anterior
                                nuevo_balance = c_form2.number_input("Balance (V)", value=None, format="%.2f", placeholder=str(bal_def))
                                # Si lo dejan en blanco, conservamos el balance anterior
                                nuevo_balance = nuevo_balance if nuevo_balance is not None else bal_def
                            else:
                                st.caption("Resistencia (Ohms)")
                                def_val = float(valor_ocr_detectado) if valor_ocr_detectado else 0.0
    
                                def_base = 0.0
                                def_exp = 0
                                if def_val != 0:
                                    def_exp = int(math.floor(math.log10(abs(def_val))))
                                    def_base = def_val / (10 ** def_exp)
    
                                c_b, c_x, c_e = st.columns([2, 1, 2])
                                base_upd = c_b.number_input("Número", value=None, format="%.2f", placeholder=f"{def_base:.2f}")
                                c_x.markdown("<div style='text-align: center; margin-top: 30px; font-weight: bold; font-size: 18px;'>x 10^</div>", unsafe_allow_html=True)
                                exp_upd = c_e.number_input("Exponente", value=None, step=1, format="%d", placeholder=str(def_exp))
    
                                # Si se dejan en blanco, mantenemos el valor extraído del OCR o del historial
                                base_upd = base_upd if base_upd is not None else def_base
                                exp_upd = exp_upd if exp_upd is not None else def_exp
                                nuevo_valor_final = base_upd * (10 ** exp_upd) if base_upd != 0 else 0.0
                                
                            fecha_hoy = datetime.today().date()
                            nueva_fecha_valida = st.date_input("Fecha de medición", fecha_hoy)
                            
                            texto_boton_submit = "Reactivar y Guardar" if estatus_actual_op == "NO OPERATIVO" else "Guardar en servidor"
                            if st.form_submit_button(texto_boton_submit):
                                with st.spinner("Guardando en base de datos y archivo histórico..."):
                                    if es_ion:
                                        nuevo_valor_final = v_act

                                    freq = str(equipo.get('Frecuencia de verificación', 'Anual'))
                                    proxy = calcular_proxima_fecha(nueva_fecha_valida, freq)
                                    
                                    import gspread
                                    sec = dict(st.secrets["connections"]["gsheets"])
                                    gc_gspread = gspread.service_account_from_dict(sec)
                                    
                                    if pd.notna(val_previo) and str(val_previo).strip() != '':
                                        try:
                                            ws_hist = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet("HISTORIAL")
                                            fila_historial = [
                                                id_limpio,                                  
                                                hoja_activa,                                
                                                equipo.get('Línea', ''),                    
                                                str(val_previo),                            
                                                str(equipo.get('Balance', '')),             
                                                str(equipo.get('Fecha de verificación', '')),
                                                str(equipo.get('Auditor', '')),             
                                                datetime.now().strftime("%d-%b-%Y %H:%M")   
                                            ]
                                            ws_hist.append_row(fila_historial, value_input_option="USER_ENTERED")
                                        except Exception as e:
                                            pass

                                    ws = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet(hoja_activa)
                                    
                                    try:
                                        id_idx = df_actual.columns.get_loc('Id de producto')
                                        linea_idx = df_actual.columns.get_loc('Línea')
                                        val_idx = df_actual.columns.get_loc('Valor de verificación')
                                        f_idx = df_actual.columns.get_loc('Fecha de verificación')
                                        fp_idx = df_actual.columns.get_loc('Fecha de próxima verificación')
                                        st_idx = df_actual.columns.get_loc('Estatus de verificación')
                                        aud_idx = df_actual.columns.get_loc('Auditor') 
                                    except KeyError as e:
                                        st.error(f"Falta columna {e}")
                                        st.stop()
                                    
                                    ids_gsheets = ws.col_values(id_idx + 1)
                                    ids_gsheets_limpios = [str(v).strip().upper() for v in ids_gsheets]
                                    
                                    try:
                                        r_idx = ids_gsheets_limpios.index(id_limpio) + 1
                                    except ValueError:
                                        st.error("No se pudo encontrar el campo en servidor para actualizar.")
                                        st.stop()
                                    
                                    ws.update_cell(r_idx, linea_idx + 1, nueva_linea_upd)
                                    ws.update_cell(r_idx, val_idx + 1, float(nuevo_valor_final))
                                    ws.update_cell(r_idx, f_idx + 1, nueva_fecha_valida.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, fp_idx + 1, proxy.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, st_idx + 1, 'VIGENTE')
                                    
                                    # --- EJECUCIÓN LÓGICA REACTIVACIÓN ---
                                    if estatus_actual_op == "NO OPERATIVO":
                                        try:
                                            est_op_idx = df_actual.columns.get_loc('Estatus operativo')
                                            ws.update_cell(r_idx, est_op_idx + 1, "OPERATIVO")
                                        except Exception:
                                            pass
                                    
                                    try:
                                        ws.update_cell(r_idx, aud_idx + 1, st.session_state.usuario_nombre)
                                    except:
                                        ws.update_cell(r_idx, 18, st.session_state.usuario_nombre)
                                        
                                    if es_ion:
                                        try:
                                            bal_idx = df_actual.columns.get_loc('Balance')
                                            ws.update_cell(r_idx, bal_idx + 1, float(nuevo_balance))
                                        except KeyError:
                                            ws.update_cell(r_idx, 19, float(nuevo_balance))

                                st.success("💾 ¡Guardado correctamente con trazabilidad histórica!")
                                st.cache_data.clear()
                                limpiar_url_escaneo()
                                st.rerun()
            else:
                st.error(f"❌ El ID '{id_escaneado_url}' no se encontró en la base de datos.")
# ==========================================
    # VISTA 3: EVENT METER
    # ==========================================
    elif st.session_state.vista_actual == "Event Meter" and not st.session_state.modo_lectura:
        st.markdown("### ⚡ Estudio de Event Meter (PCBA)")
        st.info("Mide descargas electrostáticas y transitorios durante la operación normal de la maquinaria/proceso.")

        # --- SECCIÓN: GENERADOR DE REPORTE ANSI/ESD S20.20 ---
        with st.expander("📄 Generar Reporte Oficial ANSI/ESD S20.20", expanded=False):
            st.write("Genera el formato pre-llenado listo para imprimir en PDF con los registros actuales de tu base de datos.")
            
            lineas_reporte = ["Todas"]
            if df_em_local is not None and 'Línea' in df_em_local.columns:
                lineas_reporte += sorted([str(x).strip() for x in df_em_local['Línea'].dropna().unique() if str(x).strip() != ''])
            
            linea_reporte = st.selectbox("Seleccionar Línea para el Reporte", options=lineas_reporte)
            
            if st.button("Generar Reporte HTML", use_container_width=True):
                html_rows = ""
                if df_em_local is not None and not df_em_local.empty:
                    df_rep = df_em_local.copy()
                    if linea_reporte != "Todas":
                        df_rep = df_rep[df_rep['Línea'].astype(str).str.strip() == linea_reporte]
                    
                    # Convertimos a numérico y ordenamos descendente por cantidad de eventos
                    col_eventos = 'Detección (Cantidad)' if 'Detección (Cantidad)' in df_rep.columns else 'Detección'
                    df_rep[col_eventos] = pd.to_numeric(df_rep[col_eventos], errors='coerce').fillna(0)
                    df_rep = df_rep.sort_values(by=col_eventos, ascending=False)
                    
                    for i, row in enumerate(df_rep.to_dict('records'), 1):
                        op = str(row.get('Id de Operación', 'N/A'))
                        eventos = int(row.get(col_eventos, 0))
                        
                        # Buscamos la columna de voltaje (soporta variaciones de nombre)
                        vmax = row.get('Voltaje máximo de descarga', row.get('Voltaje máximo', 0.0))
                        
                        estatus = str(row.get('Estatus de verificación', '')).upper()
                        notas = str(row.get('Notas', ''))
                        if notas == "nan": notas = ""
                        
                        color_estatus = "text-green-600" if "APROBADO" in estatus else "text-red-600"
                        pass_fail = "PASA" if "APROBADO" in estatus else "FALLA"
                        
                        html_rows += f"""
                        <tr>
                            <td class="border border-gray-800 p-1 text-center font-bold text-gray-600">{i}</td>
                            <td class="border border-gray-800 p-1">{op}</td>
                            <td class="border border-gray-800 p-1 text-center font-bold">5</td>
                            <td class="border border-gray-800 p-1 text-center">{eventos}</td>
                            <td class="border border-gray-800 p-1 text-center">{vmax}V</td>
                            <td class="border border-gray-800 p-1 text-center font-bold {color_estatus}">{pass_fail}</td>
                            <td class="border border-gray-800 p-1">{notas}</td>
                        </tr>
                        """
                
                if html_rows == "":
                    st.warning("No hay registros guardados para esta línea.")
                else:
                    fecha_hoy_str = datetime.today().strftime("%Y-%m-%d")
                    auditor_name = st.session_state.usuario_nombre if st.session_state.usuario_nombre else ""
                    
                    html_template = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Event Meter - {{LINEA}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @media print {
            body { background-color: white; padding: 0; }
            .no-print { display: none !important; }
            .print-border { border: 1px solid #000; }
            .shadow-lg { box-shadow: none; }
            input, textarea { border: none !important; resize: none; background: transparent; }
            input::placeholder, textarea::placeholder { color: transparent; }
        }
        input, textarea {
            width: 100%; background-color: #f9fafb; border: 1px solid #e5e7eb;
            border-radius: 0.25rem; padding: 0.25rem 0.5rem; font-size: 0.875rem;
        }
    </style>
</head>
<body class="bg-gray-100 p-4 md:p-8 text-gray-800 font-sans">
    <div class="max-w-5xl mx-auto bg-white p-8 shadow-lg print:shadow-none print:p-0">
        <div class="flex justify-end space-x-4 mb-6 no-print">
            <button onclick="window.print()" class="bg-gray-800 text-white px-4 py-2 rounded shadow hover:bg-gray-900 transition flex items-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"></path></svg>
                Imprimir / Guardar PDF
            </button>
        </div>
        <div class="border-2 border-gray-800 mb-6 flex flex-col md:flex-row text-sm print-border">
            <div class="p-4 border-b-2 md:border-b-0 md:border-r-2 border-gray-800 flex items-center justify-center w-full md:w-1/4">
                <img src="https://github.com/aldoaoa/Visualizador-BCS-IDS/blob/main/BCS%20LOGO.png?raw=true" alt="Logo BCS" class="max-h-20 object-contain">
            </div>
            <div class="p-4 flex-1 border-b-2 md:border-b-0 md:border-r-2 border-gray-800 text-center flex flex-col justify-center">
                <h1 class="text-lg font-bold uppercase">Registro de Estudio de Eventos ESD (Event Meter)</h1>
                <p class="text-gray-600 font-semibold">Norma de Referencia: ANSI/ESD S20.20</p>
            </div>
            <div class="p-2 w-full md:w-1/4 flex flex-col justify-center text-xs space-y-1">
                <div class="flex justify-between"><span class="font-bold">Código:</span> <span>F-ESD-001</span></div>
                <div class="flex justify-between"><span class="font-bold">Límite Permitido:</span> <span class="font-bold text-red-600">< 100V</span></div>
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 text-sm">
            <div class="space-y-2">
                <div class="flex items-center"><label class="w-32 font-bold">Fecha:</label> <input type="date" value="{{FECHA}}"></div>
                <div class="flex items-center"><label class="w-32 font-bold">Línea/Área:</label> <input type="text" value="{{LINEA}}"></div>
                <div class="flex items-center"><label class="w-32 font-bold">Auditor:</label> <input type="text" value="{{AUDITOR}}"></div>
            </div>
            <div class="space-y-2">
                <div class="flex items-center"><label class="w-40 font-bold">Equipo Utilizado:</label> <input type="text" value="SCS EM EYE" readonly></div>
                <div class="flex items-center"><label class="w-40 font-bold">No. de Serie:</label> <input type="text" value="2451005" readonly></div>
            </div>
        </div>
        <div class="overflow-x-auto mb-8">
            <table class="w-full text-sm border-collapse border border-gray-800 print-border">
                <thead>
                    <tr class="bg-gray-200">
                        <th class="border border-gray-800 p-2 text-center w-10">No.</th>
                        <th class="border border-gray-800 p-2 text-left">Operación / Estación</th>
                        <th class="border border-gray-800 p-2 text-center w-24">Tiempo (m)</th>
                        <th class="border border-gray-800 p-2 text-center w-24">Eventos</th>
                        <th class="border border-gray-800 p-2 text-center w-24">Voltaje Máx.</th>
                        <th class="border border-gray-800 p-2 text-center w-24">Resultado</th>
                        <th class="border border-gray-800 p-2 text-left">Observaciones</th>
                    </tr>
                </thead>
                <tbody>
                    {{ROWS}}
                </tbody>
            </table>
        </div>
        <div class="grid grid-cols-2 gap-8 mt-12 text-sm text-center">
            <div><div class="border-b border-gray-800 w-3/4 mx-auto mb-2 h-8"></div><p class="font-bold">Realizado por</p></div>
            <div><div class="border-b border-gray-800 w-3/4 mx-auto mb-2 h-8"></div><p class="font-bold">Revisado / Aprobado por</p></div>
        </div>
    </div>
</body>
</html>"""
                    html_template = html_template.replace("{{FECHA}}", fecha_hoy_str)
                    html_template = html_template.replace("{{LINEA}}", linea_reporte)
                    html_template = html_template.replace("{{AUDITOR}}", auditor_name)
                    html_template = html_template.replace("{{ROWS}}", html_rows)

                    b64_html = base64.b64encode(html_template.encode('utf-8')).decode('utf-8')
                    nombre_archivo = f"Reporte_EventMeter_{linea_reporte.replace(' ', '_')}.html"
                    
                    st.success("✅ Formato generado correctamente.")
                    href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-top: 10px;">📥 Descargar Reporte (Abre el archivo para Imprimir/Guardar PDF)</a>'
                    st.markdown(href, unsafe_allow_html=True)

        # --- SECCIÓN DEL TEMPORIZADOR ---
        modo_tiempo = st.radio("Temporizador de Estudio (5 minutos)", ["⏱️ Usar Cronómetro Integrado", "⏭️ Omitir (Ya cronometrado)"], horizontal=True)

        if modo_tiempo == "⏱️ Usar Cronómetro Integrado":
            # Temporizador en HTML/JS para no bloquear Streamlit
            html_timer = """
            <div style="text-align:center; padding: 15px; border: 2px dashed #0052cc; border-radius: 10px; background-color: #f0f7ff;">
                <div id="timer_display" style="font-size: 50px; font-weight: bold; font-family: monospace; color: #0052cc; margin-bottom: 10px;">05:00</div>
                <button onclick="startTimer()" style="padding: 10px 20px; font-size: 16px; font-weight:bold; cursor: pointer; background-color: #28a745; color: white; border: none; border-radius: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">▶ Iniciar</button>
                <button onclick="stopTimer()" style="padding: 10px 20px; font-size: 16px; font-weight:bold; cursor: pointer; background-color: #dc3545; color: white; border: none; border-radius: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-left: 10px;">⏹ Detener / Reset</button>
            </div>
            <script>
                let timeLeft = 300; // 5 minutos en segundos
                let timerId = null;

                function updateDisplay() {
                    let m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
                    let s = (timeLeft % 60).toString().padStart(2, '0');
                    let display = document.getElementById('timer_display');
                    display.innerText = m + ":" + s;
                    
                    if (timeLeft <= 0) {
                        display.style.color = "#dc3545";
                        display.innerText = "¡TIEMPO TERMINADO!";
                        clearInterval(timerId);
                        timerId = null;
                    } else if (timeLeft <= 60) {
                        display.style.color = "#ffc107"; // Advertencia en el último minuto
                    } else {
                        display.style.color = "#0052cc";
                    }
                }

                function startTimer() {
                    if (!timerId && timeLeft > 0) {
                        timerId = setInterval(() => {
                            timeLeft--;
                            updateDisplay();
                        }, 1000);
                    }
                }

                function stopTimer() {
                    clearInterval(timerId);
                    timerId = null;
                    timeLeft = 300; // Resetear
                    updateDisplay();
                }
            </script>
            """
            components.html(html_timer, height=200)

        st.divider()

        # --- FORMULARIO DE CAPTURA ---
        st.divider()
        st.markdown("#### 📍 Ubicación y Operación")
        c_loc1, c_loc2 = st.columns(2)

        # --- LÓGICA DINÁMICA DE SELECCIÓN (AFUERA DEL FORM) ---
        lineas_existentes = []
        if df_em_local is not None and 'Línea' in df_em_local.columns:
            lineas_existentes = sorted([str(x).strip() for x in df_em_local['Línea'].dropna().unique() if str(x).strip() != ''])
        
        if not lineas_existentes:
            lineas_existentes = ["Sin registros"]

        linea_seleccionada = c_loc1.selectbox("Línea", options=lineas_existentes)
        
        # Checkbox para capturar opciones nuevas
        nueva_op_check = c_loc2.checkbox("➕ Registrar nueva Operación o Línea")

        if nueva_op_check:
            linea_final = c_loc1.text_input("Ingresa Nueva Línea", value=linea_seleccionada if linea_seleccionada != "Sin registros" else "")
            id_operacion_final = c_loc2.text_input("Ingresa Nuevo ID de Operación (Ej: OP50-AUDIO)")
        else:
            linea_final = linea_seleccionada
            ops_existentes = []
            if df_em_local is not None and 'Id de Operación' in df_em_local.columns and 'Línea' in df_em_local.columns:
                # Filtramos las operaciones correspondientes a la línea seleccionada
                ops_filtradas = df_em_local[df_em_local['Línea'].astype(str).str.strip() == linea_seleccionada]
                ops_existentes = sorted([str(x).strip() for x in ops_filtradas['Id de Operación'].dropna().unique() if str(x).strip() != ''])
            
            if not ops_existentes:
                id_operacion_final = c_loc2.selectbox("ID de Operación", options=["(Sin operaciones previas)"])
            else:
                id_operacion_final = c_loc2.selectbox("Selecciona ID de Operación", options=ops_existentes)

        # --- FORMULARIO DE CAPTURA (Mediciones) ---
        with st.form("form_event_meter_captura"):
            col1, col2 = st.columns(2)
            
            tipo_contacto = col1.selectbox("Tipo de contacto", options=["Maquinaria", "EOLT", "AOI", "Herramienta Manual", "Humano", "Otro"])
            if tipo_contacto == "Otro":
                tipo_contacto = col1.text_input("Especifique Tipo de Contacto")

            st.markdown("#### ⚡ Resultados de Detección")
            col_d1, col_d2 = st.columns(2)
            
            deteccion_eventos = col_d1.number_input("Cantidad de Eventos Detectados", min_value=0, step=1, value=None, placeholder="0")
            deteccion_eventos = deteccion_eventos if deteccion_eventos is not None else 0
            
            voltaje_max = col_d2.number_input("Voltaje máximo de descarga (V)", min_value=0.0, max_value=999.0, step=0.1, value=None, placeholder="0.0")
            voltaje_max = voltaje_max if voltaje_max is not None else 0.0

            notas_em = st.text_area("Notas / Observaciones")

            limite_maximo_v = 100.0  
            estatus_verificacion = "APROBADO" if voltaje_max <= limite_maximo_v else "RECHAZADO"
            fecha_hoy = datetime.today().date()
            frecuencia_em = "Semestral" 
            proxima_fecha = calcular_proxima_fecha(fecha_hoy, frecuencia_em)

            submit_em = st.form_submit_button("💾 Guardar Registro de Event Meter", use_container_width=True)

            if submit_em:
                if not id_operacion_final or id_operacion_final == "(Sin operaciones previas)":
                    st.error("⚠️ Debes proporcionar un ID de Operación válido.")
                else:
                    with st.spinner("Guardando en la hoja EVENT_METER..."):
                        import gspread
                        sec = dict(st.secrets["connections"]["gsheets"])
                        gc_em = gspread.service_account_from_dict(sec)
                        
                        try:
                            ws_em = gc_em.open_by_url(sec["spreadsheet"]).worksheet("EVENT_METER")
                        except gspread.exceptions.WorksheetNotFound:
                            st.error("❌ No se encontró la pestaña 'EVENT_METER'.")
                            st.stop()
                        
                        fila_em = [
                            linea_final,                                    # Línea
                            id_operacion_final.upper(),                     # Id de Operación
                            tipo_contacto,                                  # Tipo de contacto
                            int(deteccion_eventos),                         # Detección (Cantidad)
                            float(voltaje_max) if deteccion_eventos > 0 else 0.0, # Voltaje máximo
                            st.session_state.usuario_nombre,                # Auditor
                            limite_maximo_v,                                # Maximo
                            "Volts",                                        # Unidad de aceptabilidad
                            "Event Meter",                                  # Método
                            fecha_hoy.strftime("%d-%b-%Y"),                 # Fecha de verificación
                            proxima_fecha.strftime("%d-%b-%Y"),             # Fecha de próxima verificación
                            frecuencia_em,                                  # Frecuencia de verificación
                            estatus_verificacion,                           # Estatus de verificación
                            "OPERATIVO",                                    # Estatus operativo
                            notas_em                                        # Notas
                        ]
                        
                        ws_em.append_row(fila_em, value_input_option="USER_ENTERED")
                        
                    st.success(f"✅ ¡Estudio de {id_operacion_final} registrado exitosamente! Estatus: {estatus_verificacion}")
                    st.cache_data.clear() # Limpiamos la caché para que la nueva operación aparezca en la lista inmediatamente
                    st.balloons()

# ... existing code ...
# ==========================================
    # VISTA 4: WALKING TEST
    # ==========================================
    elif st.session_state.vista_actual == "Walking Test" and not st.session_state.modo_lectura:
        st.markdown("### 🚶‍♂️ Análisis de Walking Test")
        st.info("Sube uno o varios archivos PDF generados por el equipo de medición para extraer los datos automáticamente vía OCR y generar un reporte consolidado.")

        archivos_pdf = st.file_uploader("Selecciona los archivos PDF", type=["pdf"], accept_multiple_files=True)

        if archivos_pdf:
            st.markdown("#### Resultados Extraídos")
            
            # Lista para guardar los datos de todas las ubicaciones y armar el reporte final
            datos_extraidos_wt = [] 
            
            for archivo in archivos_pdf:
                with st.expander(f"📄 Reporte: {archivo.name}", expanded=True):
                    try:
                        # 1. Leer el PDF con PyMuPDF
                        doc = fitz.open(stream=archivo.read(), filetype="pdf")
                        pagina = doc[0] 

                        imagen_grafica = None
                        texto_ocr = ""
                        img_b64 = "" # Inicializamos la variable para el reporte HTML

                        # 2. Extraer la imagen principal del PDF
                        imagenes_pdf = pagina.get_images(full=True)
                        if imagenes_pdf:
                            xref = imagenes_pdf[0][0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            imagen_grafica = Image.open(io.BytesIO(image_bytes))

                            # 3. Aplicar OCR a la imagen extraída
                            with st.spinner("Analizando imagen con OCR..."):
                                texto_ocr = pytesseract.image_to_string(imagen_grafica)
                            
                            # Convertir imagen a Base64 para incrustar en el reporte HTML final
                            buffered = io.BytesIO()
                            imagen_grafica.save(buffered, format="PNG")
                            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                        else:
                            st.warning("No se detectó ninguna imagen/gráfica en este PDF para analizar.")
                            continue

                        # 4. EXTRACCIÓN DE DATOS DESDE EL TEXTO OCR
                        fecha_hora_match = re.search(r"(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})", texto_ocr)
                        fecha = fecha_hora_match.group(1) if fecha_hora_match else "N/D"
                        hora = fecha_hora_match.group(2) if fecha_hora_match else "N/D"

                        hum_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%?\s*RH", texto_ocr, re.IGNORECASE)
                        humedad = f"{hum_match.group(1)} %" if hum_match else "N/D"

                        temp_match = re.search(r"(\d{1,3}(?:\.\d+)?)\s*[^C]*C", texto_ocr, re.IGNORECASE)
                        temperatura = f"{temp_match.group(1)} °C" if temp_match else "N/D"

                        peaks_match = re.search(r"highest peaks:\s*(.*?)(?:\(|Arithmetic|\n|$)", texto_ocr, re.IGNORECASE)
                        picos = peaks_match.group(1).strip() if peaks_match else "N/D"

                        valleys_match = re.search(r"highest valleys:\s*(.*?)(?:\(|Arithmetic|\n|$)", texto_ocr, re.IGNORECASE)
                        valles = valleys_match.group(1).strip() if valleys_match else "N/D"

                        # --- PROCESAMIENTO MATEMÁTICO (MÁXIMO ABSOLUTO Y PROMEDIO DE PICOS) ---
                        max_abs = 0.0
                        promedio_picos = 0.0
                        try:
                            # Extraer todos los números flotantes de las cadenas de picos y valles
                            p_vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", picos)]
                            v_vals = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", valles)]
                            
                            todos_los_valores = p_vals + v_vals
                            if todos_los_valores:
                                # Buscamos la magnitud máxima sin importar el signo (Voltaje máximo absoluto)
                                max_abs = max(abs(x) for x in todos_los_valores)
                                
                            if p_vals:
                                # Promedio de los picos
                                promedio_picos = sum(p_vals) / len(p_vals)
                        except:
                            pass

                        # --- RENDERIZADO EN PANTALLA ---
                        col_datos1, col_datos2 = st.columns(2)
                        
                        with col_datos1:
                            st.metric("📅 Fecha", fecha)
                            st.metric("🌡️ Temperatura", temperatura)
                            st.metric("⚡ Voltaje Máx (Absoluto)", f"{max_abs:.2f} V")
                            
                        with col_datos2:
                            st.metric("🕒 Hora", hora)
                            st.metric("💧 Humedad", humedad)
                            st.metric("📊 Promedio Picos", f"{promedio_picos:.2f} V")

                        st.divider()
                        st.markdown("**Gráfica Extraída:**")
                        st.image(imagen_grafica, use_container_width=True)

                        # Guardamos los datos actualizados para el reporte final consolidado
                        datos_extraidos_wt.append({
                            "archivo": archivo.name,
                            "fecha": fecha,
                            "temp": temperatura,
                            "hum": humedad,
                            "max_abs": max_abs,
                            "promedio_picos": promedio_picos,
                            "img_b64": img_b64
                        })

                    except Exception as e:
                        st.error(f"Ocurrió un error al procesar el archivo {archivo.name}: {e}")

            # --- SECCIÓN: GENERADOR DE REPORTE CONSOLIDADO ---
            if datos_extraidos_wt:
                st.divider()
                st.markdown("### 📄 Generar Reporte Oficial Consolidado")
                st.write("Completa la información general para generar un solo reporte con todas las ubicaciones procesadas.")
                
                fecha_defecto = datos_extraidos_wt[0]['fecha'] if datos_extraidos_wt[0]['fecha'] != "N/D" else datetime.today().strftime("%d/%m/%Y")
                temp_defecto = datos_extraidos_wt[0]['temp']
                hum_defecto = datos_extraidos_wt[0]['hum']
                
                with st.form("form_reporte_wt"):
                    st.markdown("#### Datos Generales")
                    col_g1, col_g2, col_g3 = st.columns(3)
                    auditor_wt = col_g1.text_input("Auditor / Técnico", value=st.session_state.usuario_nombre if st.session_state.usuario_nombre else "")
                    operador_wt = col_g2.text_input("Operador de Prueba")
                    periodo_wt = col_g3.selectbox("Periodo de Evaluación", ["Semestre 1", "Semestre 2"])
                    
                    col_g4, col_g5 = st.columns(2)
                    equipo_wt = col_g4.text_input("Equipo de Medición Utilizado", value="DESCO 46006")
                    calzado_wt = col_g5.text_input("Calzado ESD Utilizado", value="Zapato antiestático Workman")
                    
                    st.markdown("#### 🌡️ Condiciones Ambientales (Edítalas si es necesario)")
                    col_amb1, col_amb2, col_amb3 = st.columns(3)
                    fecha_gen = col_amb1.text_input("Fecha de Prueba", value=fecha_defecto)
                    temp_gen = col_amb2.text_input("Temperatura", value=temp_defecto)
                    hum_gen = col_amb3.text_input("Humedad", value=hum_defecto)
                    
                    st.markdown("#### Configuración de Ubicaciones")
                    bloques_ubicaciones = []
                    
                    for i, dato in enumerate(datos_extraidos_wt):
                        st.markdown(f"**Ubicación {i+1} (Archivo: {dato['archivo']})**")
                        c_ub1, c_ub2 = st.columns(2)
                        nombre_ub = c_ub1.text_input(f"Nombre de Línea/Área", value=dato['archivo'].replace(".pdf", ""), key=f"nombre_{i}")
                        tipo_piso = c_ub2.selectbox(f"Tipo de Piso", ["Piso Epóxico ESD", "Loseta Vinílica Conductiva", "Tapete Antifatiga ESD", "Otro"], key=f"piso_{i}")
                        bloques_ubicaciones.append({"nombre": nombre_ub, "piso": tipo_piso, "datos": dato})
                        st.write("") 

                    submit_reporte = st.form_submit_button("Generar Reporte Consolidado en PDF/HTML", use_container_width=True)
                    
                    if submit_reporte:
                        html_ubicaciones = ""
                        for idx, block in enumerate(bloques_ubicaciones, 1):
                            data = block['datos']
                            
                            # Lógica de aprobación actualizada (Límite S20.20 es < 100V de magnitud máxima)
                            if data['max_abs'] < 100:
                                res_class = "result-pass"
                                res_text = "CUMPLE (PASS)"
                                res_color = "green"
                                obs = "Ninguna anomalía. Los picos se mantuvieron por debajo del límite de 100V."
                            else:
                                res_class = "result-fail"
                                res_text = "NO CUMPLE (FAIL)"
                                res_color = "red"
                                obs = f"ATENCIÓN: Se registró un pico absoluto de {data['max_abs']:.2f}V, superando el límite permitido de 100V. Se requiere limpieza o revisión."

                            img_tag = f'<img src="data:image/png;base64,{data["img_b64"]}" alt="Gráfica">' if data['img_b64'] else '<i>Sin gráfica disponible</i>'

                            # Bloque HTML para cada ubicación
                            html_ubicaciones += f"""
                            <div class="location-block" style="border: 2px solid #003366; border-radius: 6px; padding: 20px; margin-bottom: 30px; page-break-inside: avoid;">
                                <div class="location-title" style="font-size: 18px; font-weight: bold; color: white; background-color: #003366; padding: 10px; margin: -20px -20px 20px -20px; border-top-left-radius: 4px; border-top-right-radius: 4px;">Ubicación {idx}: {block['nombre']}</div>
                                <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px;">
                                    <tr>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 25%;">Tipo de Piso:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">{block['piso']}</td>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 25%;">Limpieza previa:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">Sí</td>
                                    </tr>
                                    <tr>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6;">Voltaje Máx (Abs):</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left; font-weight: bold;">{data['max_abs']:.2f} V</td>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6;">Promedio de Picos:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">{data['promedio_picos']:.2f} V</td>
                                    </tr>
                                </table>
                                
                                <div class="graph-placeholder" style="width: 100%; height: 250px; background-color: #fafafa; border: 2px dashed #aaa; display: flex; align-items: center; justify-content: center; color: #888; margin: 20px 0; overflow: hidden;">
                                    {img_tag}
                                </div>

                                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                                    <tr>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 20%;">Observaciones:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left;">{obs}</td>
                                        <th style="border: 1px solid #ccc; padding: 10px; text-align: left; background-color: #f4f7f6; width: 20%;">Resultado Final:</th>
                                        <td style="border: 1px solid #ccc; padding: 10px; text-align: left; color: {res_color}; font-weight: bold; font-size: 16px;">{res_text}</td>
                                    </tr>
                                </table>
                            </div>
                            """

                        html_completo = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Walking Test</title>
    <style>
        body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 0; padding: 20px; background-color: white; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
        header {{ text-align: center; border-bottom: 3px solid #003366; padding-bottom: 20px; margin-bottom: 30px; }}
        h1 {{ color: #003366; margin: 0 0 10px 0; font-size: 24px; }}
        h2 {{ font-size: 18px; color: #003366; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }}
        th, td {{ border: 1px solid #ccc; padding: 10px; text-align: left; }}
        th {{ background-color: #f4f7f6; font-weight: bold; width: 25%; }}
        .signatures {{ display: flex; justify-content: space-between; margin-top: 50px; page-break-inside: avoid; }}
        .signature-box {{ width: 45%; text-align: center; }}
        .signature-line {{ border-top: 1px solid black; margin-top: 50px; padding-top: 5px; font-size: 14px; }}
        img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
        @media print {{ body {{ padding: 0; }} .no-print {{ display: none; }} }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>Reporte de Walking Test (Prueba de Caminado)</h1>
        <p style="margin: 0; color: #666; font-size: 14px;">Evaluación de Sistema de Piso y Calzado ESD</p>
        <p style="margin: 0; color: #666; font-size: 14px;"><strong>Estándares aplicables:</strong> ANSI/ESD S20.20 y ANSI/ESD STM97.2</p>
    </header>

    <h2>1. Información General y Condiciones Ambientales</h2>
    <table>
        <tr><th>Fecha de Prueba:</th><td>{fecha_gen}</td><th>Periodo:</th><td>{periodo_wt}</td></tr>
        <tr><th>Auditor / Técnico:</th><td>{auditor_wt}</td><th>Operador de Prueba:</th><td>{operador_wt}</td></tr>
        <tr><th>Temperatura:</th><td>{temp_gen}</td><th>Humedad:</th><td>{hum_gen}</td></tr>
    </table>

    <h2>2. Equipo de Medición y Sistema Evaluado</h2>
    <table>
        <tr><th>Equipo Utilizado:</th><td>{equipo_wt}</td><th>Criterio de Aceptación:</th><td style="font-weight:bold; color:#003366;">&lt; 100 Voltios (Absoluto)</td></tr>
        <tr><th>Calzado ESD:</th><td colspan="3">{calzado_wt}</td></tr>
    </table>

    <h2>3. Resultados por Ubicación</h2>
    {html_ubicaciones}

    <div class="signatures">
        <div class="signature-box"><div class="signature-line"><strong>Realizado por:</strong><br>{auditor_wt}</div></div>
        <div class="signature-box"><div class="signature-line"><strong>Revisado / Aprobado por:</strong><br>Coordinador ESD</div></div>
    </div>
</div>
</body>
</html>"""

                        b64_html = base64.b64encode(html_completo.encode('utf-8')).decode('utf-8')
                        nombre_archivo = f"Walking_Test_{fecha_gen.replace('/', '-')}_{periodo_wt.replace(' ', '')}.html"
                        
                        st.success("✅ ¡Reporte consolidado generado exitosamente!")
                        href = f'<a href="data:text/html;base64,{b64_html}" download="{nombre_archivo}" target="_blank" style="display: block; text-align: center; padding: 15px; background-color: #003366; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; font-size: 16px;">📥 Descargar Reporte Completo (Abrir para imprimir PDF)</a>'
                        st.markdown(href, unsafe_allow_html=True)
