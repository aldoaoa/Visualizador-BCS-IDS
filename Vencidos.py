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

# Configuración horizontal (Wide)
st.set_page_config(page_title="Control ESD Corporativo S20.20", layout="wide")

RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"

# --- CONEXIÓN A GOOGLE SHEETS EN TIEMPO REAL ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2, max_entries=1) 
def cargar_datos_cloud():
    try:
        df_piso = conn.read(worksheet="PISO", header=4)
        df_mob = conn.read(worksheet="MOBILIARIO", header=4)
        return df_piso, df_mob
    except Exception as e:
        st.error(f"Error de conexión con la nube de Google Sheets: {e}")
        return None, None

def calcular_proxima_fecha(fecha_actual, frecuencia):
    frecuencia = str(frecuencia).strip().lower()
    if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
    elif 'semestral' in frecuencia or '6 meses' in frecuencia: return fecha_actual + relativedelta(months=6)
    elif 'trimestral' in frecuencia or '3 meses' in frecuencia: return fecha_actual + relativedelta(months=3)
    elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
    else: return fecha_actual + relativedelta(years=1)

# --- INICIO DE LA APLICACIÓN CORPORATIVA ---
st.title("Sistema de Gestión ESD S20.20 - Corporativo")

df_piso_local, df_mob_local = cargar_datos_cloud()

if df_piso_local is None or df_mob_local is None:
    st.warning("⚠️ Asegúrate de haber compartido la Google Sheet Corporativa con el correo de la cuenta de servicio de Streamlit (Editor).")
    st.stop()

# --- CONTROL DE NAVEGACIÓN ---
if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "Mapa"

# Solo conservamos QR y el valor OCR de resistencia
id_escaneado_url = st.query_params.get("qr_id", "")
valor_ocr_detectado = st.query_params.get("ocr_val", "")

if id_escaneado_url or valor_ocr_detectado:
    st.session_state.vista_actual = "Escáner"

col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    if st.button("🗺️ Mapa y Reportes ESD", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
        st.session_state.vista_actual = "Mapa"
        st.query_params.clear() 
        st.rerun()
with col_nav2:
    if st.button("📱 Escáner Automático (QR/Medidor)", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
        st.session_state.vista_actual = "Escáner"
        st.rerun()

st.divider()

# ==========================================
# VISTA 1: MAPA Y REPORTES ESD
# ==========================================
if st.session_state.vista_actual == "Mapa":
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
        st.error(f"🚨 Se encontraron {len(vencidos)} equipos o mobiliario VENCIDOS en operación.")
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
                    hover_data={"X": False, "Y": False, "Etiqueta": False, "Total Vencidos": True, "Equipos (Piso)": True, "Mobiliario": True},
                    color_continuous_scale="Reds"
                )
                fig.update_traces(textposition='middle center', textfont=dict(color='white', size=12, weight='bold'), marker=dict(symbol='square', size=50, opacity=0.9, line=dict(width=2, color='DarkSlateGrey')))
                fig.update_layout(images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")], xaxis=dict(showgrid=False, zeroline=False, range=[0, width], visible=False), yaxis=dict(showgrid=False, zeroline=False, range=[height, 0], visible=False, scaleanchor="x", scaleratio=1), margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True)
            del img, df_coords, mapa_data, fig
            gc.collect()
            
        st.markdown("### Detalles de Equipos fuera de cumplimiento")
        columnas_mostrar = ['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación', 'Estatus operativo', 'Hoja Origen']
        st.dataframe(vencidos[[col for col in columnas_mostrar if col in vencidos.columns]], use_container_width=True, hide_index=True)
    else:
        st.success("✅ ¡Felicidades! No hay equipos operativos con estatus 'VENCIDO'.")
    
    del df_piso_mapa, df_mob_mapa, df_total, vencidos
    gc.collect()

# ==========================================
# VISTA 2: ESCÁNER Y ACTUALIZACIÓN
# ==========================================
elif st.session_state.vista_actual == "Escáner":
    
    if not id_escaneado_url:
        st.markdown("### 📷 Apunta al Código QR")
        
        # --- NUEVA LÓGICA DE CÁMARA TRASERA PARA QR ---
        html_code_qr = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
        <p id="cam-status" style="text-align:center; font-family:sans-serif; color:#666; font-size: 14px;">Iniciando cámara trasera...</p>
        <script>
        Html5Qrcode.getCameras().then(devices => {
            if (devices && devices.length) {
                let selectedCameraId = devices[0].id; // Fallback extremo
                
                // 1. Filtrar SOLO cámaras traseras (ignorar selfie)
                let rearCams = devices.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera'));
                
                if (rearCams.length > 0) {
                    selectedCameraId = rearCams[0].id; // Usar la primera trasera por default
                    document.getElementById("cam-status").innerText = "Cámara trasera activada.";
                    
                    // 2. Buscar específicamente lente Macro/Ultra Wide
                    for (let cam of rearCams) {
                        if (cam.label.toLowerCase().includes('ultra') || cam.label.toLowerCase().includes('macro')) {
                            selectedCameraId = cam.id;
                            document.getElementById("cam-status").innerText = "Lente Macro trasero activado.";
                            break;
                        }
                    }
                }

                // Iniciar escáner con la cámara trasera garantizada
                const html5QrCode = new Html5Qrcode("reader");
                html5QrCode.start(
                    selectedCameraId,
                    { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                    (decodedText) => {
                        html5QrCode.stop();
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set("qr_id", decodedText);
                        url.searchParams.delete("ocr_val");
                        window.parent.history.replaceState({}, "", url);
                        window.parent.location.reload();
                    },
                    (err) => {} // Ignorar errores de "no se encuentra QR en este frame"
                ).then(() => {
                    setTimeout(() => { document.getElementById("cam-status").style.display = 'none'; }, 1500);
                });
            }
        }).catch(err => {
            document.getElementById("cam-status").innerText = "Otorga permisos de cámara.";
        });
        </script>
        """
        components.html(html_code_qr, height=450)
        
        id_manual = st.text_input("O ingresa el ID manual:", key="input_manual")
        if id_manual:
            st.query_params["qr_id"] = id_manual
            st.rerun()

    # --- SI YA TENEMOS UN ID ESCANEADO ---
    if id_escaneado_url:
        colA, colB = st.columns([0.8, 0.2])
        with colA:
            st.info(f"🔍 **ID Detectado:** {id_escaneado_url}")
        with colB:
            if st.button("❌ Cancelar Escaneo"):
                st.query_params.clear()
                st.rerun()

        encontrado_piso = id_escaneado_url in df_piso_local['Id de producto'].values
        encontrado_mob = id_escaneado_url in df_mob_local['Id de producto'].values

        if encontrado_piso or encontrado_mob:
            hoja_activa = "PISO" if encontrado_piso else "MOBILIARIO"
            df_actual = df_piso_local if encontrado_piso else df_mob_local
            idx = df_actual[df_actual['Id de producto'] == id_escaneado_url].index[0]
            equipo = df_actual.iloc[idx]
            
            st.markdown("### 📊 Estatus Actual del Equipo")
            c_estatus, c_fecha, c_val = st.columns(3)
            
            estatus_actual = str(equipo.get('Estatus de verificación', 'N/A')).strip().upper()
            color_estatus = "🟢" if estatus_actual == "VIGENTE" else "🔴"
            
            c_estatus.metric("Estatus", f"{color_estatus} {estatus_actual}")
            c_fecha.metric("Última Verificación", str(equipo.get('Fecha de verificación', 'N/A'))[:10])
            
            val_previo = equipo.get('Valor de verificación', 0)
            c_val.metric("Última Resistencia", f"{float(val_previo):,.0f} Ω" if pd.notna(val_previo) else "N/A")
            
            st.divider()

            hacer_medicion = st.checkbox("✅ Realizar nueva medición y actualizar", value=bool(valor_ocr_detectado))
            
            if hacer_medicion:
                st.markdown("### 📷 Captura Automática del Medidor")
                
                if not valor_ocr_detectado:
                    st.write("Alinea la pantalla del medidor centrando los números de resistencia dentro del recuadro verde.")
                    
                    # --- NUEVA LÓGICA DE CÁMARA TRASERA PARA LCD (SÚPER-RESOLUCIÓN) ---
                    html_code_ocr = """
                    <script src="https://unpkg.com/tesseract.js@v4.0.3/dist/tesseract.min.js"></script>
                    <div id="ocr_scanner" style="width:100%; max-width:600px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #0052cc; background-color: #111; padding: 10px; text-align: center; color: white;">
                        
                        <div id="cam_container" style="position: relative; width: 100%; padding-bottom: 75%; overflow: hidden; border-radius: 8px; background: #000;">
                            <video id="ocr_video" autoplay playsinline muted style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;"></video>
                            
                            <div id="lcd_screen" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 90%; height: 45%; border: 2px solid rgba(0,255,0,0.5); pointer-events: none;">
                                <div id="box-ohms" style="position: absolute; top: 10%; left: 5%; width: 90%; height: 80%; border: 3px solid #00ff00;">
                                    <span style="position:absolute; top:-22px; left:0; font-size:12px; color:#00ff00; font-weight:bold;">ENFOQUE RESISTENCIA Y EXPONENTE</span>
                                </div>
                            </div>
                        </div>
                        
                        <p id="ocr_status" style="margin: 15px 0; font-size: 14px; color: #aaa;">Iniciando cámara trasera...</p>
                        
                        <button id="ocr_btn" style="width: 100%; padding: 18px; font-size: 18px; font-weight: bold; background-color: #0052cc; color: white; border: none; border-radius: 8px;">
                            📸 LEER MEDICIÓN
                        </button>
                    </div>

                    <script>
                        const video = document.getElementById('ocr_video');
                        const btn = document.getElementById('ocr_btn');
                        const status = document.getElementById('ocr_status');
                        let camStream = null;

                        async function setupCamera() {
                            try {
                                // Solicitamos cámara trasera genérica primero para que iOS nos revele las etiquetas de hardware
                                let tempStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
                                
                                const devices = await navigator.mediaDevices.enumerateDevices();
                                const cameras = devices.filter(d => d.kind === 'videoinput');
                                
                                let selectedId = null;
                                
                                // Filtrar SOLO cámaras traseras
                                const rearCams = cameras.filter(c => c.label.toLowerCase().includes('back') || c.label.toLowerCase().includes('trasera'));
                                
                                if (rearCams.length > 0) {
                                    selectedId = rearCams[0].id; // Default a la primera trasera
                                    status.innerText = "Cámara trasera lista. Alinea y lee.";
                                    
                                    // Buscar Macro trasero
                                    for (const cam of rearCams) {
                                        if (cam.label.toLowerCase().includes('ultra') || cam.label.toLowerCase().includes('macro')) {
                                            selectedId = cam.id;
                                            status.innerText = "Lente Macro trasero listo. Alinea y lee.";
                                            break;
                                        }
                                    }
                                }

                                // Detenemos el stream temporal
                                tempStream.getTracks().forEach(t => t.stop());

                                // Iniciamos la cámara definitiva elegida
                                const constraints = selectedId 
                                    ? { video: { deviceId: { exact: selectedId }, focusMode: 'continuous' } }
                                    : { video: { facingMode: 'environment', focusMode: 'continuous' } };
                                    
                                camStream = await navigator.mediaDevices.getUserMedia(constraints);
                                video.srcObject = camStream;
                                
                            } catch (e) {
                                status.innerText = "Error: " + e.message;
                            }
                        }
                        setupCamera();

                        function getHighResCrop(boxId) {
                            const box = document.getElementById(boxId);
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
                            canvas.width = cropW * 2; // Súper resolución 2X
                            canvas.height = cropH * 2;
                            const ctx = canvas.getContext('2d');
                            
                            ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, canvas.width, canvas.height);
                            
                            const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                            const data = imgData.data;
                            for (let i=0; i<data.length; i+=4) {
                                const avg = (data[i] + data[i+1] + data[i+2]) / 3;
                                const val = avg >= 130 ? 255 : 0; 
                                data[i] = data[i+1] = data[i+2] = val;
                            }
                            ctx.putImageData(imgData, 0, 0);
                            return canvas;
                        }

                        btn.addEventListener('click', async () => {
                            btn.disabled = true;
                            status.innerText = "⏳ ANALIZANDO EXPONENTE...";
                            
                            const canvas = getHighResCrop('box-ohms');
                            
                            try {
                                const worker = await Tesseract.createWorker();
                                await worker.loadLanguage('eng');
                                await worker.initialize('eng');
                                await worker.setParameters({ tessedit_char_whitelist: '0123456789.xX*Ee^ ' });
                                
                                const { data: { text } } = await worker.recognize(canvas);
                                await worker.terminate();

                                let cleaned = text.replace(/\\s+/g, '');
                                const pattern = /(\\d+\\.\\d{1,2}).*?10.*?(\\d{1,2})/;
                                const match = cleaned.match(pattern);

                                if (match) {
                                    const base = parseFloat(match[1]);
                                    const exp = parseInt(match[2]);
                                    const finalValue = base * Math.pow(10, exp);
                                    
                                    camStream.getTracks().forEach(t => t.stop());
                                    const url = new URL(window.parent.location.href);
                                    url.searchParams.set("ocr_val", finalValue);
                                    window.parent.history.replaceState({}, "", url);
                                    window.parent.location.reload();
                                } else {
                                    status.innerText = "❌ Exponente no claro. Intenta acercarte más.";
                                    status.style.color = "#ff4b4b";
                                    btn.disabled = false;
                                }
                            } catch (err) {
                                status.innerText = "Error: " + err.message;
                                btn.disabled = false;
                            }
                        });
                    </script>
                    """
                    components.html(html_code_ocr, height=700)
                    
                else:
                    st.success("✅ **Resistencia capturada:**")
                    st.metric("Nuevo Valor", f"{float(valor_ocr_detectado):,.0f} Ω")
                    
                    if st.button("🔄 Descartar y reintentar captura"):
                        if "ocr_val" in st.query_params: 
                            del st.query_params["ocr_val"]
                        st.rerun()

                st.markdown("#### Validar y Sincronizar")
                with st.form("form_actualizacion"):
                    
                    default_ohm = float(valor_ocr_detectado) if valor_ocr_detectado else float(equipo.get('Valor de verificación', 0) or 0.0)
                    nuevo_valor_final = st.number_input("Resistencia (Ohms)", value=default_ohm, format="%f")
                    
                    fecha_hoy = datetime.today().date()
                    nueva_fecha_valida = st.date_input("Fecha de medición", fecha_hoy)
                    
                    submit_corporativo = st.form_submit_button("Guardar en Google Sheets")
                    
                    if submit_corporativo:
                        with st.spinner("Guardando en la nube..."):
                            frecuencia_corp = str(equipo.get('Frecuencia de verificación', 'Anual'))
                            proxima_fecha_val = calcular_proxima_fecha(nueva_fecha_valida, frecuencia_corp)
                            
                            import gspread
                            secretos_dict_corp = dict(st.secrets["connections"]["gsheets"])
                            url_hoja_corp = secretos_dict_corp["spreadsheet"]
                            
                            gc_gspread_corp = gspread.service_account_from_dict(secretos_dict_corp)
                            doc_corp = gc_gspread_corp.open_by_url(url_hoja_corp)
                            ws_corp = doc_corp.worksheet(hoja_activa)
                            
                            try:
                                id_col_idx = df_actual.columns.get_loc('Id de producto')
                                val_col_idx = df_actual.columns.get_loc('Valor de verificación')
                                fecha_col_idx = df_actual.columns.get_loc('Fecha de verificación')
                                prox_fecha_col_idx = df_actual.columns.get_loc('Fecha de próxima verificación')
                                status_col_idx = df_actual.columns.get_loc('Estatus de verificación')
                            except KeyError as e:
                                st.error(f"Falta la columna {e}")
                                st.stop()
                            
                            columna_ids_corp = ws_corp.col_values(id_col_idx + 1)
                            row_gspread = [str(val).strip() for val in columna_ids_corp].index(str(id_escaneado_url).strip()) + 1
                            
                            ws_corp.update_cell(row_gspread, val_col_idx + 1, float(nuevo_valor_final))
                            ws_corp.update_cell(row_gspread, fecha_col_idx + 1, nueva_fecha_valida.strftime("%Y-%m-%d"))
                            ws_corp.update_cell(row_gspread, prox_fecha_col_idx + 1, proxima_fecha_val.strftime("%Y-%m-%d"))
                            ws_corp.update_cell(row_gspread, status_col_idx + 1, 'VIGENTE')

                        st.success("💾 ¡Registro de Resistencia guardado y equipo Vigente!")
                        st.cache_data.clear()
                        st.query_params.clear()
                        st.rerun()
        else:
            st.error("❌ El ID escaneado no existe.")
