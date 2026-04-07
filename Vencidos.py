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

# Configuración horizontal (Wide) para iPhone corporativo
st.set_page_config(page_title="Control ESD Corporativo S20.20", layout="wide")

RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"

# --- CONEXIÓN A GOOGLE SHEETS EN TIEMPO REAL ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=2, max_entries=1) 
def cargar_datos_cloud():
    try:
        # Cargamos los datos interpretando la fila 5 (índice 4) como encabezados corporativos
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
    st.warning("⚠️ Asegúrate de haber compartido la Google Sheet Corporativa con el correo de la cuenta de servicio de Streamlit (Editor) y que el archivo esté en formato nativo de Google Sheets.")
    st.stop()

# --- CONTROL DE NAVEGACIÓN CORPORATIVA TIPO MÓVIL ---
if "vista_actual" not in st.session_state:
    st.session_state.vista_actual = "Mapa"

id_escaneado_url = st.query_params.get("qr_id", "")
valor_ocr_detectado = st.query_params.get("ocr_val", "")

# Si el HTML5 inyectó el QR o el valor OCR en la URL, forzamos ir a la vista del escáner
if id_escaneado_url or valor_ocr_detectado:
    st.session_state.vista_actual = "Escáner"

# Barra de navegación tipo app nativa
col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    if st.button("🗺️ Mapa y Reportes ESD", use_container_width=True, type="primary" if st.session_state.vista_actual == "Mapa" else "secondary"):
        st.session_state.vista_actual = "Mapa"
        st.query_params.clear() # Limpia cualquier escaneo en proceso
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
        
        # Componente HTML5 nativo optimizado para iPhone corporativo para leer QR
        html_code_qr = """
        <script src="https://unpkg.com/html5-qrcode"></script>
        <div id="reader" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
        <script>
        function onScanSuccess(decodedText, decodedResult) {
            html5QrcodeScanner.clear(); 
            const url = new URL(window.parent.location.href);
            url.searchParams.set("qr_id", decodedText);
            // Limpiamos cualquier OCR previo
            url.searchParams.delete("ocr_val");
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

    # Si hay un QR ID detectado, procedemos a mostrar detalles y permitir actualización
    if id_escaneado_url:
        colA, colB = st.columns([0.8, 0.2])
        with colA:
            st.info(f"🔍 **ID Corporativo Detectado:** {id_escaneado_url}")
        with colB:
            if st.button("❌ Cancelar Escaneo"):
                st.query_params.clear()
                st.rerun()

        # Buscar en qué hoja corporativa está el equipo
        encontrado_piso = id_escaneado_url in df_piso_local['Id de producto'].values
        encontrado_mob = id_escaneado_url in df_mob_local['Id de producto'].values

        if encontrado_piso or encontrado_mob:
            hoja_activa = "PISO" if encontrado_piso else "MOBILIARIO"
            df_actual = df_piso_local if encontrado_piso else df_mob_local
            
            idx = df_actual[df_actual['Id de producto'] == id_escaneado_url].index[0]
            equipo = df_actual.iloc[idx]
            
            st.divider()
            
            # --- SECCIÓN NUEVA: ESCÁNER DE PANTALLA DEL MEDIDOR (OCR) ---
            st.markdown("### 📷 Actualización por Imagen Corporativa (OCR)")
            
            # Solo mostramos el escáner si no hemos capturado un valor OCR previamente en esta sesión de actualización
            if not valor_ocr_detectado:
                st.write("Concede permiso y **toma una foto nítida de la pantalla del medidor**. El iPhone procesará la imagen localmente buscando el formato $A \\times 10^B$ (ej. 3.20x10^8).")
                
                # Componente HTML5/JavaScript avanzado que corre 100% en el iPhone
                # Toma una foto, usa CamanJS para pre-procesar (blanco y negro/contraste) y Tesseract.js para OCR.
                # Al final, calcula el valor Ohms e inyecta en la URL para actualizar Streamlit.
                html_code_ocr = """
                <script src="https://unpkg.com/tesseract.js@v4.0.3/dist/tesseract.min.js"></script>
                <div id="ocr_scanner" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 3px solid # primary; background-color: white; padding: 10px; text-align: center;">
                    
                    <div id="cam_container" style="position: relative; width: 100%; padding-bottom: 75%; overflow: hidden; border-radius: 8px;">
                        <video id="ocr_video" autoplay playsinline style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover;"></video>
                        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 70%; height: 30%; border: 4px solid #primary; border-radius: 5px; box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.4); pointer-events: none;"></div>
                    </div>
                    
                    <p id="ocr_status" style="margin: 10px 0; font-weight: bold; color: #555;">Listo para escanear medidor...</p>
                    
                    <button id="ocr_btn" style="width: 100%; padding: 15px; font-size: 18px; font-weight: bold; background-color: #primary; color: white; border: none; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        📸 TOMAR FOTO DE PANTALLA
                    </button>
                    
                    <canvas id="ocr_canvas" style="display: none;"></canvas>
                </div>
                <script>
                    const video = document.getElementById('ocr_video');
                    const canvas = document.getElementById('ocr_canvas');
                    const btn = document.getElementById('ocr_btn');
                    const status = document.getElementById('ocr_status');
                    let camStream = null;

                    // 1. Setup Cámara Nítida para iPhone Corporativo
                    async function setupCamera() {
                        status.innerText = "Accediendo a cámara nítida...";
                        try {
                            const constraints = {
                                video: {
                                    facingMode: 'environment', // Usar cámara trasera
                                    focusMode: 'continuous', // Asegurar enfoque nítido de la pantalla
                                    whiteBalanceMode: 'continuous',
                                    exposureMode: 'continuous',
                                    frameRate: { max: 30 }
                                },
                                audio: false
                            };
                            camStream = await navigator.mediaDevices.getUserMedia(constraints);
                            video.srcObject = camStream;
                        } catch (err) {
                            status.innerText = "Error accediendo a cámara. Verifica permisos.";
                            status.style.color = "red";
                            console.error("Camera access error:", err);
                        }
                    }

                    setupCamera();

                    // 2. Función de Análisis Heurístico para formato ANSI/ESD de la muestra
                    function parseResistanceMeter(text) {
                        // Limpieza corporativa: quitar espacios, cambiar comas por puntos (errores comunes de OCR)
                        let cleaned = text.replace(/\s+/g, '').replace(/,/g, '.');
                        status.innerText = "Procesando heurística de medidor... Texto crudo: " + text.substring(0, 30);
                        
                        // Heurística de la muestra: Digitos . Digitos X (o x) 10 ^ (opcional) Digitos
                        const pattern = /(\d+\.?\d*)\s*[xX]\s*10\s*[\^\s]*(\d+)/;
                        const match = cleaned.match(pattern);
                        
                        if (match) {
                            const base = parseFloat(match[1]);
                            const exp = parseInt(match[2]);
                            
                            // Validaciones corporativas de seguridad (ej. exp < 20 para evitar números imposibles)
                            if (!isNaN(base) && !isNaN(exp) && exp < 20) {
                                return base * Math.pow(10, exp);
                            }
                        }
                        
                        // Plan B: Buscar solo notación científica estándar (ej. 3.20E8) por si el medidor cambió
                        const patternSci = /(\d+\.?\d*)\s*[eE]\s*(\d+)/;
                        const matchSci = cleaned.match(patternSci);
                        if(matchSci) {
                            const baseSci = parseFloat(matchSci[1]);
                            const expSci = parseInt(matchSci[2]);
                            return baseSci * Math.pow(10, expSci);
                        }

                        return null;
                    }

                    // 3. Lógica de Captura y Procesamiento OCR (Corre 100% en el iPhone)
                    btn.addEventListener('click', async () => {
                        if (!camStream) {
                            setupCamera();
                            return;
                        }
                        btn.disabled = true;
                        btn.innerText = "⏳ PROCESANDO IMAGEN EN IPHONE...";
                        status.innerText = "Capturando imagen nítida de pantalla...";
                        status.style.color = "# primary";

                        // Dibujar frame en canvas con alta resolución (usando tamaño real de video)
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                        // APICAR PRE-PROCESADO EN CLIENTE (iPhone)
                        // Para Tesseract, el OCR funciona mejor en Blanco y Negro puro (Threshold)
                        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        const data = imgData.data;
                        // Brillo/Contraste heurístico para pantallas corporativas
                        const threshold = 128; // Punto de corte (50%)
                        for (let i = 0; i < data.length; i += 4) {
                            const avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
                            // Blanco y negro puro (Binarización)
                            const val = avg >= threshold ? 255 : 0;
                            data[i] = val; // red
                            data[i+1] = val; // green
                            data[i+2] = val; // blue
                        }
                        ctx.putImageData(imgData, 0, 0);
                        status.innerText = "Aplicando Blanco y Negro corporativo...";
                        
                        // EJECUTAR OCR CON TESSERACT.JS (100% en iPhone)
                        status.innerText = "Analizando texto en iPhone (Visión Artificial)...";
                        try {
                            const worker = await Tesseract.createWorker({
                                // Solo necesitamos español y números para medidores corporativos
                                logger: m => {
                                    if(m.status == 'recognizing text') {
                                        status.innerText = "Analizando caracteres corporativos... " + (Math.round(m.progress * 100)) + "%";
                                    }
                                }
                            });
                            await worker.loadLanguage('eng'); // Inglés por defecto para números
                            await worker.initialize('eng');
                            // Parámetros de configuración corporativa de Tesseract: whitelist numérica
                            await worker.setParameters({
                                tessedit_char_whitelist: '0123456789.x10^EXoΩ',
                            });
                            
                            // Ejecutar reconocimiento corporativo en el canvas Blanco y Negro
                            const { data: { text } } = await worker.recognize(canvas);
                            await worker.terminate();

                            // 4. Analizar Resultado
                            const valOhms = parseResistanceMeter(text);
                            
                            if (valOhms) {
                                status.innerText = "¡VALOR CORPORATIVO DETECTADO! Ohms: " + valOhms.toLocaleString();
                                status.style.color = "green";
                                // Detener cámara nítida
                                camStream.getTracks().forEach(track => track.stop());
                                
                                // ENVIAR DE REGRESO A STREAMLIT INYECTANDO EN URL
                                const url = new URL(window.parent.location.href);
                                url.searchParams.set("ocr_val", valOhms.toString());
                                window.parent.history.replaceState({}, "", url);
                                // Forzamos recarga nítida
                                window.parent.location.reload();
                                
                            } else {
                                status.innerText = "❌ No se reconoció el formato corporativo ANSI/ESD (A x 10^B). Asegúrate de encuadrar nítidamente y que la pantalla esté estabilizada. Texto detectado crudo: " + text.substring(0, 30);
                                status.style.color = "red";
                                btn.disabled = false;
                                btn.innerText = "🔄 REINTENTAR FOTO NÍTIDA";
                            }
                        } catch (ocrErr) {
                            status.innerText = "Error crítico de OCR Corporativo: " + ocrErr.message;
                            status.style.color = "red";
                            console.error("OCR Corporativo Error:", ocrErr);
                            btn.disabled = false;
                            btn.innerText = "📸 REINTENTAR FOTO NÍTIDA";
                        }
                    });
                </script>
                """
                # Inyección del componente nítido HTML/JS en el iPhone
                components.html(html_code_ocr, height=650)
                
            else:
                st.success(f"💾 **Valor corporativo detectado por Visión Artificial (OCR):** **{float(valor_ocr_detectado):,.0f} Ohms**")
                if st.button("🔄 Borrar Escáner de Medidor y Reintentar foto corporativa"):
                    del st.query_params["ocr_val"]
                    st.rerun()

            st.divider()

            # --- FORMULARIO DE ACTUALIZACIÓN NATIVA CORPORATIVA ---
            st.markdown("#### Validar Datos ESD Corporativos y Guardar")
            with st.form("form_actualizacion"):
                
                # El valor por defecto se carga del OCR si existe, si no, del Sheets corporativo
                default_value = float(valor_ocr_detectado) if valor_ocr_detectado else (float(equipo.get('Valor de verificación', 0)) if pd.notna(equipo.get('Valor de verificación')) else 0.0)
                
                nuevo_valor_final = st.number_input(
                    "Nuevo valor corporativo ESD (Ohms)", 
                    value=default_value,
                    format="%f",
                    help="Este valor es capturado nítidamente por el iPhone. Valida que coincida con el medidor."
                )
                
                fecha_hoy_corporativa = datetime.today().date()
                nueva_fecha_valida = st.date_input("Fecha de validación corporativa", fecha_hoy_corporativa)
                
                submit_corporativo = st.form_submit_button("Sincronizar mediciones corporativas con Google Sheets")
                
                if submit_corporativo:
                    with st.spinner("Actualizando celdas quirúrgicas en la nube corporativa..."):
                        # 1. Calcular próxima fecha nítida
                        frecuencia_corp = str(equipo.get('Frecuencia de verificación', 'Anual'))
                        proxima_fecha_val = calcular_proxima_fecha(nueva_fecha_valida, frecuencia_corp)
                        
                        # 2. MÉTODO QUIRÚRGICO DE SEGURIDAD CORPORATIVA (Usando gspread nativo)
                        # Este método evita OOM y protege fórmulas corporativas en filas 1-4
                        import gspread
                        secretos_dict_corp = dict(st.secrets["connections"]["gsheets"])
                        url_hoja_corp = secretos_dict_corp["spreadsheet"]
                        
                        # Autenticación corporativa nativa
                        gc_gspread_corp = gspread.service_account_from_dict(secretos_dict_corp)
                        doc_corp = gc_gspread_corp.open_by_url(url_hoja_corp)
                        ws_corp = doc_corp.worksheet(hoja_activa)
                        
                        # Coordenadas nítidas de columnas
                        id_col_idx_c = df_actual.columns.get_loc('Id de producto')
                        val_col_idx_c = df_actual.columns.get_loc('Valor de verificación')
                        fecha_col_idx_c = df_actual.columns.get_loc('Fecha de verificación')
                        prox_fecha_col_idx_c = df_actual.columns.get_loc('Fecha de próxima verificación')
                        status_col_idx_c = df_actual.columns.get_loc('Estatus de verificación')
                        
                        # Extraemos columna de IDs corporativa (gspread cuenta desde 1)
                        columna_ids_corp = ws_corp.col_values(id_col_idx_c + 1)
                        # Limpieza corporativa de espacios invisibles
                        columna_ids_corp_limpia = [str(val).strip() for val in columna_ids_corp]
                        # Fila nítida en Google Sheets corporativo (sumamos 1 por gspread)
                        row_gspread_corp = columna_ids_corp_limpia.index(str(id_escaneado_url).strip()) + 1
                        
                        # 3. ACTUALIZACIONES QUIRÚRGICAS NÍTIDAS EN TIEMPO REAL
                        ws_corp.update_cell(row_gspread_corp, val_col_idx_c + 1, float(nuevo_valor_final))
                        ws_corp.update_cell(row_gspread_corp, fecha_col_idx_c + 1, nueva_fecha_valida.strftime("%Y-%m-%d"))
                        ws_corp.update_cell(row_gspread_corp, prox_fecha_col_idx_c + 1, proxima_fecha_val.strftime("%Y-%m-%d"))
                        # Marcamos como VIGENTE corporativo nítido
                        ws_corp.update_cell(row_gspread_corp, status_col_idx_c + 1, 'VIGENTE')

                    st.success("💾 ¡Actualización ESD corporativa nítida sincronizada al instante en Google Sheets!")
                    # Limpiamos caché corporativa de 2s
                    st.cache_data.clear()
                    
                    # Limpiamos URL para permitir nuevo escaneo corporativo nítido
                    st.query_params.clear()
                    st.rerun()

        else:
            st.error("❌ El ID corporativo escaneado no existe en el sistema.")
