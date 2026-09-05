import streamlit as st
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# 1. การตั้งค่าหน้าเว็บหลักของ Streamlit
# ---------------------------------------------------------
st.set_page_config(
    page_title="Delivery Map Dashboard",
    page_icon="🚚",
    layout="wide"
)

# ID ของ Google Sheet จาก URL
SHEET_ID = "1c7fFdgvhebZp5S-BUyAt69bvzAh5rf0ed5arMyGlkHI"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"


# ---------------------------------------------------------
# 2. ฟังก์ชันดึงและประมวลผลข้อมูล
# ---------------------------------------------------------
@st.cache_data(ttl=300)
def load_data():
    """ดึงข้อมูลจาก Google Sheet และเตรียมพิกัด GPS"""
    try:
        df = pd.read_csv(CSV_URL)
    except Exception as e:
        return pd.DataFrame(), [], None

    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    # แยกพิกัด GPS
    if 'พิกัด GPS' in df.columns:
        gps_split = df['พิกัด GPS'].astype(str).str.split(',', expand=True)
        if gps_split.shape[1] >= 2:
            df['lat'] = pd.to_numeric(gps_split[0].str.strip(), errors='coerce')
            df['lon'] = pd.to_numeric(gps_split[1].str.strip(), errors='coerce')
        else:
            df['lat'] = np.nan
            df['lon'] = np.nan
    else:
        df['lat'] = np.nan
        df['lon'] = np.nan
    
    # ลบจุดที่ไม่มี GPS
    df = df.dropna(subset=['lat', 'lon']).copy()
    
    # สร้างคอลัมน์ชื่อจุดพิกัด
    if 'รหัสสมาชิก' in df.columns and 'ชื่อ-นามสกุล' in df.columns:
        df['point_label'] = df['รหัสสมาชิก'].astype(str) + " - " + df['ชื่อ-นามสกุล'].astype(str)
    elif 'รหัสสมาชิก' in df.columns:
        df['point_label'] = df['รหัสสมาชิก'].astype(str)
    else:
        df['point_label'] = df.index.astype(str)
    
    month_cols = [c for c in df.columns if c.startswith('ยอดส่ง/เดือน')]
    latest_month_col = month_cols[-1] if len(month_cols) > 0 else None
    
    for col in month_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(',', '').str.strip(), 
            errors='coerce'
        ).fillna(0)
        
    return df, month_cols, latest_month_col


# ---------------------------------------------------------
# 3. โหลดข้อมูล
# ---------------------------------------------------------
df, month_cols, default_latest_col = load_data()

if df.empty:
    st.error("❌ ไม่พบข้อมูลพิกัด GPS หรือไม่สามารถดึงข้อมูลจาก Google Sheet ได้")
    st.stop()


# ---------------------------------------------------------
# 4. แผงควบคุมด้านข้าง (Sidebar Controls)
# ---------------------------------------------------------
st.sidebar.title("⚙️ แผงควบคุม (Controls)")

if month_cols:
    selected_month_col = st.sidebar.selectbox(
        "เลือกคอลัมน์ยอดส่งสำหรับขนาดจุด:",
        options=month_cols,
        index=len(month_cols) - 1
    )
else:
    selected_month_col = None

radius_multiplier = st.sidebar.slider(
    "ปรับขนาดจุดพิกัด:",
    min_value=1,
    max_value=50,
    value=15
)

st.sidebar.subheader("🔍 ตัวกรองกลุ่มข้อมูล")

all_warehouses = sorted(df['คลัง'].dropna().unique().tolist()) if 'คลัง' in df.columns else []
selected_wh = st.sidebar.multiselect("คลัง:", options=all_warehouses, default=all_warehouses)

all_cars = sorted(df['เบอร์รถ'].dropna().unique().tolist()) if 'เบอร์รถ' in df.columns else []
selected_car = st.sidebar.multiselect("เบอร์รถ:", options=all_cars, default=all_cars)

filtered_df = df.copy()

if 'คลัง' in filtered_df.columns and selected_wh:
    filtered_df = filtered_df[filtered_df['คลัง'].isin(selected_wh)]

if 'เบอร์รถ' in filtered_df.columns and selected_car:
    filtered_df = filtered_df[filtered_df['เบอร์รถ'].isin(selected_car)]


# ---------------------------------------------------------
# 5. ฟังก์ชันเรนเดอร์แผนที่แบบ Streamlit Native Map
# ---------------------------------------------------------
HEX_COLORS = [
    "#FF2A6D", "#05D9E8", "#FFC300", "#00FF66",
    "#D600FF", "#FF7700", "#E74C3C", "#2ECC71",
    "#3498DB", "#9B59B6", "#F1C40F", "#E67E22"
]

def render_map(data, color_column, key_suffix=""):
    if len(data) == 0:
        st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไขตัวกรอง")
        return

    unique_keys = sorted(data[color_column].dropna().unique().tolist())
    c_map = {key: HEX_COLORS[i % len(HEX_COLORS)] for i, key in enumerate(unique_keys)}

    # 📌 เลือกจุดพิกัดเฉพาะ
    st.markdown("### 📍 เลือกเน้นเฉพาะจุดพิกัดที่ต้องการ")
    col_search, col_select = st.columns([1, 2])
    with col_search:
        search_kw = st.text_input("🔎 พิมพ์ค้นหาจุดพิกัด:", key=f"kw_{key_suffix}")
    
    all_point_labels = sorted(data['point_label'].dropna().unique().tolist())
    filtered_options = [l for l in all_point_labels if search_kw.lower() in str(l).lower()][:100] if search_kw else all_point_labels[:50]

    session_key = f"selected_pts_{key_suffix}"
    if session_key not in st.session_state:
        st.session_state[session_key] = []

    combined_options = list(dict.fromkeys(st.session_state[session_key] + filtered_options))

    with col_select:
        selected_points = st.multiselect(
            "เลือกจุดพิกัด:",
            options=combined_options,
            default=st.session_state[session_key],
            key=f"select_points_{key_suffix}"
        )
        st.session_state[session_key] = selected_points

    # เตรียมข้อมูลสำหรับแผนที่ Native Map
    map_data = data.copy()

    # คำนวณขนาด
    if selected_month_col and selected_month_col in map_data.columns:
        max_val = map_data[selected_month_col].max()
        max_val = max_val if max_val > 0 else 1
        map_data['size'] = (map_data[selected_month_col] / max_val) * (radius_multiplier * 50) + 10
    else:
        map_data['size'] = radius_multiplier * 10

    # คำนวณสี
    selected_set = set(selected_points)

    def get_hex_color(row):
        lbl = row['point_label']
        grp = row.get(color_column, None)
        if len(selected_set) > 0:
            return c_map.get(grp, "#3388FF") if lbl in selected_set else "#CCCCCC"
        else:
            return c_map.get(grp, "#3388FF")

    map_data['color'] = map_data.apply(get_hex_color, axis=1)

    if len(selected_set) > 0:
        map_data['size'] = np.where(
            map_data['point_label'].isin(selected_set), 
            map_data['size'] * 1.5, 
            map_data['size'] * 0.3
        )

    # แสดงผลผ่าน st.map
    st.map(
        map_data,
        latitude='lat',
        longitude='lon',
        color='color',
        size='size',
        use_container_width=True
    )

    # แสดงสัญลักษณ์สี (Legend)
    legend_cols = st.columns(min(len(unique_keys), 6) if len(unique_keys) > 0 else 1)
    for i, key in enumerate(unique_keys):
        hex_color = c_map[key]
        legend_cols[i % 6].markdown(
            f"<span style='color:{hex_color}; font-size:16px;'>██</span> <b>{key}</b>", 
            unsafe_allow_html=True
        )


# ---------------------------------------------------------
# 6. ส่วนหัวหลัก และแท็บแสดงผล
# ---------------------------------------------------------
st.title("🚚 แดชบอร์ดแผนที่จัดส่งสินค้า (Delivery Map Dashboard)")

tab1, tab2, tab3 = st.tabs([
    "🏢 หน้าที่ 1: แบ่งสีตามคลัง",
    "🚛 หน้าที่ 2: แบ่งสีตามเบอร์รถ",
    "📅 หน้าที่ 3: แบ่งสีตามรอบส่งประจำสัปดาห์"
])

with tab1:
    if 'คลัง' in filtered_df.columns:
        render_map(filtered_df, 'คลัง', key_suffix="t1")

with tab2:
    if 'เบอร์รถ' in filtered_df.columns:
        render_map(filtered_df, 'เบอร์รถ', key_suffix="t2")

with tab3:
    if 'รอบส่งประจำสัปดาห์' in filtered_df.columns:
        render_map(filtered_df, 'รอบส่งประจำสัปดาห์', key_suffix="t3")

st.divider()

# ---------------------------------------------------------
# 7. ตารางสรุปข้อมูล
# ---------------------------------------------------------
st.header("📋 ตารางข้อมูลรายบรรทัด")

search_term = st.text_input("🔍 ค้นหาข้อมูลในตาราง:", "")

display_df = filtered_df.drop(columns=['lat', 'lon', 'point_label'], errors='ignore')

if search_term:
    mask = display_df.astype(str).apply(
        lambda r: r.str.contains(search_term, case=False, na=False), axis=1
    ).any(axis=1)
    search_result_df = display_df[mask]
else:
    search_result_df = display_df

st.dataframe(search_result_df.head(2000), use_container_width=True)
