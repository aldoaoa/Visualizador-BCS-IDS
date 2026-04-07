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
        st.error(f"Error de conexión con la nube corporativa de Google Sheets: {e}")
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

# Captura de parámetros URL (Ahora incluyendo ambientales y voltaje)
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
    st.info("☁️ Los datos mostrados están sincronizados en tiempo real con Google Sheets para todos los usuarios.")
    
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
        
        st.markdown("### Mapa de Ubicaciones Corporativas")
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
                fig.update_traces(
                    textposition='middle center', textfont=dict(color='white', size=12, weight='bold'),
                    marker=dict(symbol='square', size=50, opacity=0.9, line=dict(width=2, color='DarkSlateGrey'))
                )
                fig.update_layout(
                    images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")],
                    xaxis=dict(showgrid=False, zeroline=False, range=[0, width], visible=False),
                    yaxis=dict(showgrid=False, zeroline=False, range=[height, 0], visible=False, scaleanchor="x", scaleratio=1),
                    margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No hay coincidencias con el archivo de coordenadas corporativas.")
            del img, df_coords, mapa_data, fig
            gc.collect()
        else:
            st.info(f"📌 Falta cargar '{RUTA_MAPA}' o '{RUTA_COORDENADAS}' en el repositorio.")
            
        st.markdown("### Detalles de Equipos fuera de cumplimiento")
        columnas_mostrar = ['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación', 'Estatus operativo', 'Hoja Origen']
        st.dataframe(vencidos[[col for col in columnas_mostrar if col in vencidos.columns]], use_container_width=True, hide_index=True)
    else:
        st.success("✅ ¡Felicidades! No hay equipos operativos corporativos con estatus 'VENCIDO'.")
    
    del df_piso_mapa, df_mob_mapa, df_total, vencidos
    gc.collect()

# ==========================================
# VISTA 2: ESCÁNER Y ACTUALIZACIÓN NATIVA
# ==========================================
elif st.session_state.vista_actual == "Escáner":
    
    if not id_escaneado_url:
        st.markdown("### 📷 Apunta al Código QR Corporativo")
        st.write("Concede permiso a la cámara en tu iPhone. El escaneo es automático y cargará los detalles.")
        
        html_code_qr = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
        <script>
        function onScanSuccess(decodedText, decodedResult) {
            html5QrcodeScanner.clear(); 
            const url = new URL(window.parent.location.href);
            url.searchParams.set("qr_id", decodedText);
            // Limpiamos OCRs previos
            url.searchParams.delete("ocr_val");
            url.searchParams.delete("ocr_temp");
            url.searchParams.delete("ocr_hum");
            url.searchParams.delete("ocr_volts");
            window.parent.history.replaceState({}, "", url);
            window.parent.location.reload();
        }
        
        let html5QrcodeScanner = new Html5QrcodeScanner(
          "reader", 
          { fps: 15, qrbox: {width: 250, height: 250}, aspectRatio: 1.0 }, 
          false
        );
        html5QrcodeScanner.render(onScanSuccess);
        </script>
        """
        components.html(html_code_qr, height=450)
        
        st.markdown("O ingresa el ID manual:")
        id_manual = st.text_input("Ingresar ID manual corporativo:", key="input_manual")
        if id_manual:
            st.query_params["qr_id"] = id_manual
            st.rerun()

    if id_escaneado_url:
        colA, colB = st.columns([0.8, 0.2])
        with colA:
            st.info(f"🔍 **ID Corporativo Detectado:** {id_escaneado_url}")
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
            
            st.divider()
            
            # --- SECCIÓN: ESCÁNER DE PANTALLA DEL MEDIDOR MULTIPARÁMETRO (OCR) ---
            st.markdown("### 📷 Captura Automática del Medidor (OCR)")
            
            if not valor_ocr_detectado:
                st.write("Toma una foto de la pantalla del medidor. Se intentará leer Resistencia, Temp, HR y Voltaje.")
                
                html_code_ocr = """
                <script src="https://unpkg.com/tesseract.js@v4.0.3/dist/tesseract.min.js"></script>
                <div id="ocr_scanner" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 3px solid #0052cc; background-color: #222; padding: 10px; text-align: center; color: white;">
                    
                    <div id="cam_container" style="position: relative; width: 100%; padding-bottom: 75%; overflow: hidden; border-radius: 8px; background: #000;">
                        <video id="ocr_video" autoplay playsinline style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;"></video>
                        
                        <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); pointer-events: none;">
                            <div id="box-ohms" style="position: absolute; top: 15%; left: 10%; width: 80%; height: 35%; border: 3px solid #00ff00; background: transparent; box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);">
                                <span style="position:absolute; top:-20px; left:0; font-size:12px; color:#00ff00; background:black; padding:2px 5px;">RESISTENCIA (A x 10^B)</span>
                            </div>
                            
                            <div id="box-temp" style="position: absolute; top: 60%; left: 10%; width: 25%; height: 25%; border: 2px dashed #00ffff; background: transparent;">
                                <span style="position:absolute; bottom:-20px; left:0; font-size:10px; color:#00ffff; background:black;">TEMP</span>
                            </div>
                            <div id="box-hum" style="position: absolute; top: 60%; left: 37.5%; width: 25%; height: 25%; border: 2px dashed #ff00ff; background: transparent;">
                                <span style="position:absolute; bottom:-20px; left:0; font-size:10px; color:#ff00ff; background:black;">HUM</span>
                            </div>
                            <div id="box-volt" style="position: absolute; top: 60%; left: 65%; width: 25%; height: 25%; border: 2px dashed #ffff00; background: transparent;">
                                <span style="position:absolute; bottom:-20px; left:0; font-size:10px; color:#ffff00; background:black;">VOLTS</span>
                            </div>
                        </div>
                    </div>
                    
                    <p id="ocr_status" style="margin: 15px 0; font-weight: bold; font-size: 14px;">Alinea los números en sus cajas y presiona leer...</p>
                    
                    <button id="ocr_btn" style="width: 100%; padding: 15px; font-size: 18px; font-weight: bold; background-color: #0052cc; color: white; border: none; border-radius: 8px; cursor: pointer;">
                        📸 LEER CON PLANTILLA
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

                    // Función para extraer y procesar un recorte (ROI) del video
                    function getCroppedCanvas(boxId) {
                        const box = document.getElementById(boxId);
                        const container = document.getElementById('cam_container');
                        
                        // Calcular proporciones relativas
                        const rectBox = box.getBoundingClientRect();
                        const rectCont = container.getBoundingClientRect();
                        
                        const relX = (rectBox.left - rectCont.left) / rectCont.width;
                        const relY = (rectBox.top - rectCont.top) / rectCont.height;
                        const relW = rectBox.width / rectCont.width;
                        const relH = rectBox.height / rectCont.height;
                        
                        // Pixeles reales en el video
                        const cropX = video.videoWidth * relX;
                        const cropY = video.videoHeight * relY;
                        const cropW = video.videoWidth * relW;
                        const cropH = video.videoHeight * relH;

                        const canvas = document.createElement('canvas');
                        canvas.width = cropW;
                        canvas.height = cropH;
                        const ctx = canvas.getContext('2d');
                        
                        // Recortar la región exacta
                        ctx.drawImage(video, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);
                        
                        // Filtro de binarización extremo (Ideal para LCDs de 7 segmentos)
                        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        const data = imgData.data;
                        let sum = 0;
                        for (let i=0; i<data.length; i+=4) sum += (data[i] + data[i+1] + data[i+2]) / 3;
                        const threshold = (sum / (canvas.width * canvas.height)) * 0.90; // Contraste agresivo
                        
                        for (let i=0; i<data.length; i+=4) {
                            const avg = (data[i] + data[i+1] + data[i+2]) / 3;
                            // Invertimos los colores (LCDs oscuros sobre fondo claro se leen mejor como texto blanco sobre negro en Tesseract)
                            const val = avg >= threshold ? 0 : 255; 
                            data[i] = data[i+1] = data[i+2] = val;
                        }
                        ctx.putImageData(imgData, 0, 0);
                        return canvas;
                    }

                    btn.addEventListener('click', async () => {
                        if (!camStream) { setupCamera(); return; }
                        btn.disabled = true;
                        
                        // 1. Extraemos los 4 recortes inmediatamente para que no haya movimiento de la mano
                        status.innerText = "📸 Capturando ROIs...";
                        const canvasOhms = getCroppedCanvas('box-ohms');
                        const canvasTemp = getCroppedCanvas('box-temp');
                        const canvasHum  = getCroppedCanvas('box-hum');
                        const canvasVolt = getCroppedCanvas('box-volt');
                        
                        try {
                            const worker = await Tesseract.createWorker({
                                logger: m => { if(m.status === 'recognizing text') status.innerText = `Analizando... ${Math.round(m.progress * 100)}%`; }
                            });
                            await worker.loadLanguage('eng');
                            await worker.initialize('eng');

                            // --- LECTURA 1: RESISTENCIA ---
                            // Permitimos la "x" y la "e"
                            await worker.setParameters({ tessedit_char_whitelist: '0123456789.xX*Ee^ ' });
                            let { data: { text: textOhms } } = await worker.recognize(canvasOhms);
                            textOhms = textOhms.replace(/\\s+/g, ''); // Limpiar espacios
                            
                            // Extraer resistencia
                            let valOhms = null;
                            const matchSci = textOhms.match(/(\\d+\\.?\\d*)[xX*eE]1?0?\\^?(\\d+)/);
                            if (matchSci) {
                                let base = parseFloat(matchSci[1]);
                                let exp = parseInt(matchSci[2]);
                                if (exp < 20) valOhms = base * Math.pow(10, exp);
                            }

                            // --- LECTURA 2: TEMPERATURA ---
                            // Estricto: Solo números y el punto. Eliminamos la "C" del diccionario para evitar que se confunda con el "0"
                            await worker.setParameters({ tessedit_char_whitelist: '0123456789.' });
                            let { data: { text: textTemp } } = await worker.recognize(canvasTemp);
                            let valTemp = parseFloat(textTemp.replace(/[^0-9.]/g, ''));

                            // --- LECTURA 3: HUMEDAD ---
                            let { data: { text: textHum } } = await worker.recognize(canvasHum);
                            let valHum = parseFloat(textHum.replace(/[^0-9.]/g, ''));

                            // --- LECTURA 4: VOLTAJE ---
                            let { data: { text: textVolt } } = await worker.recognize(canvasVolt);
                            let valVolt = parseInt(textVolt.replace(/[^0-9]/g, ''));

                            await worker.terminate();
                            camStream.getTracks().forEach(track => track.stop());

                            if (valOhms) {
                                status.innerText = "✅ Valores extraídos con éxito";
                                status.style.color = "#00ff00";
                                
                                const url = new URL(window.parent.location.href);
                                url.searchParams.set("ocr_val", valOhms);
                                if (!isNaN(valTemp)) url.searchParams.set("ocr_temp", valTemp);
                                if (!isNaN(valHum)) url.searchParams.set("ocr_hum", valHum);
                                if (!isNaN(valVolt) && (valVolt === 10 || valVolt === 100)) url.searchParams.set("ocr_volts", valVolt);
                                
                                window.parent.history.replaceState({}, "", url);
                                window.parent.location.reload();
                            } else {
                                status.innerText = `❌ No se detectó Resistencia. Leído: [${textOhms}]`;
                                status.style.color = "#ff3333";
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
                components.html(html_code_ocr, height=650)
                
            else:
                st.success("✅ **Valores detectados por OCR:**")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Resistencia", f"{float(valor_ocr_detectado):,.0f} Ω")
                if temp_ocr_detectado: c2.metric("Temp", f"{temp_ocr_detectado} °C")
                if hum_ocr_detectado: c3.metric("Humedad", f"{hum_ocr_detectado} %")
                if volt_ocr_detectado: c4.metric("Voltaje", f"{volt_ocr_detectado} V")
                
                if st.button("🔄 Descartar y reintentar foto"):
                    # Limpiamos todos los valores OCR de la URL
                    for key in ["ocr_val", "ocr_temp", "ocr_hum", "ocr_volts"]:
                        if key in st.query_params: del st.query_params[key]
                    st.rerun()

            st.divider()

            # --- FORMULARIO DE ACTUALIZACIÓN CON VARIABLES AMBIENTALES ---
            st.markdown("#### Validar Datos ESD y Sincronizar")
            with st.form("form_actualizacion"):
                
                col_ohm, col_volt = st.columns(2)
                # Resistencia
                default_ohm = float(valor_ocr_detectado) if valor_ocr_detectado else (float(equipo.get('Valor de verificación', 0)) if pd.notna(equipo.get('Valor de verificación')) else 0.0)
                nuevo_valor_final = col_ohm.number_input("Resistencia (Ohms)", value=default_ohm, format="%f")
                
                # Voltaje
                idx_volt = 1 if volt_ocr_detectado == "100" else 0
                nuevo_voltaje = col_volt.selectbox("Voltaje de prueba (V)", options=[10, 100], index=idx_volt)
                
                col_temp, col_hum = st.columns(2)
                # Temperatura
                default_temp = float(temp_ocr_detectado) if temp_ocr_detectado else 23.0
                nueva_temp = col_temp.number_input("Temperatura (°C)", value=default_temp, step=0.1)
                
                # Humedad
                default_hum = float(hum_ocr_detectado) if hum_ocr_detectado else 50.0
                nueva_hum = col_hum.number_input("Humedad relativa (%)", value=default_hum, step=0.1)
                
                fecha_hoy = datetime.today().date()
                nueva_fecha_valida = st.date_input("Fecha de validación", fecha_hoy)
                
                submit_corporativo = st.form_submit_button("Sincronizar mediciones y variables con Google Sheets")
                
                if submit_corporativo:
                    with st.spinner("Guardando registro completo S20.20 en la nube..."):
                        frecuencia_corp = str(equipo.get('Frecuencia de verificación', 'Anual'))
                        proxima_fecha_val = calcular_proxima_fecha(nueva_fecha_valida, frecuencia_corp)
                        
                        import gspread
                        secretos_dict_corp = dict(st.secrets["connections"]["gsheets"])
                        url_hoja_corp = secretos_dict_corp["spreadsheet"]
                        
                        gc_gspread_corp = gspread.service_account_from_dict(secretos_dict_corp)
                        doc_corp = gc_gspread_corp.open_by_url(url_hoja_corp)
                        ws_corp = doc_corp.worksheet(hoja_activa)
                        
                        # Coordenadas numéricas de las columnas (Validando que existan)
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
                            st.error(f"❌ Error crítico: Falta la columna {e} en la hoja {hoja_activa}. Revisa que los nombres coincidan exactamente con las instrucciones.")
                            st.stop()
                        
                        columna_ids_corp = ws_corp.col_values(id_col_idx + 1)
                        columna_ids_corp_limpia = [str(val).strip() for val in columna_ids_corp]
                        row_gspread = columna_ids_corp_limpia.index(str(id_escaneado_url).strip()) + 1
                        
                        # Inyectamos TODOS los datos recolectados
                        ws_corp.update_cell(row_gspread, val_col_idx + 1, float(nuevo_valor_final))
                        ws_corp.update_cell(row_gspread, temp_col_idx + 1, float(nueva_temp))
                        ws_corp.update_cell(row_gspread, hum_col_idx + 1, float(nueva_hum))
                        ws_corp.update_cell(row_gspread, volt_col_idx + 1, int(nuevo_voltaje))
                        ws_corp.update_cell(row_gspread, fecha_col_idx + 1, nueva_fecha_valida.strftime("%Y-%m-%d"))
                        ws_corp.update_cell(row_gspread, prox_fecha_col_idx + 1, proxima_fecha_val.strftime("%Y-%m-%d"))
                        ws_corp.update_cell(row_gspread, status_col_idx + 1, 'VIGENTE')

                    st.success("💾 ¡Registro S20.20 exitoso! Medición y condiciones ambientales guardadas.")
                    st.cache_data.clear()
                    
                    st.query_params.clear()
                    st.rerun()

        else:
            st.error("❌ El ID corporativo escaneado no existe en el sistema.")
