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
    valor_ocr_detectado = st.query_params.get("ocr_val", "")
    id_baja_url = st.query_params.get("qr_baja", "")
    
    if id_escaneado_url or valor_ocr_detectado:
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
                
                estatus_op = str(equipo.get('Estatus operativo', '')).strip().upper()
                if estatus_op == "NO OPERATIVO":
                    st.warning("⚠️ Este equipo ya se encuentra dado de BAJA.")
                
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
                tipo_alta = st.radio("Categoría:", ["Mobiliario", "Ionizador"], horizontal=True)
                df_target_alta = df_mob_local if tipo_alta == "Mobiliario" else df_ion_local
                
                todas_lineas = set()
                for df_temp in [df_piso_local, df_mob_local, df_ion_local]:
                    if df_temp is not None and 'Línea' in df_temp.columns:
                        todas_lineas.update([str(x).strip() for x in df_temp['Línea'].dropna() if str(x).strip() != ''])
                lineas_disponibles = sorted(list(todas_lineas))

                with st.form("form_alta_equipo"):
                    col1, col2 = st.columns(2)
                    nueva_linea = col1.selectbox("Línea (Ubicación)", options=lineas_disponibles if lineas_disponibles else ["SMT", "Ensamble"])
                    
                    # --- MEJORA: Validación en tiempo real del ID ---
                    nuevo_id = col2.text_input("ID de Producto")
                    id_limpio_alta = str(nuevo_id).strip().upper()
                    
                    es_duplicado = False
                    es_reactivacion = False
                    
                    if id_limpio_alta:
                        ids_existentes = df_target_alta.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper()
                        if id_limpio_alta in ids_existentes.values:
                            idx_ext = ids_existentes[ids_existentes == id_limpio_alta].index[0]
                            estatus_op_ext = str(df_target_alta.loc[idx_ext].get('Estatus operativo', '')).strip().upper()
                            
                            if estatus_op_ext == "NO OPERATIVO":
                                col2.warning("⚠️ Este equipo está dado de BAJA. Si continúas, se REACTIVARÁ con los datos nuevos.")
                                es_reactivacion = True
                            else:
                                col2.error("❌ Este ID ya está en uso y Activo.")
                                es_duplicado = True
                    
                    if tipo_alta == "Mobiliario":
                        tipos_disponibles = sorted([str(x).strip() for x in df_target_alta.get('Clasificación', pd.Series()).unique() if pd.notna(x) and str(x).strip() != ''])
                        nuevo_tipo = col1.selectbox("Tipo", options=tipos_disponibles if tipos_disponibles else ["Mesa", "Silla"])
                        
                        st.caption("Valor de medición inicial (Ohms)")
                        c_b, c_x, c_e = st.columns([2, 1, 2])
                        base_alta = c_b.number_input("Número", value=None, format="%.2f", key="base_alt_mob")
                        c_x.markdown("<div style='text-align: center; margin-top: 30px;'>x 10^</div>", unsafe_allow_html=True)
                        exp_alta = c_e.number_input("Exponente", value=None, step=1, key="exp_alt_mob")
                        valor_alta = (base_alta * (10 ** exp_alta)) if base_alta is not None and exp_alta is not None else None
                        
                        fabricante_opc = col1.selectbox("Fabricante", options=["BCS", "Otro", "N/A"])
                        fabricante_final = fabricante_opc
                        if fabricante_opc == "Otro":
                            fabricante_final = col1.text_input("Especifique Fabricante")
                            
                        frecuencia_alta = col2.selectbox("Frecuencia", options=["Anual", "Semestral", "Trimestral", "Mensual"], index=0)
                        col3, col4 = st.columns(2)
                        nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e")
                        limite_alta = col4.text_input("Límite S20.20", value="1.00E+09")
                        
                    else:
                        nuevo_tipo = col1.selectbox("Tipo", options=["Ventilador", "Barra", "Pistola"])
                        valor_alta = col2.number_input("Tiempo de descarga (Seg)", value=None, format="%.2f")
                        fabricante_opc = col1.selectbox("Fabricante", options=["SMC", "Panasonic", "Keyence", "SIMCO", "Otro"])
                        fabricante_final = fabricante_opc
                        if fabricante_opc == "Otro":
                            fabricante_final = col1.text_input("Especifique Fabricante")
                            
                        balance_alta = col2.number_input("Balance (V)", value=None, format="%.2f")
                        frecuencia_alta = "Trimestral"; nuevo_minimo = 0.00; limite_alta = "10.00"

                    comentarios = st.text_area("Comentarios")
                    
                    texto_boton = "Reactivar Equipo" if es_reactivacion else "Registrar en sistema"
                    submit_alta = st.form_submit_button(texto_boton, use_container_width=True)
                    
                    if submit_alta:
                        if es_duplicado:
                            st.error(f"❌ No se puede guardar. El ID {nuevo_id} ya existe y está activo.")
                        elif not nuevo_id or (fabricante_opc == "Otro" and not fabricante_final):
                            st.error("Completa los campos obligatorios.")
                        else:
                            with st.spinner("Guardando en base de datos..."):
                                import gspread
                                sec = dict(st.secrets["connections"]["gsheets"])
                                gc_client = gspread.service_account_from_dict(sec)
                                nombre_hoja = "MOBILIARIO" if tipo_alta == "Mobiliario" else "IONIZADORES"
                                ws = gc_client.open_by_url(sec["spreadsheet"]).worksheet(nombre_hoja)
                                
                                fecha_hoy = datetime.today().date()
                                proxima = calcular_proxima_fecha(fecha_hoy, frecuencia_alta)
                                
                                unidad = "Segundos" if tipo_alta == "Ionizador" else "Ohms"
                                metodo = "CPM" if tipo_alta == "Ionizador" else "RTG"
                                
                                val_guardar = float(valor_alta) if valor_alta is not None else ""
                                
                                nueva_fila = [
                                    nueva_linea, nuevo_id, nuevo_tipo, "Aprobado", fabricante_final,
                                    float(nuevo_minimo), float(limite_alta) if "E" in str(limite_alta).upper() else limite_alta,
                                    unidad, val_guardar, unidad, metodo,
                                    fecha_hoy.strftime("%d-%b-%Y") if val_guardar != "" else "", 
                                    proxima.strftime("%d-%b-%Y") if val_guardar != "" else "", frecuencia_alta,
                                    "Vigente" if val_guardar != "" and fecha_hoy < proxima else "", 
                                    "Operativo", comentarios, st.session_state.usuario_nombre
                                ]
                                
                                if tipo_alta == "Ionizador":
                                    bal_guardar = float(balance_alta) if balance_alta is not None else ""
                                    nueva_fila.append(bal_guardar)
                                
                                # Si es reactivación, sobreescribimos la fila existente
                                if es_reactivacion:
                                    id_idx_alta = df_target_alta.columns.get_loc('Id de producto')
                                    ids_gsheets_alta = ws.col_values(id_idx_alta + 1)
                                    ids_gsheets_limpios_alta = [str(v).strip().upper() for v in ids_gsheets_alta]
                                    r_idx_alta = ids_gsheets_limpios_alta.index(id_limpio_alta) + 1
                                    
                                    for col_num, val in enumerate(nueva_fila, start=1):
                                        ws.update_cell(r_idx_alta, col_num, val)
                                        
                                    st.success(f"✅ ¡Equipo {nuevo_id} REACTIVADO con éxito en {nombre_hoja}!")
                                else:
                                    ws.append_row(nueva_fila, value_input_option="USER_ENTERED")
                                    st.success(f"✅ Registrado exitosamente en {nombre_hoja}")
                                    
                                st.cache_data.clear(); st.balloons()

            with tab_baja:
                st.markdown("#### Escanea el equipo a dar de baja")
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
        tipo_mapa = st.radio("Categoría:", ["Mobiliario", "Ionizadores"], horizontal=True)
        df_total = df_mob_local.copy() if tipo_mapa == "Mobiliario" else df_ion_local.copy()
        
        if df_total.empty or 'Estatus de verificación' not in df_total.columns:
            st.warning("Verifica los encabezados de la hoja.")
        else:
            df_total['Estatus de verificación'] = df_total['Estatus de verificación'].astype(str).str.strip().str.upper()
            df_total['Estatus operativo'] = df_total['Estatus operativo'].astype(str).str.strip().str.upper() if 'Estatus operativo' in df_total.columns else 'OPERATIVO'
            
            activos = df_total[df_total['Estatus operativo'] != 'NO OPERATIVO']
            vencidos = activos[activos['Estatus de verificación'] == 'VENCIDO']
            
            cumplimiento = ((len(activos) - len(vencidos)) / len(activos) * 100) if not activos.empty else 100
            
            if not vencidos.empty:
                st.error(f"🚨 Cumplimiento: {cumplimiento:.1f}% | {len(vencidos)} vencidos de {len(activos)} activos.")
                if os.path.exists(RUTA_MAPA) and os.path.exists(RUTA_COORDENADAS):
                    img = Image.open(RUTA_MAPA); df_coords = pd.read_csv(RUTA_COORDENADAS)
                    mapa_data = pd.merge(vencidos.groupby('Línea').size().reset_index(name='V'), df_coords, on='Línea')
                    fig = px.scatter(mapa_data, x="X", y="Y", color="V", text="V", hover_name="Línea", color_continuous_scale="Reds")
                    fig.update_layout(images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=img.size[0], sizey=img.size[1], sizing="stretch", layer="below")], xaxis_visible=False, yaxis_visible=False, yaxis_range=[img.size[1], 0], margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.success(f"✅ 100% Cumplimiento ({len(activos)} activos).")

    # ==========================================
    # VISTA: ESCÁNER / AUDITORÍA
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        if not id_escaneado_url:
            st.markdown("### 📷 Identificar Activo")
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
            if st.button("❌ Cerrar Escaneo"): limpiar_url_escaneo(); st.rerun()
            id_limpio = str(id_escaneado_url).strip().upper()
            es_mob = id_limpio in df_mob_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper().values
            es_ion = id_limpio in df_ion_local.get('Id de producto', pd.Series()).astype(str).str.strip().str.upper().values

            if es_mob or es_ion:
                hoja_activa = "MOBILIARIO" if es_mob else "IONIZADORES"
                df = df_mob_local if es_mob else df_ion_local
                idx = df[df['Id de producto'].astype(str).str.strip().str.upper() == id_limpio].index[0]
                equipo = df.loc[idx]
                
                estatus_actual_op = str(equipo.get('Estatus operativo', '')).strip().upper()
                if estatus_actual_op == "NO OPERATIVO":
                    st.error("⚠️ Este equipo se encuentra dado de BAJA.")
                
                st.subheader(f"Equipo: {id_limpio} ({hoja_activa})")
                
                # --- MEJORA: Checkbox dinámico (Actualizar vs Reactivar) ---
                if estatus_actual_op == "NO OPERATIVO":
                    texto_checkbox = "✅ REACTIVAR equipo y registrar nueva medición"
                else:
                    texto_checkbox = "✅ Realizar nueva medición y actualizar"
                
                hacer_medicion = st.checkbox(texto_checkbox, value=bool(valor_ocr_detectado))

                if hacer_medicion:
                    with st.form("form_upd"):
                        todas_l = sorted(list(set(df_mob_local['Línea'].dropna().tolist() + df_ion_local['Línea'].dropna().tolist())))
                        linea_act = str(equipo.get('Línea', '')).strip()
                        nueva_l = st.selectbox("Cambiar Ubicación (opcional):", options=todas_l, index=todas_l.index(linea_act) if linea_act in todas_l else 0)
                        
                        if es_ion:
                            v_act = st.number_input("Tiempo de Descarga (s)", value=None, format="%.2f")
                            b_act = st.number_input("Balance (V)", value=None, format="%.2f")
                        else:
                            st.caption("Resistencia (Ohms)")
                            c1, c2, c3 = st.columns([2,1,2])
                            n_base = c1.number_input("Base", value=None, format="%.2f")
                            c2.markdown("<br><div style='text-align: center; font-weight: bold;'>x 10^</div>", unsafe_allow_html=True)
                            n_exp = c3.number_input("Exp", value=None, step=1)
                            
                        f_med = st.date_input("Fecha Medición", datetime.today().date())
                        
                        texto_guardar_escaner = "Reactivar y Guardar" if estatus_actual_op == "NO OPERATIVO" else "Guardar"
                        if st.form_submit_button(texto_guardar_escaner):
                            if (not es_ion and (n_base is None or n_exp is None)) or (es_ion and (v_act is None or b_act is None)):
                                st.error("⚠️ Ingresa los valores de medición antes de guardar.")
                            else:
                                with st.spinner("Procesando..."):
                                    if not es_ion:
                                        v_act_final = n_base * (10**n_exp)
                                    else:
                                        v_act_final = v_act

                                    import gspread
                                    sec = dict(st.secrets["connections"]["gsheets"])
                                    gc = gspread.service_account_from_dict(sec)
                                    
                                    # Historial
                                    try:
                                        wh = gc.open_by_url(sec["spreadsheet"]).worksheet("HISTORIAL")
                                        wh.append_row([id_limpio, hoja_activa, equipo.get('Línea',''), str(equipo.get('Valor de verificación','')), str(equipo.get('Balance','')), str(equipo.get('Fecha de verificación','')), str(equipo.get('Auditor','')), datetime.now().strftime("%d-%b-%Y %H:%M")])
                                    except: pass
                                    
                                    # Update
                                    ws = gc.open_by_url(sec["spreadsheet"]).worksheet(hoja_activa)
                                    r_idx = ws.col_values(df.columns.get_loc('Id de producto') + 1).index(id_limpio) + 1
                                    
                                    ws.update_cell(r_idx, df.columns.get_loc('Línea') + 1, nueva_l)
                                    ws.update_cell(r_idx, df.columns.get_loc('Valor de verificación') + 1, float(v_act_final))
                                    ws.update_cell(r_idx, df.columns.get_loc('Fecha de verificación') + 1, f_med.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, df.columns.get_loc('Fecha de próxima verificación') + 1, calcular_proxima_fecha(f_med, equipo.get('Frecuencia de verificación','Anual')).strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, df.columns.get_loc('Estatus de verificación') + 1, "VIGENTE")
                                    
                                    # Si estaba dado de baja, se fuerza a OPERATIVO nuevamente
                                    if estatus_actual_op == "NO OPERATIVO":
                                        try: ws.update_cell(r_idx, df.columns.get_loc('Estatus operativo') + 1, "OPERATIVO")
                                        except: pass

                                    try: ws.update_cell(r_idx, df.columns.get_loc('Auditor') + 1, st.session_state.usuario_nombre)
                                    except: ws.update_cell(r_idx, 18, st.session_state.usuario_nombre) 
                                    
                                    if es_ion:
                                        try: ws.update_cell(r_idx, df.columns.get_loc('Balance') + 1, float(b_act))
                                        except: ws.update_cell(r_idx, 19, float(b_act))

                                    st.success("Guardado"); st.cache_data.clear(); limpiar_url_escaneo(); st.rerun()
            else:
                st.error("No encontrado.")
            
