import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
import gc
import base64
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
        try:
            df_mob = conn.read(worksheet="MOBILIARIO", header=4)
            return df_mob
        except Exception: return None

    def calcular_proxima_fecha(fecha_actual, frecuencia):
        frecuencia = str(frecuencia).strip().lower()
        if 'anual' in frecuencia: return fecha_actual + relativedelta(years=1)
        elif 'semestral' in frecuencia: return fecha_actual + relativedelta(months=6)
        elif 'trimestral' in frecuencia: return fecha_actual + relativedelta(months=3)
        elif 'mensual' in frecuencia: return fecha_actual + relativedelta(months=1)
        else: return fecha_actual + relativedelta(years=1)

    st.title("Sistema de Gestión ESD BCS-AIS Querétaro")
    
    df_mob_local = cargar_datos_cloud()

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
                st.session_state.vista_actual = "Mapa"
                limpiar_url_escaneo() 
                st.rerun()
        with c_nav2:
            if st.button("📱 Escáner / Auditoría", use_container_width=True, type="primary" if st.session_state.vista_actual == "Escáner" else "secondary"):
                st.session_state.vista_actual = "Escáner"
                limpiar_url_escaneo()
                st.rerun()
        with c_nav3:
            if st.button("🆕 Alta/Baja Mobiliario", use_container_width=True, type="primary" if st.session_state.vista_actual == "Alta" else "secondary"):
                st.session_state.vista_actual = "Alta"
                limpiar_url_escaneo()
                st.rerun()
    else:
        st.session_state.vista_actual = "Escáner"

    st.divider()

    # ==========================================
    # VISTA: ALTA Y BAJA DE MOBILIARIO
    # ==========================================
    if st.session_state.vista_actual == "Alta" and not st.session_state.modo_lectura:
        st.markdown("### Gestión de Inventario ESD (Mobiliario)")
        
        with st.expander("📋 Directorio de IDs Existentes (Click para abrir/cerrar)", expanded=False):
            st.info("💡 **Tip:** Puedes dejar este panel abierto. Haz clic en el título de una columna para ordenar (A-Z) o usa la lupa (🔍) en la tabla para buscar un ID específico.")
            if not df_mob_local.empty and 'Id de producto' in df_mob_local.columns and 'Línea' in df_mob_local.columns:
                df_clean = df_mob_local[['Línea', 'Id de producto']].dropna(subset=['Id de producto'])
                df_clean = df_clean[df_clean['Id de producto'].astype(str).str.strip() != '']
                st.dataframe(df_clean, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay datos disponibles aún.")
        
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
            lineas_disponibles = sorted([str(x).strip() for x in df_mob_local['Línea'].unique() if pd.notna(x) and str(x).strip() != ''])
            tipos_disponibles = sorted([str(x).strip() for x in df_mob_local['Clasificación'].unique() if pd.notna(x) and str(x).strip() != ''])

            with st.form("form_alta_mobiliario"):
                col1, col2 = st.columns(2)
                nueva_linea = col1.selectbox("Línea (Ubicación)", options=lineas_disponibles)
                nuevo_id = col2.text_input("ID de Producto (Ej: MOB-001)")
                
                nuevo_tipo = col1.selectbox("Tipo de Mobiliario (Clasificación)", options=tipos_disponibles)
                valor_alta = col2.number_input("Valor de medición inicial (Opcional - Ohms)", value=0.0, format="%.2e")
                
                fabricante_opc = col1.selectbox("Fabricante", options=["BCS", "Otro", "N/A"])
                fabricante_final = fabricante_opc
                if fabricante_opc == "Otro":
                    fabricante_final = col1.text_input("Especifique Fabricante", help="Ingrese el nombre de la marca")
                
                frecuencia_alta = col2.selectbox("Frecuencia de verificación", options=["Anual", "Semestral", "Trimestral", "Mensual"], index=0)
                
                col3, col4 = st.columns(2)
                nuevo_minimo = col3.number_input("Mínimo", value=0.00, format="%.2e")
                limite_alta = col4.text_input("Límite S20.20 (Maximo)", value="1.00E+09")
                
                comentarios = st.text_area("Comentarios (Notas opcionales)")
                
                submit_alta = st.form_submit_button("Registrar en sistema", use_container_width=True)
                
                if submit_alta:
                    if not nuevo_id or (fabricante_opc == "Otro" and not fabricante_final):
                        st.error("Por favor complete los campos obligatorios (ID y Fabricante).")
                    else:
                        id_limpio_alta = str(nuevo_id).strip().upper()
                        ids_existentes = df_mob_local['Id de producto'].astype(str).str.strip().str.upper().values
                        
                        if id_limpio_alta in ids_existentes:
                            st.error(f"El ID {nuevo_id} ya existe en el sistema.")
                        else:
                            with st.spinner("Creando nuevo registro..."):
                                import gspread
                                sec = dict(st.secrets["connections"]["gsheets"])
                                gc_client = gspread.service_account_from_dict(sec)
                                ws = gc_client.open_by_url(sec["spreadsheet"]).worksheet("MOBILIARIO")
                                
                                fecha_hoy = datetime.today().date()
                                dias_map = {"Anual": 360, "Semestral": 180, "Trimestral": 90, "Mensual": 30}
                                proxima = fecha_hoy + timedelta(days=dias_map.get(frecuencia_alta, 360))
                                
                                nueva_fila = [
                                    nueva_linea,                                     
                                    nuevo_id,                                        
                                    nuevo_tipo,                                      
                                    "Aprobado",                                      
                                    fabricante_final,                                
                                    float(nuevo_minimo),                             
                                    float(limite_alta) if "E" in limite_alta.upper() else limite_alta, 
                                    "Ohms",                                          
                                    float(valor_alta) if valor_alta > 0 else "",      
                                    "Ohms",                                          
                                    "RTG",                                           
                                    fecha_hoy.strftime("%d-%b-%Y") if valor_alta > 0 else "", 
                                    proxima.strftime("%d-%b-%Y") if valor_alta > 0 else "",   
                                    frecuencia_alta,                                 
                                    "Vigente" if valor_alta > 0 and fecha_hoy < proxima else "", 
                                    "Operativo",                                     
                                    comentarios,                                     
                                    st.session_state.usuario_nombre                  
                                ]
                                
                                ws.append_row(nueva_fila, value_input_option="USER_ENTERED")
                                
                            st.success(f"✅ ¡Activo {nuevo_id} registrado exitosamente en la línea {nueva_linea}!")
                            st.cache_data.clear()
                            st.balloons()
                            
        # --- SUB-VISTA 2: BAJA ---
        elif accion_seleccionada == "🗑️ Dar de Baja":
            st.markdown("#### 🗑️ Eliminar equipo del sistema")
            
            if not id_baja_url:
                st.write("Escanea el QR o ingresa manualmente el ID del equipo a dar de baja.")
                html_code_baja = """
                <script src="https://unpkg.com/html5-qrcode"></script>
                <div id="reader_baja" style="width:100%; max-width:500px; margin:auto; border-radius:10px; overflow:hidden; border: 2px solid #ddd; background-color: #f9f9f9;"></div>
                <p id="cam-status-baja" style="text-align:center; color:#666; font-size: 14px;">Iniciando cámara trasera...</p>
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
                        const html5QrCode = new Html5Qrcode("reader_baja");
                        html5QrCode.start(
                            selectedCameraId, { fps: 15, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
                            (decodedText) => {
                                html5QrCode.stop();
                                const url = new URL(window.parent.location.href);
                                url.searchParams.set("qr_baja", decodedText);
                                window.parent.history.replaceState({}, "", url);
                                window.parent.location.reload();
                            }, (err) => {} 
                        ).then(() => { setTimeout(() => { document.getElementById("cam-status-baja").style.display = 'none'; }, 1500); });
                    }
                }).catch(err => { document.getElementById("cam-status-baja").innerText = "Otorga permisos de cámara."; });
                </script>
                """
                components.html(html_code_baja, height=650) 
                
                id_manual_baja = st.text_input("Ingresa el ID manual a eliminar:", key="input_manual_baja")
                if id_manual_baja:
                    st.query_params["qr_baja"] = id_manual_baja
                    st.rerun()
            else:
                colA, colB = st.columns([0.8, 0.2])
                with colA:
                    st.error(f"🗑️ **ID a Eliminar:** {id_baja_url}")
                with colB:
                    if st.button("❌ Cancelar"):
                        limpiar_url_escaneo()
                        st.rerun()

                id_limpio_baja = str(id_baja_url).strip().upper()
                mob_ids = df_mob_local['Id de producto'].astype(str).str.strip().str.upper()

                if id_limpio_baja in mob_ids.values:
                    idx_baja = mob_ids[mob_ids == id_limpio_baja].index[0]
                    equipo_baja = df_mob_local.loc[idx_baja]
                    
                    st.markdown("### Verificación del Equipo")
                    col1_b, col2_b, col3_b = st.columns(3)
                    col1_b.metric("Ubicación", str(equipo_baja.get('Línea', 'N/A')))
                    
                    # MEJORA AÑADIDA: Mostrar la clasificación en la vista de Baja
                    col2_b.metric("Tipo (Clasificación)", str(equipo_baja.get('Clasificación', 'N/A')))
                    col3_b.metric("Base de Datos", "MOBILIARIO")

                    with st.form("form_confirmacion_baja"):
                        st.warning("⚠️ **¡Atención!** Esta acción destruirá la fila por completo en Google Sheets y no se puede deshacer.")
                        
                        if st.form_submit_button("🗑️ Confirmar Baja Definitiva"):
                            with st.spinner("Eliminando fila en el servidor..."):
                                import gspread
                                sec = dict(st.secrets["connections"]["gsheets"])
                                gc_gspread = gspread.service_account_from_dict(sec)
                                ws_baja = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet("MOBILIARIO")
                                
                                try:
                                    id_idx_baja = df_mob_local.columns.get_loc('Id de producto')
                                except KeyError as e:
                                    st.error(f"Falta columna {e}")
                                    st.stop()
                                
                                ids_gsheets_baja = ws_baja.col_values(id_idx_baja + 1)
                                ids_gsheets_limpios_baja = [str(v).strip().upper() for v in ids_gsheets_baja]
                                
                                try:
                                    r_idx_baja = ids_gsheets_limpios_baja.index(id_limpio_baja) + 1
                                except ValueError:
                                    st.error("No se pudo encontrar la fila exacta en el servidor para eliminarla.")
                                    st.stop()
                                
                                ws_baja.delete_rows(r_idx_baja)
                                
                            st.success(f"✅ ¡Equipo {id_baja_url} eliminado exitosamente!")
                            st.cache_data.clear()
                            limpiar_url_escaneo()
                            st.rerun()
                else:
                    st.error(f"❌ El ID '{id_baja_url}' no se encontró en la base de datos para darlo de baja.")

    # ==========================================
    # VISTA 1: MAPA Y REPORTES ESD
    # ==========================================
    elif st.session_state.vista_actual == "Mapa" and not st.session_state.modo_lectura:
        st.info("☁️ Los datos mostrados están sincronizados en tiempo real con el servidor.")
        df_total = df_mob_local.copy()
        df_total['Estatus de verificación'] = df_total['Estatus de verificación'].astype(str).str.strip().str.upper()
        if 'Estatus operativo' in df_total.columns:
            df_total['Estatus operativo'] = df_total['Estatus operativo'].astype(str).str.strip().str.upper()
        else:
            df_total['Estatus operativo'] = 'OPERATIVO'

        # MEJORA AÑADIDA: Calcular el total de equipos activos para la proporción
        equipos_activos = df_total[df_total['Estatus operativo'] != 'NO OPERATIVO']
        total_equipos = len(equipos_activos)

        vencidos = equipos_activos[equipos_activos['Estatus de verificación'] == 'VENCIDO']
        
        if not vencidos.empty:
            # MEJORA AÑADIDA: Mostrar la cantidad de equipos vencidos vs el total
            st.error(f"🚨 Se encontraron **{len(vencidos)}** equipos de mobiliario VENCIDOS de un total de **{total_equipos}** equipos activos.")
            conteo_tipos = vencidos.groupby(['Línea']).size().reset_index(name='Total Vencidos')
            conteo_tipos['Etiqueta'] = "M: " + conteo_tipos['Total Vencidos'].astype(str)
            
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
            # MEJORA AÑADIDA: Mostrar la felicitación con el total de equipos evaluados
            st.success(f"✅ ¡Felicidades! No hay mobiliario operativo VENCIDO (0 de {total_equipos} equipos activos).")

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
            components.html(html_code_qr, height=650) 
            
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
            mob_ids_limpios = df_mob_local['Id de producto'].astype(str).str.strip().str.upper()

            if id_limpio in mob_ids_limpios.values:
                idx = mob_ids_limpios[mob_ids_limpios == id_limpio].index[0]
                equipo = df_mob_local.loc[idx]
                
                st.markdown("### 📊 Detalles del Equipo")
                
                # MEJORA AÑADIDA: Cambiado a 3 columnas para mostrar la Clasificación
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
                if pd.notna(val_previo) and val_previo != 0 and str(val_previo).strip() != '':
                    try:
                        c_val.metric("Resistencia Registrada", f"{float(val_previo):.2E} Ω")
                    except ValueError:
                        c_val.metric("Resistencia Registrada", str(val_previo))
                else:
                    c_val.metric("Resistencia Registrada", "N/A")
                
                limite_raw = equipo.get('Maximo', 'N/A')
                if pd.notna(limite_raw) and str(limite_raw).strip() != 'N/A' and str(limite_raw).strip() != '':
                    try:
                        limite_str = f"{float(limite_raw):.2E} Ω"
                    except ValueError:
                        limite_str = str(limite_raw)
                else:
                    limite_str = "N/A"
                    
                st.markdown(f"**Límite S20.20-2021 Permitido:** {limite_str}")
                st.divider()

                if st.session_state.modo_lectura:
                    st.warning("👁️ **Estás en Modo Consulta.** No tienes permisos para capturar pantallas de medidores ni actualizar los registros corporativos. Si deseas realizar una auditoría completa, cierra esta sesión en el menú lateral e ingresa con tus credenciales.")
                else:
                    hacer_medicion = st.checkbox("✅ Realizar nueva medición y actualizar", value=bool(valor_ocr_detectado))
                    
                    if hacer_medicion:
                        st.markdown("### 📷 Captura Automática del Medidor (BETA)")
                        
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
                                limpiar_url_escaneo()
                                st.rerun()

                        with st.form("form_actualizacion"):
                            def_val = float(valor_ocr_detectado) if valor_ocr_detectado else 0.0
                            nuevo_valor_final = st.number_input("Resistencia (Ohms)", value=def_val, format="%.2e")
                            fecha_hoy = datetime.today().date()
                            nueva_fecha_valida = st.date_input("Fecha de medición", fecha_hoy)
                            
                            if st.form_submit_button("Guardar en servidor"):
                                with st.spinner("Guardando..."):
                                    freq = str(equipo.get('Frecuencia de verificación', 'Anual'))
                                    proxy = calcular_proxima_fecha(nueva_fecha_valida, freq)
                                    
                                    import gspread
                                    sec = dict(st.secrets["connections"]["gsheets"])
                                    gc_gspread = gspread.service_account_from_dict(sec)
                                    
                                    ws = gc_gspread.open_by_url(sec["spreadsheet"]).worksheet("MOBILIARIO")
                                    
                                    try:
                                        id_idx = df_mob_local.columns.get_loc('Id de producto')
                                        val_idx = df_mob_local.columns.get_loc('Valor de verificación')
                                        f_idx = df_mob_local.columns.get_loc('Fecha de verificación')
                                        fp_idx = df_mob_local.columns.get_loc('Fecha de próxima verificación')
                                        st_idx = df_mob_local.columns.get_loc('Estatus de verificación')
                                        aud_idx = df_mob_local.columns.get_loc('Auditor') 
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
                                    
                                    ws.update_cell(r_idx, val_idx + 1, float(nuevo_valor_final))
                                    ws.update_cell(r_idx, f_idx + 1, nueva_fecha_valida.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, fp_idx + 1, proxy.strftime("%d-%b-%Y"))
                                    ws.update_cell(r_idx, st_idx + 1, 'VIGENTE')
                                    ws.update_cell(r_idx, aud_idx + 1, st.session_state.usuario_nombre)

                                st.success("💾 ¡Guardado correctamente!")
                                st.cache_data.clear()
                                limpiar_url_escaneo()
                                st.rerun()
            else:
                st.error(f"❌ El ID '{id_escaneado_url}' no se encontró en la base de datos.")
