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

# Inicializar controlador de cookies (El correcto)
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
            try: 
                controller.remove('auditor_esd_sesion')
            except KeyError: 
                pass
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
        
        # --- ACORDEÓN DESPLEGABLE DE IDs (OPCIÓN 2) ---
        with st.expander("📋 Directorio de IDs Existentes (Click para abrir/cerrar)", expanded=False):
            st.info("💡 **Tip:** Puedes dejar este panel abierto mientras llenas el formulario abajo. Haz clic en el título de una columna para ordenar (A-Z) o usa la lupa (🔍) en la tabla para buscar un ID específico.")
            if not df_mob_local.empty and 'Id de producto' in df_mob_local.columns and 'Línea' in df_mob_local.columns:
                df_clean = df_mob_local[['Línea', 'Id de producto']].dropna(subset=['Id de producto'])
                df_clean = df_clean[df_clean['Id de producto'].astype(str).str.strip() != '']
                st.dataframe(df_clean, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay datos disponibles aún.")
        
        st.divider()
        
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
                    with st.spinner("Guardando registro corporativo..."):
                        import gspread
                        sec = dict(st.secrets["connections"]["gsheets"])
                        gc = gspread.service_account_from_dict(sec)
                        ws = gc.open_by_url(sec["spreadsheet"]).worksheet("MOBILIARIO")
                        
                        fecha_hoy = datetime.today().date()
                        dias_map = {"Anual": 360, "Semestral": 180, "Trimestral": 90, "Mensual": 30}
                        proxima = fecha_hoy + timedelta(days=dias_map.get(frecuencia_alta, 360))
                        
                        # Construcción de Fila A-R (18 columnas exactas)
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
    elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
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

        vencidos = df_total[(df_total['Estatus de verificación'] == 'VENCIDO') & (df_total['Estatus operativo'] != 'NO OPERATIVO')]
        
        if not vencidos.empty:
            st.error(f"🚨 Se encontraron {len(vencidos)} equipos VENCIDOS operativos.")
            conteo_tipos = vencidos.groupby(['Línea', 'Hoja Origen']).size().unstack(fill_value=0).reset_index()
            if 'PISO' not in conteo_tipos.columns: conteo_tipos['PISO'] = 0
            if 'MOBILIARIO' not in conteo_tipos.columns: conteo_tipos['MOBILIARIO'] = 0
            conteo_tipos.rename(columns={'PISO': 'Equipos (Piso)', 'MOBILIARIO': 'Mobiliario'}, inplace=True)
            conteo_tipos['Total Vencidos'] = conteo_tipos['Equipos (Piso)'] + conteo_tipos['Mobiliario']
            conteo_tipos['Etiqueta'] = "P: " + conteo_tipos['Equipos (Piso)'].astype(str) + "<br>M: " + conteo_tipos['Mobiliario'].astype(str)
            
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
                    fig.update_traces(
                        textposition='middle center', 
                        textfont=dict(color='white', size=10, weight='bold'), 
                        marker=dict(symbol='square', size=26, opacity=0.85, line=dict(width=1, color='black'))
                    )
                    fig.update_layout(
                        images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")], 
                        xaxis=dict(visible=False, range=[0, width]), 
                        yaxis=dict(visible=False, range=[height, 0], scaleanchor="x"), 
                        margin=dict(l=0, r=0, t=0, b=0),
                        coloraxis_showscale=False
                    )
                    st.plotly_chart(fig, use_container_width=True)
            st.dataframe(vencidos[['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación']], use_container_width=True, hide_index=True)
        else:
            st.success("✅ ¡Felicidades! No hay equipos operativos VENCIDOS.")

    # ==========================================
    # VISTA 2: ESCÁNER
    # ==========================================
    elif st.session_state.vista_actual == "Escáner":
        if not id_escaneado_url:
            st.markdown("### 📷 Apunta al Código QR")
            html_code_qr = """
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
            components.html(html_code_qr, height=500)
            
            id_manual = st.text_input("O ingresa el ID manual:", key="input_manual")
            if id_manual:
                st.query_params["qr_id"] = id_manual
                st.rerun()
        else:
            df_a = df_piso_local if id_escaneado_url in df_piso_local['Id de producto'].values else df_mob_local
            
            colA, colB = st.columns([0.8, 0.2])
            with colA: st.info(f"🔍 **ID Detectado:** {id_escaneado_url}")
            with colB:
                if st.button("❌ Cerrar"): st.query_params.clear(); st.rerun()
                
            if id_escaneado_url in df_a['Id de producto'].values:
                eq = df_a[df_a['Id de producto'] == id_escaneado_url].iloc[0]
                st.markdown("### 📊 Detalles del Equipo")
                
                c_linea, c_estatus = st.columns(2)
                c_linea.metric("Ubicación (Línea)", str(eq.get('Línea', 'N/A')))
                est_act = str(eq.get('Estatus de verificación', 'N/A')).strip().upper()
                c_estatus.metric("Estatus Actual", f"{'🟢' if est_act == 'VIGENTE' else '🔴'} {est_act}")
                
                c_f1, c_f2, c_val = st.columns(3)
                c_f1.metric("Última Medición", str(eq.get('Fecha de verificación', 'N/A')).strip())
                c_f2.metric("Próxima Medición", str(eq.get('Fecha de próxima verificación', 'N/A')).strip())
                
                v_prev = eq.get('Valor de verificación', 0)
                c_val.metric("Resistencia Registrada", f"{float(v_prev):.2E} Ω" if pd.notna(v_prev) and v_prev != 0 else "N/A")
                
                lim_raw = eq.get('Maximo', 'N/A')
                lim_str = f"{float(lim_raw):.2E} Ω" if pd.notna(lim_raw) and str(lim_raw).strip() != 'N/A' else "N/A"
                st.markdown(f"**Límite S20.20 Permitido:** {lim_str}")
                st.divider()

                if st.session_state.modo_lectura:
                    st.warning("👁️ **Modo Consulta.** No puedes editar datos.")
                else:
                    if st.checkbox("✅ Realizar nueva medición y actualizar", value=bool(valor_ocr_detectado)):
                        if not valor_ocr_detectado:
                            html_code_ocr = """
                            <script src="https://unpkg.com/tesseract.js@v4.0.3/dist/tesseract.min.js"></script>
                            <div id="ocr_scanner" style="width:100%; max-width:600px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0052cc; background-color: #111; padding: 10px; text-align: center; color: white;">
                                <div id="cam_container" style="position: relative; width: 100%; padding-bottom: 75%; overflow: hidden; border-radius: 8px; background: #000;">
                                    <video id="ocr_video" autoplay playsinline muted style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;"></video>
                                    <div id="lcd_screen" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 90%; height: 45%; border: 2px solid rgba(0,255,0,0.5); pointer-events: none;">
                                        <div id="box-ohms" style="position: absolute; top: 10%; left: 5%; width: 90%; height: 80%; border: 3px solid #00ff00;">
                                            <span style="position:absolute; top:-22px; left:0; font-size:12px; color:#00ff00; font-weight:bold;">ENFOQUE RESISTENCIA</span>
                                        </div>
                                    </div>
                                </div>
                                <p id="ocr_status" style="margin: 15px 0; font-size: 14px; color: #aaa;">Iniciando cámara trasera...</p>
                                <button id="ocr_btn" style="width: 100%; padding: 18px; font-size: 18px; font-weight: bold; background-color: #0052cc; color: white; border: none; border-radius: 8px;">📸 LEER MEDICIÓN</button>
                            </div>
                            <script>
                                const video = document.getElementById('ocr_video');
                                const btn = document.getElementById('ocr_btn');
                                const status = document.getElementById('ocr_status');
                                let camStream = null;

                                async function setupCamera() {
                                    try {
                                        let tempStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
                                        const devices = await navigator.mediaDevices.enumerateDevices();
                                        const cameras = devices.filter(d => d.kind === 'videoinput');
                                        let selectedId = null;
                                        const rearCams = cameras.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera'));
                                        
                                        if (rearCams.length > 0) {
                                            selectedId = rearCams[0].id; 
                                            status.innerText = "Alinea y lee.";
                                            for (const cam of rearCams) {
                                                if (cam.label.toLowerCase().includes('ultra') || cam.label.toLowerCase().includes('macro')) {
                                                    selectedId = cam.id; break;
                                                }
                                            }
                                        }
                                        tempStream.getTracks().forEach(t => t.stop());
                                        const constraints = selectedId ? { video: { deviceId: { exact: selectedId }, focusMode: 'continuous' } } : { video: { facingMode: 'environment', focusMode: 'continuous' } };
                                        camStream = await navigator.mediaDevices.getUserMedia(constraints);
                                        video.srcObject = camStream;
                                    } catch (e) { status.innerText = "Error de cámara"; }
                                }
                                setupCamera();

                                btn.addEventListener('click', async () => {
                                    btn.disabled = true;
                                    status.innerText = "⏳ ANALIZANDO...";
                                    
                                    const box = document.getElementById('box-ohms');
                                    const container = document.getElementById('cam_container');
                                    const rectBox = box.getBoundingClientRect();
                                    const rectCont = container.getBoundingClientRect();
                                    const relX = (rectBox.left - rectCont.left) / rectCont.width;
                                    const relY = (rectBox.top - rectCont.top) / rectCont.height;
                                    const relW = rectBox.width / rectCont.width;
                                    const relH = rectBox.height / rectCont.height;
                                    const cropX = video.videoWidth * relX;
                                    const cropY = video.videoHeight * relY;
                                    const cropW = video.videoWidth * relW;
                                    const cropH = video.videoHeight * relH;

                                    const canvas = document.createElement('canvas');
                                    canvas.width = cropW * 2; canvas.height = cropH * 2;
                                    const ctx = canvas.getContext('2d');
                                    ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, canvas.width, canvas.height);
                                    
                                    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                                    const data = imgData.data;
                                    for (let i=0; i<data.length; i+=4) {
                                        const avg = (data[i] + data[i+1] + data[i+2]) / 3;
                                        data[i] = data[i+1] = data[i+2] = avg >= 130 ? 255 : 0; 
                                    }
                                    ctx.putImageData(imgData, 0, 0);
                                    
                                    try {
                                        const worker = await Tesseract.createWorker();
                                        await worker.loadLanguage('eng');
                                        await worker.initialize('eng');
                                        await worker.setParameters({ tessedit_char_whitelist: '0123456789.xX*Ee^ ' });
                                        const { data: { text } } = await worker.recognize(canvas);
                                        await worker.terminate();

                                        let cleaned = text.replace(/\\s+/g, '');
                                        const match = cleaned.match(/(\\d+\\.\\d{1,2}).*?10.*?(\\d{1,2})/);

                                        if (match) {
                                            const finalValue = parseFloat(match[1]) * Math.pow(10, parseInt(match[2]));
                                            camStream.getTracks().forEach(t => t.stop());
                                            const url = new URL(window.parent.location.href);
                                            url.searchParams.set("ocr_val", finalValue);
                                            window.parent.history.replaceState({}, "", url);
                                            window.parent.location.reload();
                                        } else {
                                            status.innerText = "❌ Exponente no claro.";
                                            status.style.color = "#ff4b4b";
                                            btn.disabled = false;
                                        }
                                    } catch (err) { btn.disabled = false; }
                                });
                            </script>
                            """
                            components.html(html_code_ocr, height=700)
                        else:
                            st.success("✅ **Resistencia capturada:**")
                            st.metric("Nuevo Valor", f"{float(valor_ocr_detectado):.2E} Ω")
                            if st.button("🔄 Descartar captura"):
                                if "ocr_val" in st.query_params: del st.query_params["ocr_val"]
                                st.rerun()

                        with st.form("form_actualizacion"):
                            def_val = float(valor_ocr_detectado) if valor_ocr_detectado else 0.0
                            nuevo_valor_final = st.number_input("Resistencia (Ohms)", value=def_val, format="%.2e")
                            fecha_hoy = datetime.today().date()
                            nueva_fecha_valida = st.date_input("Fecha de medición", fecha_hoy)
                            
                            if st.form_submit_button("Guardar en Google Sheets"):
                                with st.spinner("Guardando..."):
                                    freq = str(eq.get('Frecuencia de verificación', 'Anual'))
                                    proxy = calcular_proxima_fecha(nueva_fecha_valida, freq)
                                    
                                    import gspread
                                    sec = dict(st.secrets["connections"]["gsheets"])
                                    gc_gspread = gspread.service_account_from_dict(sec)
                                    ws = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet("PISO" if encontrado_piso else "MOBILIARIO")
                                    
                                    ids = ws.col_values(df_a.columns.get_loc('Id de producto') + 1)
                                    r_idx = [str(v).strip() for v in ids].index(str(id_escaneado_url).strip()) + 1
                                    
                                    ws.update_cell(r_idx, df_a.columns.get_loc('Valor de verificación') + 1, float(nuevo_valor_final))
                                    ws.update_cell(r_idx, df_a.columns.get_loc('Fecha de verificación') + 1, nueva_fecha_valida.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, df_a.columns.get_loc('Fecha de próxima verificación') + 1, proxy.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, df_a.columns.get_loc('Estatus de verificación') + 1, 'VIGENTE')
                                    ws.update_cell(r_idx, df_a.columns.get_loc('Auditor') + 1, st.session_state.usuario_nombre)

                                st.success("💾 Guardado!")
                                st.cache_data.clear()
                                st.query_params.clear()
                                st.rerun()
