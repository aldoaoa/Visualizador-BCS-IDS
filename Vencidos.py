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

# Inicializar el controlador de cookies
controller = CookieController()

# ==========================================
# CAPA DE SEGURIDAD (COOKIES Y ROLES)
# ==========================================

# Definimos los posibles roles de la sesión actual
if "usuario_nombre" not in st.session_state:
    st.session_state.usuario_nombre = None
if "modo_lectura" not in st.session_state:
    st.session_state.modo_lectura = False

# Intentar recuperar sesión persistente
cookie_auditor = controller.get('auditor_esd_sesion')
if cookie_auditor:
    st.session_state.usuario_nombre = cookie_auditor
    st.session_state.modo_lectura = False # Si hay cookie, es un auditor real

# --- PANTALLA DE ACCESO PRINCIPAL ---
if st.session_state.usuario_nombre is None and not st.session_state.modo_lectura:
    st.markdown("<h2 style='text-align: center;'>🛡️ Sistema de Gestión ESD S20.20</h2>", unsafe_allow_html=True)
    
    col_vacia1, col_central, col_vacia2 = st.columns([1, 1.2, 1])
    
    with col_central:
        # Pestañas para elegir el método de entrada
        tab_login, tab_monitor = st.tabs(["🔒 Ingreso de Auditores", "👁️ Modo Consulta"])
        
        with tab_login:
            with st.form("login_form"):
                user_input = st.text_input("Usuario (ID)")
                pwd_input = st.text_input("Contraseña", type="password")
                submit_login = st.form_submit_button("Ingresar y Editar", use_container_width=True)
                
                if submit_login:
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
                        st.error("⚠️ No hay usuarios configurados en los secretos.")
        
        with tab_monitor:
            st.info("El Modo Consulta permite escanear equipos y ver su vigencia en tiempo real. No requiere contraseña, pero **no permite modificar o auditar valores**.")
            if st.button("👁️ Entrar en Modo Consulta", use_container_width=True, type="secondary"):
                st.session_state.modo_lectura = True
                st.session_state.usuario_nombre = "Usuario de Consulta"
                st.rerun()
                
    st.stop() # Detiene la ejecución si no se ha elegido un acceso

# ==========================================
# APLICACIÓN PRINCIPAL (Auditor o Monitor)
# ==========================================
RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"

# Barra lateral informativa
with st.sidebar:
    if st.session_state.modo_lectura:
        st.warning("👁️ **Modo Consulta Activo**\n\nSolo lectura.")
    else:
        st.success(f"👤 **Auditor:** {st.session_state.usuario_nombre}")
        
    if st.button("Salir al Menú Principal", use_container_width=True):
        st.session_state.usuario_nombre = None
        st.session_state.modo_lectura = False
        
        # Intentamos borrar la cookie de sesión de forma segura
        try:
            controller.remove('auditor_esd_sesion')
        except KeyError:
            pass # Si la cookie no existe (Ej. Modo Consulta), simplemente lo ignora
            
        st.rerun()

conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2, max_entries=1) 
def cargar_datos_cloud():
    try:
        df_piso = conn.read(worksheet="PISO", header=4)
        df_mob = conn.read(worksheet="MOBILIARIO", header=4)
        return df_piso, df_mob
    except Exception as e:
        st.error(f"Error de conexión con la nube: {e}")
        return None, None

st.title("Sistema de Gestión ESD S20.20")

df_piso_local, df_mob_local = cargar_datos_cloud()

if df_piso_local is None or df_mob_local is None:
    st.warning("⚠️ Falla al conectar con Google Sheets.")
    st.stop()

if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "Escáner" # Mejor default para celulares

id_escaneado_url = st.query_params.get("qr_id", "")
valor_ocr_detectado = st.query_params.get("ocr_val", "")

if id_escaneado_url or valor_ocr_detectado:
    st.session_state.vista_actual = "Escáner"

# Si está en modo lectura, no mostramos el mapa para simplificar (opcional, lo puedes quitar)
if not st.session_state.modo_lectura:
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("🗺️ Mapa y Reportes ESD", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
            st.session_state.vista_actual = "Mapa"
            st.query_params.clear() 
            st.rerun()
    with col_nav2:
        if st.button("📱 Escáner Automático", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
            st.session_state.vista_actual = "Escáner"
            st.rerun()
else:
    # Forzar vista de escáner en modo lectura
    st.session_state.vista_actual = "Escáner"

st.divider()

# ==========================================
# VISTA 1: MAPA Y REPORTES ESD (Oculto para el modo consulta)
# ==========================================
if st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
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
                fig.update_traces(textposition='middle center', textfont=dict(color='white', size=12, weight='bold'), marker=dict(symbol='square', size=50, opacity=0.9))
                fig.update_layout(images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")], xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"), margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)
        st.dataframe(vencidos[['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación']], use_container_width=True, hide_index=True)
    else:
        st.success("✅ ¡Felicidades! No hay equipos operativos VENCIDOS.")

# ==========================================
# VISTA 2: ESCÁNER Y DETALLES
# ==========================================
elif st.session_state.vista_actual == "Escáner":
    
    if not id_escaneado_url:
        st.markdown("### 📷 Apunta al Código QR")
        html_code_qr = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
        <p id="cam-status" style="text-align:center; color:#666; font-size: 14px;">Iniciando cámara trasera...</p>
        <script>
        Html5Qrcode.getCameras().then(devices => {
            if (devices && devices.length) {
                let selectedCameraId = devices[0].id; 
                let rearCams = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera'));
                if (rearCams.length > 0) {
                    selectedCameraId = rearCams[0].id; 
                    for (let cam of rearCams) {
                        if (cam.label.toLowerCase().includes('ultra') || cam.label.toLowerCase().includes('macro')) {
                            selectedCameraId = cam.id; break;
                        }
                    }
                }
                const html5QrCode = new Html5Qrcode("reader");
                html5QrCode.start(
                    selectedCameraId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    (decodedText) => {
                        html5QrCode.stop();
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set("qr_id", decodedText);
                        url.searchParams.delete("ocr_val");
                        window.parent.history.replaceState({}, "", url);
                        window.parent.location.reload();
                    }, (err) => {} 
                ).then(() => { setTimeout(() => { document.getElementById("cam-status").style.display = 'none'; }, 1500); });
            }
        }).catch(err => { document.getElementById("cam-status").innerText = "Otorga permisos de cámara."; });
        </script>
        """
        components.html(html_code_qr, height=500)
        
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
                st.query_params.clear()
                st.rerun()

        encontrado_piso = id_escaneado_url in df_piso_local['Id de producto'].values
        encontrado_mob = id_escaneado_url in df_mob_local['Id de producto'].values

        if encontrado_piso or encontrado_mob:
            hoja_activa = "PISO" if encontrado_piso else "MOBILIARIO"
            df_actual = df_piso_local if encontrado_piso else df_mob_local
            idx = df_actual[df_actual['Id de producto'] == id_escaneado_url].index[0]
            equipo = df_actual.iloc[idx]
            
            # --- MOSTRAR DETALLES Y ESTATUS (Para ambos roles) ---
            st.markdown("### 📊 Detalles del Equipo")
            
            # Fila 1: Línea y Estatus
            c_linea, c_estatus = st.columns(2)
            c_linea.metric("Ubicación (Línea)", str(equipo.get('Línea', 'N/A')))
            estatus_actual = str(equipo.get('Estatus de verificación', 'N/A')).strip().upper()
            color_estatus = "🟢" if estatus_actual == "VIGENTE" else "🔴"
            c_estatus.metric("Estatus Actual", f"{color_estatus} {estatus_actual}")
            
            # Fila 2: Fechas y Valor
            c_fecha_ult, c_fecha_prox, c_val = st.columns(3)
            c_fecha_ult.metric("Última Medición", str(equipo.get('Fecha de verificación', 'N/A'))[:10])
            c_fecha_prox.metric("Próxima Medición", str(equipo.get('Fecha de próxima verificación', 'N/A'))[:10])
            
            val_previo = equipo.get('Valor de verificación', 0)
            limite = equipo.get('Límite de verificación (ohmios)', 'N/A')
            
            if pd.notna(val_previo) and val_previo != 0:
                c_val.metric("Resistencia Registrada", f"{float(val_previo):.2E} Ω")
            else:
                c_val.metric("Resistencia Registrada", "N/A")
                
            st.markdown(f"**Límite S20.20 Permitido:** {limite}")
            
            st.divider()

            # --- BLOQUEO DE EDICIÓN PARA MODO CONSULTA ---
            if st.session_state.modo_lectura:
                st.warning("👁️ **Estás en Modo Consulta.** No tienes permisos para capturar pantallas de medidores ni actualizar los registros de Google Sheets. Regresa al menú principal e inicia sesión para auditar.")
            else:
                # --- FLUJO DE AUDITOR (OCR Y ACTUALIZACIÓN) ---
                hacer_medicion = st.checkbox("✅ Realizar nueva medición y actualizar", value=bool(valor_ocr_detectado))
                
                if hacer_medicion:
                    st.markdown("### 📷 Captura Automática del Medidor")
                    
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

                    st.markdown("#### Validar y Sincronizar")
                    with st.form("form_actualizacion"):
                        def_val = float(valor_ocr_detectado) if valor_ocr_detectado else 0.0
                        nuevo_valor_final = st.number_input("Resistencia (Ohms)", value=def_val, format="%.2e")
                        fecha_hoy = datetime.today().date()
                        nueva_fecha_valida = st.date_input("Fecha de medición", fecha_hoy)
                        
                        submit_corporativo = st.form_submit_button("Guardar en Google Sheets")
                        
                        if submit_corporativo:
                            with st.spinner("Guardando..."):
                                freq = str(equipo.get('Frecuencia de verificación', 'Anual'))
                                proxy = calcular_proxima_fecha(nueva_fecha_valida, freq)
                                import gspread
                                sec = dict(st.secrets["connections"]["gsheets"])
                                gc_gspread = gspread.service_account_from_dict(sec)
                                ws = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet(hoja_activa)
                                
                                try:
                                    id_idx = df_actual.columns.get_loc('Id de producto')
                                    val_idx = df_actual.columns.get_loc('Valor de verificación')
                                    f_idx = df_actual.columns.get_loc('Fecha de verificación')
                                    fp_idx = df_actual.columns.get_loc('Fecha de próxima verificación')
                                    st_idx = df_actual.columns.get_loc('Estatus de verificación')
                                    aud_idx = df_actual.columns.get_loc('Auditor') 
                                except KeyError as e:
                                    st.error(f"Falta columna {e}")
                                    st.stop()
                                
                                ids = ws.col_values(id_idx + 1)
                                r_idx = [str(v).strip() for v in ids].index(str(id_escaneado_url).strip()) + 1
                                
                                ws.update_cell(r_idx, val_idx + 1, float(nuevo_valor_final))
                                ws.update_cell(r_idx, f_idx + 1, nueva_fecha_valida.strftime("%Y-%m-%d"))
                                ws.update_cell(r_idx, fp_idx + 1, proxy.strftime("%Y-%m-%d"))
                                ws.update_cell(r_idx, st_idx + 1, 'VIGENTE')
                                ws.update_cell(r_idx, aud_idx + 1, st.session_state.usuario_nombre)

                            st.success("💾 Guardado!")
                            st.cache_data.clear()
                            st.query_params.clear()
                            st.rerun()
        else:
            st.error("❌ El ID escaneado no existe.")
