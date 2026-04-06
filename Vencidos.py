import streamlit as st
import pandas as pd
import plotly.express as px
from PIL import Image
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Control de Cumplimiento ESD", layout="wide")

# --- VARIABLES ESTÁTICAS Y RUTAS ---
RUTA_MAPA = "mapa.jpg" 
RUTA_COORDENADAS = "coordenadas.csv"
RUTA_EXCEL = "E_310_4_110_QRO_SP_Rev.A_BCS ESD IDS.xlsx" # Nombre exacto de tu archivo

# --- FUNCIÓN PARA CARGAR DATOS DIRECTAMENTE DEL DISCO ---
@st.cache_data(ttl=5) # Cache corto para reflejar cambios rápidos, pero evitar lecturas constantes
def cargar_datos(ruta):
    if not os.path.exists(ruta):
        return None, None
    
    df_piso = pd.read_excel(ruta, sheet_name="PISO", header=4)
    df_mob = pd.read_excel(ruta, sheet_name="MOBILIARIO", header=4)
    return df_piso, df_mob

# --- FUNCIÓN PARA CALCULAR LA PRÓXIMA FECHA ---
def calcular_proxima_fecha(fecha_actual, frecuencia):
    frecuencia = str(frecuencia).strip().lower()
    if 'anual' in frecuencia:
        return fecha_actual + relativedelta(years=1)
    elif 'semestral' in frecuencia or '6 meses' in frecuencia:
        return fecha_actual + relativedelta(months=6)
    elif 'trimestral' in frecuencia or '3 meses' in frecuencia:
        return fecha_actual + relativedelta(months=3)
    elif 'mensual' in frecuencia:
        return fecha_actual + relativedelta(months=1)
    else:
        # Por defecto, suma un año si no reconoce el formato
        return fecha_actual + relativedelta(years=1)

# --- INICIO DE LA APP ---
st.title("Control de Cumplimiento ESD S20.20")

df_piso_local, df_mob_local = cargar_datos(RUTA_EXCEL)

if df_piso_local is None or df_mob_local is None:
    st.error(f"❌ No se encontró el archivo '{RUTA_EXCEL}' en la carpeta de la aplicación.")
    st.stop()

# --- NAVEGACIÓN POR PESTAÑAS ---
tab1, tab2 = st.tabs(["🗺️ Mapa y Reportes", "📱 Escáner Móvil y Actualización"])

# ==========================================
# PESTAÑA 1: MAPA Y REPORTES
# ==========================================
with tab1:
    st.markdown("Visualización en tiempo real basada en el archivo local.")
    
    # Consolidar datos para el mapa
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

    vencidos = df_total[
        (df_total['Estatus de verificación'] == 'VENCIDO') & 
        (df_total['Estatus operativo'] != 'NO OPERATIVO')
    ]
    
    if not vencidos.empty:
        st.error(f"🚨 Se encontraron {len(vencidos)} equipos VENCIDOS en operación.")
        
        # Agrupación y mapa
        conteo_tipos = vencidos.groupby(['Línea', 'Hoja Origen']).size().unstack(fill_value=0).reset_index()
        if 'PISO' not in conteo_tipos.columns: conteo_tipos['PISO'] = 0
        if 'MOBILIARIO' not in conteo_tipos.columns: conteo_tipos['MOBILIARIO'] = 0
        
        conteo_tipos.rename(columns={'PISO': 'Equipos (Piso)', 'MOBILIARIO': 'Mobiliario'}, inplace=True)
        conteo_tipos['Total Vencidos'] = conteo_tipos['Equipos (Piso)'] + conteo_tipos['Mobiliario']
        conteo_tipos['Etiqueta'] = "P: " + conteo_tipos['Equipos (Piso)'].astype(str) + "<br>M: " + conteo_tipos['Mobiliario'].astype(str)
        
        st.markdown("### Mapa de Ubicaciones")
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
                    textposition='middle center', textfont=dict(color='white', size=8, weight='bold'),
                    marker=dict(symbol='square', size=20, opacity=0.9, line=dict(width=2, color='DarkSlateGrey'))
                )
                fig.update_layout(
                    images=[dict(source=img, xref="x", yref="y", x=0, y=0, sizex=width, sizey=height, sizing="stretch", opacity=1, layer="below")],
                    xaxis=dict(showgrid=False, zeroline=False, range=[0, width], visible=False),
                    yaxis=dict(showgrid=False, zeroline=False, range=[height, 0], visible=False, scaleanchor="x", scaleratio=1),
                    margin=dict(l=0, r=0, t=0, b=0), coloraxis_showscale=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("No hay coincidencias con el archivo de coordenadas.")
        else:
            st.info(f"📌 Falta '{RUTA_MAPA}' o '{RUTA_COORDENADAS}'.")
            
        st.markdown("### Detalles de Equipos")
        columnas_mostrar = ['Línea', 'Id de producto', 'Clasificación', 'Estatus de verificación', 'Estatus operativo', 'Hoja Origen']
        st.dataframe(vencidos[[col for col in columnas_mostrar if col in vencidos.columns]], use_container_width=True, hide_index=True)
    else:
        st.success("✅ ¡Felicidades! No hay equipos operativos con estatus 'VENCIDO'.")


# ==========================================
# PESTAÑA 2: ESCÁNER Y ACTUALIZACIÓN
# ==========================================
with tab2:
    st.markdown("### Escáner y Actualización Directa")
    st.info("💡 **Tip Móvil:** Selecciona el cuadro de texto abajo y usa el botón de 'Escanear Texto' (icono de cámara) del teclado de tu celular para leer el QR.")
    
    # Campo para el ID
    id_escaneado = st.text_input("🔍 ID del Producto (Escanea el QR aquí):", key="scanner_input")

    if id_escaneado:
        # Buscar en qué hoja está el equipo
        encontrado_piso = id_escaneado in df_piso_local['Id de producto'].values
        encontrado_mob = id_escaneado in df_mob_local['Id de producto'].values

        if encontrado_piso or encontrado_mob:
            # Determinar hoja y cargar el DataFrame completo para modificarlo
            # Es importante recargar el excel original completo (con todas las hojas) para no perder datos al guardar
            try:
                # Cargamos todo el libro de excel para reescribirlo después
                with pd.ExcelFile(RUTA_EXCEL) as xls:
                    # Guardamos todas las hojas temporalmente
                    hojas_completas = {sheet: pd.read_excel(xls, sheet_name=sheet, header=4 if sheet in ["PISO", "MOBILIARIO"] else 0) for sheet in xls.sheet_names}
                    
                    # También guardamos las cabeceras (filas 0 a 3) de PISO y MOBILIARIO para no perder el formato
                    header_piso_raw = pd.read_excel(xls, sheet_name="PISO", nrows=4, header=None)
                    header_mob_raw = pd.read_excel(xls, sheet_name="MOBILIARIO", nrows=4, header=None)
            except Exception as e:
                st.error(f"Error al leer el archivo base: {e}")
                st.stop()

            if encontrado_piso:
                hoja_activa = "PISO"
                df_activo = hojas_completas["PISO"]
            else:
                hoja_activa = "MOBILIARIO"
                df_activo = hojas_completas["MOBILIARIO"]

            # Obtener el índice
            idx = df_activo[df_activo['Id de producto'] == id_escaneado].index[0]
            equipo = df_activo.iloc[idx]

            st.success(f"✅ Equipo encontrado: **{id_escaneado}** (Categoría: {hoja_activa})")
            
            # Mostrar info actual
            col1, col2 = st.columns(2)
            col1.metric("Estatus Actual", str(equipo.get('Estatus de verificación', 'N/A')))
            col2.metric("Última Fecha Validada", str(equipo.get('Fecha de verificación', 'N/A'))[:10])
            
            st.divider()

            # Formulario
            st.markdown("#### Registrar Nueva Medición")
            with st.form("form_actualizacion"):
                nuevo_valor = st.number_input(
                    "Nuevo valor de medición", 
                    value=float(equipo.get('Valor de verificación', 0)) if pd.notna(equipo.get('Valor de verificación')) else 0.0,
                    format="%f"
                )
                
                # La fecha de hoy por defecto
                fecha_hoy = datetime.today().date()
                nueva_fecha = st.date_input("Fecha de medición actual", fecha_hoy)
                
                submit = st.form_submit_button("Guardar en Excel y Actualizar Estatus")
                
                if submit:
                    # 1. Actualizar Valor
                    df_activo.at[idx, 'Valor de verificación'] = nuevo_valor
                    
                    # 2. Actualizar Fecha de Verificación Actual
                    # Aseguramos formato YYYY-MM-DD
                    fecha_str = nueva_fecha.strftime("%Y-%m-%d")
                    df_activo.at[idx, 'Fecha de verificación'] = fecha_str
                    
                    # 3. Calcular y Actualizar Fecha Próxima
                    frecuencia = str(equipo.get('Frecuencia de verificación', 'Anual'))
                    proxima_fecha = calcular_proxima_fecha(nueva_fecha, frecuencia)
                    df_activo.at[idx, 'Fecha de próxima verificación'] = proxima_fecha.strftime("%Y-%m-%d")
                    
                    # 4. Cambiar Estatus
                    df_activo.at[idx, 'Estatus de verificación'] = 'VIGENTE'
                    
                    # 5. Guardar los cambios directamente al archivo Excel físico
                    try:
                        with pd.ExcelWriter(RUTA_EXCEL, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                            # Debido a que tu archivo tiene filas de encabezado complejas (las primeras 4 filas), 
                            # escribimos primero esas filas y luego el dataframe modificado
                            if hoja_activa == "PISO":
                                header_piso_raw.to_excel(writer, sheet_name="PISO", index=False, header=False)
                                df_activo.to_excel(writer, sheet_name="PISO", index=False, startrow=4)
                            elif hoja_activa == "MOBILIARIO":
                                header_mob_raw.to_excel(writer, sheet_name="MOBILIARIO", index=False, header=False)
                                df_activo.to_excel(writer, sheet_name="MOBILIARIO", index=False, startrow=4)

                        st.success("💾 ¡Datos guardados exitosamente en el archivo Excel!")
                        st.info(f"📅 Próxima validación calculada para: {proxima_fecha.strftime('%Y-%m-%d')} (Frecuencia: {frecuencia})")
                        
                        # Limpiar cache para que el mapa se actualice
                        st.cache_data.clear()
                        
                    except PermissionError:
                        st.error("❌ Error: No se puede guardar. Asegúrate de que el archivo Excel NO esté abierto en otro programa.")
                    except Exception as e:
                        st.error(f"❌ Ocurrió un error al guardar: {e}")

        else:
            st.error("❌ El ID escaneado no existe en el sistema.")
            
    st.divider()
    st.markdown("### 📥 Respaldo de Base de Datos")
    st.info("Streamlit Cloud es un entorno temporal. No olvides descargar tu archivo Excel actualizado al terminar tus mediciones.")
        
    # Leemos el archivo físico que ha sido modificado en el contenedor
    if os.path.exists(RUTA_EXCEL):
        with open(RUTA_EXCEL, "rb") as file:
            btn = st.download_button(
                label="Descargar Excel Actualizado",
                data=file,
                file_name=f"BCS_ESD_Actualizado_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
