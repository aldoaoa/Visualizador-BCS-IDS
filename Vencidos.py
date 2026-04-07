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

id_escaneado_url = st.query_params.get("qr_id", "")
valor_ocr_detectado = st.query_params.get("ocr_val", "")
temp_ocr_detectado = st.query_params.get("ocr_temp", "")
hum_ocr_detectado = st.query_params.get("ocr_hum", "")
volt_ocr_detectado = st.query_params.get("ocr_volts", "")

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
        
        html_code_qr = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
        <script>
        function onScanSuccess(decodedText, decodedResult) {
            html5QrcodeScanner.clear(); 
            const url = new URL(window.parent.location.href);
            url.searchParams.set("qr_id", decodedText);
            url.searchParams.delete("ocr_val"); url.searchParams.delete("ocr_temp");
            url.searchParams.delete("ocr_hum"); url.searchParams.delete("ocr_volts");
            window.parent.history.replaceState({}, "", url);
            window.parent.location.reload();
        }
        let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 15, qrbox: {width: 250, height: 250}, aspectRatio: 1.0 }, false);
        html5QrcodeScanner.render(onScanSuccess);
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
            
            # --- SECCIÓN 1: MOSTRAR ESTATUS ACTUAL ANTES DE MEDIR ---
            st.markdown("### 📊 Estatus Actual del Equipo")
            c_estatus, c_fecha, c_val = st.columns(3)
            
            estatus_actual = str(equipo.get('Estatus de verificación', 'N/A')).strip().upper()
            color_estatus = "🟢" if estatus_actual == "VIGENTE" else "🔴"
            
            c_estatus.metric("Estatus", f"{color_estatus} {estatus_actual}")
            c_fecha.metric("Última Verificación", str(equipo.get('Fecha de verificación', 'N/A'))[:10])
            
            val_previo = equipo.get('Valor de verificación', 0)
            c_val.metric("Última Resistencia Registrada", f"{float(val_previo):,.0f} Ω" if pd.notna(val_previo) else "N/A")
            
            st.divider()

            # --- SECCIÓN 2: DECISIÓN DE NUEVA MEDICIÓN ---
            hacer_medicion = st.checkbox("✅ Realizar nueva medición y actualizar valores", value=bool(valor_ocr_detectado))
            
            if hacer_medicion:
                st.markdown("### 📷 Captura Automática de Pantalla LCD (AOI)")
                
                if not valor_ocr_detectado:
                    st.write("Alinea la pantalla del medidor exactamente con los cuadros de colores correspondientes.")
                    
                    html_code_ocr = """
                    <script src="https://unpkg.com/tesseract.js@v4.0.3/dist/tesseract.min.js"></script>
                    <div id="ocr_scanner" style="width:100%; max-width:600px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #555; background-color: #222; padding: 10px; text-align: center; color: white;">
                        
                        <div id="cam_container" style="position: relative; width: 100%; padding-bottom: 75%; overflow: hidden; border-radius: 8px; background: #000;">
                            <video id="ocr_video" autoplay playsinline style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;"></video>
                            
                            <div id="lcd_screen" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 85%; height: 50%; border: 3px solid rgba(255,255,255,0.8); background: rgba(0,0,0,0.3); pointer-events: none; border-radius: 8px;">
                                
                                <div id="box-volt" style="position: absolute; top: 5%; left: 2%; width: 20%; height: 25%; border: 3px solid red; background: transparent;">
                                    <span style="position:absolute; top:-20px; left:0; font-size:12px; color:red; background:black; padding:0 4px; font-weight:bold;">VOLTS</span>
                                </div>
                                
                                <div id="box-temp" style="position: absolute; top: 5%; left: 45%; width: 22%; height: 25%; border: 3px solid #a020f0; background: transparent;">
                                    <span style="position:absolute; top:-20px; left:0; font-size:12px; color:#a020f0; background:black; padding:0 4px; font-weight:bold;">TEMP</span>
                                </div>

                                <div id="box-hum" style="position: absolute; top: 5%; left: 70%; width: 25%; height: 25%; border: 3px solid #8b4513; background: transparent;">
                                    <span style="position:absolute; top:-20px; left:0; font-size:12px; color:#8b4513; background:black; padding:0 4px; font-weight:bold;">HUM</span>
                                </div>
                                
                                <div id="box-ohms" style="position: absolute; top: 35%; left: 2%; width: 95%; height: 60%; border: 3px solid #0052cc; background: transparent;">
                                    <span style="position:absolute; top:-20px; left:0; font-size:12px; color:#0052cc; background:black; padding:0 4px; font-weight:bold;">RESISTENCIA</span>
                                </div>
                            </div>
                        </div>
                        
                        <p id="ocr_status" style="margin: 15px 0; font-weight: bold; font-size: 14px;">Alinea los números en sus colores y presiona Leer...</p>
                        
                        <button id="ocr_btn" style="width: 100%; padding: 15px; font-size: 18px; font-weight: bold; background-color: #28a745; color: white; border: none; border-radius: 8px; cursor: pointer;">
                            📸 LEER PANTALLA LCD
                        </button>
                    </div>
                    <script>
                        const video = document.getElementById('ocr_video');
                        const btn = document.getElementById('ocr_btn');
                        const status = document.getElementById('ocr_status');
                        let camStream = null;

                        async function setupCamera() {
                            try {
                                const constraints = { video: { facingMode: 'environment', focusMode: 'continuous' } };
                                camStream = await navigator.mediaDevices.getUserMedia(constraints);
                                video.srcObject = camStream;
                            } catch (err) {
                                status.innerText = "Error accediendo a la cámara.";
                            }
                        }
                        setupCamera();

                        function getCroppedCanvas(boxId) {
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
                            canvas.width = cropW;
                            canvas.height = cropH;
                            const ctx = canvas.getContext('2d');
                            
                            ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);
                            
                            // Inversión de color estricta para LCD (Gris/Blanco a Negro Puro)
                            const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                            const data = imgData.data;
                            let sum = 0;
                            for (let i=0; i<data.length; i+=4) sum += (data[i] + data[i+1] + data[i+2]) / 3;
                            const threshold = (sum / (canvas.width * canvas.height)) * 0.95; // Corte alto para asegurar que solo los números queden claros
                            
                            for (let i=0; i<data.length; i+=4) {
                                const avg = (data[i] + data[i+1] + data[i+2]) / 3;
                                const val = avg >= threshold ? 0 : 255; // INVERSIÓN
                                data[i] = data[i+1] = data[i+2] = val;
                            }
                            ctx.putImageData(imgData, 0, 0);
                            return canvas;
                        }

                        btn.addEventListener('click', async () => {
                            if (!camStream) { setupCamera(); return; }
                            btn.disabled = true;
                            status.innerText = "📸 Capturando Zonas...";
                            
                            const canvasOhms = getCroppedCanvas('box-ohms');
                            const canvasTemp = getCroppedCanvas('box-temp');
                            const canvasHum  = getCroppedCanvas('box-hum');
                            const canvasVolt = getCroppedCanvas('box-volt');
                            
                            try {
                                const worker = await Tesseract.createWorker({
                                    logger: m => { if(m.status === 'recognizing text') status.innerText = `Analizando LCD... ${Math.round(m.progress * 100)}%`; }
                                });
                                await worker.loadLanguage('eng');
                                await worker.initialize('eng');

                                // 1. VOLTAJE (Solo números)
                                await worker.setParameters({ tessedit_char_whitelist: '0123456789' });
                                let { data: { text: textVolt } } = await worker.recognize(canvasVolt);
                                let valVolt = parseInt(textVolt.replace(/[^0-9]/g, ''));

                                // 2. TEMP (Números y punto)
                                await worker.setParameters({ tessedit_char_whitelist: '0123456789.' });
                                let { data: { text: textTemp } } = await worker.recognize(canvasTemp);
                                let valTemp = parseFloat(textTemp.replace(/[^0-9.]/g, ''));

                                // 3. HUMEDAD (Números y punto)
                                let { data: { text: textHum } } = await worker.recognize(canvasHum);
                                let valHum = parseFloat(textHum.replace(/[^0-9.]/g, ''));

                                // 4. RESISTENCIA (Alfanumérico)
                                await worker.setParameters({ tessedit_char_whitelist: '0123456789.xX*Ee^ ' });
                                let { data: { text: textOhms } } = await worker.recognize(canvasOhms);
                                textOhms = textOhms.replace(/\\s+/g, '');
                                
                                let valOhms = null;
                                const matchSci = textOhms.match(/(\\d+\\.?\\d*)[xX*eE]1?0?\\^?(\\d+)/);
                                if (matchSci) {
                                    let base = parseFloat(matchSci[1]);
                                    let exp = parseInt(matchSci[2]);
                                    if (exp < 20) valOhms = base * Math.pow(10, exp);
                                }

                                await worker.terminate();
                                camStream.getTracks().forEach(track => track.stop());

                                if (valOhms) {
                                    status.innerText = "✅ Valores extraídos con éxito";
                                    status.style.color = "#28a745";
                                    
                                    const url = new URL(window.parent.location.href);
                                    url.searchParams.set("ocr_val", valOhms);
                                    if (!isNaN(valTemp)) url.searchParams.set("ocr_temp", valTemp);
                                    if (!isNaN(valHum)) url.searchParams.set("ocr_hum", valHum);
                                    if (!isNaN(valVolt) && (valVolt === 10 || valVolt === 100)) url.searchParams.set("ocr_volts", valVolt);
                                    
                                    window.parent.history.replaceState({}, "", url);
                                    window.parent.location.reload();
                                } else {
                                    status.innerText = `❌ No se detectó Resistencia. Leído: [${textOhms}]`;
                                    status.style.color = "#dc3545";
                                    btn.disabled = false;
                                    btn.innerText = "🔄 REINTENTAR";
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
                    st.success("✅ **Valores capturados por AOI:**")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Resistencia", f"{float(valor_ocr_detectado):,.0f} Ω")
                    if temp_ocr_detectado: c2.metric("Temp", f"{temp_ocr_detectado} °C")
                    if hum_ocr_detectado: c3.metric("Humedad", f"{hum_ocr_detectado} %")
                    if volt_ocr_detectado: c4.metric("Voltaje", f"{volt_ocr_detectado} V")
                    
                    if st.button("🔄 Descartar y reintentar captura"):
                        for key in ["ocr_val", "ocr_temp", "ocr_hum", "ocr_volts"]:
                            if key in st.query_params: del st.query_params[key]
                        st.rerun()

                st.markdown("#### Validar Datos y Sincronizar")
                with st.form("form_actualizacion"):
                    col_ohm, col_volt = st.columns(2)
                    default_ohm = float(valor_ocr_detectado) if valor_ocr_detectado else float(equipo.get('Valor de verificación', 0) or 0.0)
                    nuevo_valor_final = col_ohm.number_input("Resistencia (Ohms)", value=default_ohm, format="%f")
                    
                    idx_volt = 1 if volt_ocr_detectado == "100" else 0
                    nuevo_voltaje = col_volt.selectbox("Voltaje de prueba (V)", options=[10, 100], index=idx_volt)
                    
                    col_temp, col_hum = st.columns(2)
                    default_temp = float(temp_ocr_detectado) if temp_ocr_detectado else 23.0
                    nueva_temp = col_temp.number_input("Temperatura (°C)", value=default_temp, step=0.1)
                    
                    default_hum = float(hum_ocr_detectado) if hum_ocr_detectado else 50.0
                    nueva_hum = col_hum.number_input("Humedad relativa (%)", value=default_hum, step=0.1)
                    
                    fecha_hoy = datetime.today().date()
                    nueva_fecha_valida = st.date_input("Fecha de validación", fecha_hoy)
                    
                    submit_corporativo = st.form_submit_button("Sincronizar con Google Sheets")
                    
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
                                temp_col_idx = df_actual.columns.get_loc('Temperatura (°C)')
                                hum_col_idx = df_actual.columns.get_loc('Humedad relativa (%)')
                                volt_col_idx = df_actual.columns.get_loc('Voltaje de prueba (V)')
                                fecha_col_idx = df_actual.columns.get_loc('Fecha de verificación')
                                prox_fecha_col_idx = df_actual.columns.get_loc('Fecha de próxima verificación')
                                status_col_idx = df_actual.columns.get_loc('Estatus de verificación')
                            except KeyError as e:
                                st.error(f"Falta la columna {e}")
                                st.stop()
                            
                            columna_ids_corp = ws_corp.col_values(id_col_idx + 1)
                            row_gspread = [str(val).strip() for val in columna_ids_corp].index(str(id_escaneado_url).strip()) + 1
                            
                            ws_corp.update_cell(row_gspread, val_col_idx + 1, float(nuevo_valor_final))
                            ws_corp.update_cell(row_gspread, temp_col_idx + 1, float(nueva_temp))
                            ws_corp.update_cell(row_gspread, hum_col_idx + 1, float(nueva_hum))
                            ws_corp.update_cell(row_gspread, volt_col_idx + 1, int(nuevo_voltaje))
                            ws_corp.update_cell(row_gspread, fecha_col_idx + 1, nueva_fecha_valida.strftime("%Y-%m-%d"))
                            ws_corp.update_cell(row_gspread, prox_fecha_col_idx + 1, proxima_fecha_val.strftime("%Y-%m-%d"))
                            ws_corp.update_cell(row_gspread, status_col_idx + 1, 'VIGENTE')

                        st.success("💾 ¡Registro guardado!")
                        st.cache_data.clear()
                        st.query_params.clear()
                        st.rerun()
        else:
            st.error("❌ El ID escaneado no existe.")
