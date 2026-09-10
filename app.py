import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import ArcGIS
import requests
import json
import os

# 1. ตั้งค่าหน้าเว็บแบบ Responsive
st.set_page_config(
    page_title="ระบบคำนวณค่าขนส่งถัง", 
    layout="wide",
    initial_sidebar_state="auto"
)

# 2. ปรับแต่ง CSS สำหรับ Mobile-first
st.markdown("""
    <style>
    .stTable { width: 100% !important; overflow-x: auto; }
    [data-testid="stMetricValue"] { font-size: clamp(1.5rem, 4vw, 2.2rem) !important; }
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 1.5rem !important;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='margin-bottom: 1rem;'>🚚 แพลตฟอร์มคำนวณค่าขนส่งและวางแผนเส้นทาง</h2>", unsafe_allow_html=True)

# Initialize geolocator
geolocator = ArcGIS(timeout=10)
HISTORY_FILE = "history_data.json"

ROUTE_COLORS = [
    {"line": "#1f77b4", "marker": "blue"},
    {"line": "#ff7f0e", "marker": "orange"},
    {"line": "#2ca02c", "marker": "green"},
    {"line": "#9467bd", "marker": "purple"},
    {"line": "#d62728", "marker": "red"},
    {"line": "#8c564b", "marker": "darkred"},
    {"line": "#e377c2", "marker": "pink"},
    {"line": "#7f7f7f", "marker": "gray"},
    {"line": "#bcbd22", "marker": "cadetblue"},
    {"line": "#17becf", "marker": "lightblue"}
]

# --- Helper Functions ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@st.cache_data(ttl=86400)
def reverse_geocode(lat, lon):
    try:
        location = geolocator.reverse(f"{lat}, {lon}")
        if location and location.raw:
            address = location.raw.get('address', {})
            district = address.get('Neighborhood') or address.get('City') or ""
            subregion = address.get('Subregion') or ""
            region = address.get('Region') or ""
            
            if "Bangkok" in region or "กรุงเทพ" in region:
                sub_txt = f"แขวง{district}" if district else ""
                district_txt = f"เขต{subregion}" if subregion else ""
                province_txt = "กรุงเทพมหานคร"
            else:
                sub_txt = f"ต.{district}" if district else ""
                district_txt = f"อ.{subregion}" if subregion else ""
                province_txt = f"จ.{region}" if region else ""

            parts = [p for p in [sub_txt, district_txt, province_txt] if p]
            if parts:
                return " ".join(parts)
            return location.address
    except Exception:
        pass
    return f"{lat:.4f}, {lon:.4f}"

@st.cache_data(ttl=86400)
def parse_and_resolve_location(text_input):
    if not text_input:
        return None, ""
    text = str(text_input).strip()
    if not text:
        return None, ""
    
    if "," in text:
        try:
            parts = text.split(",")
            lat, lon = float(parts[0].strip()), float(parts[1].strip())
            readable_name = reverse_geocode(lat, lon)
            return (lat, lon), readable_name
        except ValueError:
            pass

    try:
        location = geolocator.geocode(text)
        if location:
            return (location.latitude, location.longitude), text
    except Exception:
        pass
    return None, text

@st.cache_data(ttl=3600)
def get_multi_stop_route(coords_list):
    if len(coords_list) < 2:
        return 0.0, []
    
    loc_str = ";".join([f"{c[1]},{c[0]}" for c in coords_list])
    try:
        osrm_url = f"https://router.project-osrm.org/route/v1/driving/{loc_str}?overview=full&geometries=geojson"
        response = requests.get(osrm_url, timeout=5)
        data = response.json()
        
        if "routes" in data and len(data["routes"]) > 0:
            distance_meters = data["routes"][0]["distance"]
            distance_km = round(distance_meters / 1000.0, 2)
            geometry = data["routes"][0]["geometry"]["coordinates"]
            route_points = [[point[1], point[0]] for point in geometry]
            return distance_km, route_points
    except Exception:
        pass
    return 0.0, []

# โหลดประวัติ
history_dict = load_history()

# ฟังก์ชั่นอัปเดต Session State ทั้งหมดอย่างปลอดภัย
def apply_preset_to_session_state(preset_name, data_source=None):
    if data_source is None:
        data_source = history_dict
    data = data_source.get(preset_name)
    if not data:
        return
    
    st.session_state["tank_input_mode"] = data.get("tank_input_mode", "ระบุแบบรวมทั้งหมด")
    st.session_state["num_tanks"] = int(data.get("num_tanks", 0))
    
    # ดึงข้อมูลจุดต้นทาง
    origins = data.get("origins", [])
    st.session_state["num_origins"] = len(origins) if origins else 1
    for idx, o in enumerate(origins):
        if isinstance(o, dict):
            st.session_state[f"origin_raw_{idx}"] = o.get("raw", "")
            st.session_state[f"origin_cust_{idx}"] = o.get("custom_name", "")
        else:
            st.session_state[f"origin_raw_{idx}"] = str(o)
            st.session_state[f"origin_cust_{idx}"] = ""

    # ดึงข้อมูลจุดจัดส่ง
    dests = data.get("destinations", [])
    st.session_state["num_destinations"] = len(dests) if dests else 1
    for j, d in enumerate(dests):
        if isinstance(d, dict):
            st.session_state[f"dest_input_{j}"] = d.get("raw", "")
            st.session_state[f"dest_name_{j}"] = d.get("custom_name", "")
        else:
            st.session_state[f"dest_input_{j}"] = str(d)
            st.session_state[f"dest_name_{j}"] = ""

    # ดึงข้อมูลรถ
    trucks = data.get("trucks", [])
    st.session_state["num_trucks"] = len(trucks) if trucks else 1
    for i, t in enumerate(trucks):
        st.session_state[f"truck_origin_{i}"] = t.get("origin_key", "")
        st.session_state[f"truck_type_{i}"] = t.get("type", "รถกระบะ 4 ล้อ")
        st.session_state[f"truck_mode_{i}"] = t.get("calc_mode", "เหมาจ่ายต่อเที่ยว")
        st.session_state[f"truck_rate_{i}"] = float(t.get("rate", 0.0))
        st.session_state[f"truck_tanks_{i}"] = int(t.get("tanks", 0))
        st.session_state[f"truck_dist_{i}"] = float(t.get("dist_km", 0.0))
        st.session_state[f"truck_stops_{i}"] = t.get("stops_keys", [])
        st.session_state[f"truck_start_fee_{i}"] = int(t.get("start_fee_from_stop", 2))
        st.session_state[f"truck_stop_fee_{i}"] = float(t.get("extra_stop_fee", 0.0))
        st.session_state[f"truck_num_laborers_{i}"] = int(t.get("num_laborers", 0))
        st.session_state[f"truck_base_wage_{i}"] = float(t.get("base_wage", 0.0))
        st.session_state[f"truck_early_morning_fee_{i}"] = float(t.get("early_morning_fee", 0.0))
        st.session_state[f"truck_diligence_allowance_{i}"] = float(t.get("diligence_allowance", 0.0))
        st.session_state[f"truck_sso_company_fee_{i}"] = float(t.get("sso_company_fee", 0.0))

    # ดึงข้อมูลเงื่อนไขต่างๆ
    st.session_state["distance_input_mode"] = data.get("distance_input_mode", "แยกระยะทางตามรายคัน")
    st.session_state["use_distance_cost"] = data.get("use_distance_cost", "ไม่อิงจากระยะทาง (คิดเหมา)")
    st.session_state["cost_per_km"] = float(data.get("cost_per_km", 0.0))
    st.session_state["base_free_km"] = float(data.get("base_free_km", 0.0))
    
    st.session_state["labor_input_mode"] = data.get("labor_input_mode", "กำหนดค่าแรงแบบรวม")
    st.session_state["num_laborers"] = int(data.get("num_laborers", 0))
    st.session_state["base_wage"] = float(data.get("base_wage", 0.0))
    st.session_state["early_morning_fee"] = float(data.get("early_morning_fee", 0.0))
    st.session_state["diligence_allowance"] = float(data.get("diligence_allowance", 0.0))
    st.session_state["sso_company_fee"] = float(data.get("sso_company_fee", 0.0))
    
    st.session_state["lifting_fee_per_tank"] = float(data.get("lifting_fee_per_tank", 0.0))
    
    st.session_state["use_forklift"] = bool(data.get("use_forklift", False))
    st.session_state["forklift_mode"] = data.get("forklift_mode", "ค่าเช่ารวมคนขับ")
    st.session_state["num_forklifts"] = int(data.get("num_forklifts", 1))
    st.session_state["forklift_days"] = int(data.get("forklift_days", 1))
    st.session_state["forklift_rate_per_day"] = float(data.get("forklift_rate_per_day", 0.0))
    st.session_state["forklift_driver_wage_per_day"] = float(data.get("forklift_driver_wage_per_day", 0.0))

# --- จัดการ Pending Preset Key ก่อนที่ Widget Selectbox จะถูกสร้างขึ้น ---
if "pending_preset_key" in st.session_state:
    st.session_state["selected_preset_key"] = st.session_state.pop("pending_preset_key")

if "selected_preset_key" not in st.session_state:
    st.session_state["selected_preset_key"] = "-- เลือกรายการเพื่อโหลด --"

# --- Sidebar Management ---
st.sidebar.header("📁 จัดการประวัติและรีเซ็ตระบบ")

col_reset, col_backup = st.sidebar.columns(2)
if col_reset.button("🔄 รีเซ็ตค่า", use_container_width=True):
    st.session_state.clear()
    st.session_state["selected_preset_key"] = "-- เลือกรายการเพื่อโหลด --"
    st.rerun()

options_list = ["-- เลือกรายการเพื่อโหลด --"] + list(history_dict.keys())

# ตรวจสอบว่าคีย์ที่เลือกยังคงอยู่ในตัวเลือกหรือไม่
if st.session_state["selected_preset_key"] not in options_list:
    st.session_state["selected_preset_key"] = "-- เลือกรายการเพื่อโหลด --"

selected_preset_name = st.sidebar.selectbox(
    "📂 เลือกรายการที่เคยบันทึกไว้", 
    options=options_list,
    key="selected_preset_key",
    on_change=lambda: apply_preset_to_session_state(st.session_state.selected_preset_key)
)

col_save, col_del = st.sidebar.columns(2)
if selected_preset_name != "-- เลือกรายการเพื่อโหลด --" and col_del.button("🗑️ ลบรายการนี้", use_container_width=True):
    if selected_preset_name in history_dict:
        del history_dict[selected_preset_name]
        save_history(history_dict)
        st.session_state["pending_preset_key"] = "-- เลือกรายการเพื่อโหลด --"
        st.sidebar.warning(f"ลบรายการ '{selected_preset_name}' แล้ว")
        st.rerun()

# สำรอง/นำเข้าไฟล์ประวัติ JSON
with st.sidebar.expander("📥 Export / Import สำรองไฟล์ประวัติ"):
    json_str = json.dumps(history_dict, ensure_ascii=False, indent=4)
    st.download_button(
        label="💾 ดาวน์โหลดไฟล์ประวัติ (Backup JSON)",
        data=json_str,
        file_name="history_backup.json",
        mime="application/json",
        use_container_width=True
    )
    
    uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ประวัติกลับเข้ามาระบบ", type=["json"], key="history_uploader")
    if uploaded_file is not None:
        try:
            imported_data = json.load(uploaded_file)
            if isinstance(imported_data, dict) and len(imported_data) > 0:
                # อัปเดตไฟล์ประวัติในเครื่อง
                history_dict.update(imported_data)
                save_history(history_dict)
                
                # ดึงรายการแรกที่นำเข้าเพื่อโหลดทันที
                first_key = list(imported_data.keys())[0]
                apply_preset_to_session_state(first_key, imported_data)
                
                # ตั้งค่าคีย์รอการปรับเปลี่ยน แล้วทำการ rerun อย่างปลอดภัย
                st.session_state["pending_preset_key"] = first_key
                st.success(f"นำเข้าข้อมูลสำเร็จ! โหลดรายการ '{first_key}' แล้ว")
                st.rerun()
            else:
                st.error("ไฟล์ JSON ไม่มีข้อมูล หรือรูปแบบไม่ถูกต้อง")
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")

st.sidebar.markdown("---")

# --- ส่วนที่ 1: แถบข้างกำหนดค่า ---
st.sidebar.header("⚙️ กำหนดค่าและปัจจัยการคำนวณ")

# 1.1 จำนวนถัง
st.sidebar.subheader("📦 จำนวนถังที่จัดส่ง")
tank_input_mode = st.sidebar.radio(
    "รูปแบบการระบุจำนวนถัง",
    ["ระบุแบบรวมทั้งหมด", "ระบุแยกรายคันรถ"],
    key="tank_input_mode"
)

num_tanks = 0
if tank_input_mode == "ระบุแบบรวมทั้งหมด":
    num_tanks = st.sidebar.number_input("จำนวนถังที่ส่งทั้งหมด (ถัง)", min_value=0, step=10, key="num_tanks")

# 1.2 จุดต้นทาง (รองรับหลายจุดต้นทาง)
st.sidebar.subheader("🏬 จุดต้นทาง (คลัง / ศูนย์กระจายสินค้า)")

num_origins = st.sidebar.number_input("จำนวนจุดต้นทาง/คลังทั้งหมด", min_value=1, step=1, key="num_origins")

origins_data = []
for idx in range(int(num_origins)):
    o_num = idx + 1
    st.sidebar.markdown(f"**🏢 ต้นทาง/คลังที่ {o_num}**")
    raw_ori = st.sidebar.text_input(f"พิกัด/สถานที่ คลัง #{o_num}", key=f"origin_raw_{idx}", placeholder="เช่น 13.7563, 100.5018 หรือ บางนา")
    loc_ori, res_ori_name = parse_and_resolve_location(raw_ori)
    cust_ori = st.sidebar.text_input(f"ตั้งชื่อคลัง #{o_num}", key=f"origin_cust_{idx}", placeholder=f"เช่น คลังสินค้า {o_num}")
    
    final_ori_display = cust_ori.strip() or res_ori_name or f"คลังที่ {o_num}"
    
    if raw_ori and loc_ori:
        st.sidebar.caption(f"📍 พิกัด: **{res_ori_name}**")
    elif raw_ori:
        st.sidebar.warning(f"⚠️ ไม่พบพิกัด คลังที่ {o_num}")

    origins_data.append({
        "index": o_num,
        "raw": raw_ori,
        "custom_name": cust_ori,
        "coord": loc_ori,
        "resolved_name": res_ori_name,
        "display": final_ori_display
    })

origin_map = {f"คลังที่ {o['index']}: {o['display']}": o for o in origins_data}

# 1.3 จุดจัดส่งปลายทาง
st.sidebar.subheader("📍 จุดจัดส่งปลายทาง")
num_destinations = st.sidebar.number_input("จำนวนจุดจัดส่งปลายทางทั้งหมด (จุด)", min_value=1, step=1, key="num_destinations")

destinations_data = []
for j in range(int(num_destinations)):
    stop_num = j + 1
    st.sidebar.markdown(f"**📌 จุดส่งที่ {stop_num}**")
    raw_dest = st.sidebar.text_input(f"ค้นหาด้วย พิกัด / ชื่อสถานที่ #{stop_num}", key=f"dest_input_{j}", placeholder="เช่น 14.35, 100.57 หรือ อยุธยา")
    loc_dest, resolved_dest_name = parse_and_resolve_location(raw_dest)
    custom_name = st.sidebar.text_input(f"ตั้งชื่อจุดส่งที่ {stop_num}", key=f"dest_name_{j}", placeholder="เช่น สาขาอยุธยา หรือ คลัง B")

    final_display_name = custom_name.strip() or resolved_dest_name or f"จุดส่งที่ {stop_num}"

    if raw_dest and loc_dest:
        st.sidebar.caption(f"📍 พิกัด: **{resolved_dest_name}**")
    elif raw_dest:
        st.sidebar.warning(f"⚠️ ไม่พบพิกัดจุดส่งที่ {stop_num}")
    
    destinations_data.append({
        "index": stop_num,
        "raw": raw_dest,
        "custom_name": custom_name,
        "coord": loc_dest,
        "resolved_name": resolved_dest_name,
        "display": final_display_name
    })

dest_map = {f"จุดส่งที่ {d['index']}: {d['display']}": d for d in destinations_data}

# 1.4 การตั้งค่าค่าแรงเด็กยก
st.sidebar.subheader("👷 รายละเอียดค่าแรงและสวัสดิการเด็กยก")
labor_input_mode = st.sidebar.radio(
    "รูปแบบการระบุค่าแรงเด็กยก",
    ["กำหนดค่าแรงแบบรวม", "กำหนดแยกรายคันรถ"],
    key="labor_input_mode"
)

num_laborers = 0
base_wage = early_morning_fee = diligence_allowance = sso_company_fee = 0.0
total_labor_cost = 0.0
cost_per_laborer = 0.0

if labor_input_mode == "กำหนดค่าแรงแบบรวม":
    num_laborers = st.sidebar.number_input("จำนวนเด็กยกทั้งหมด (คน)", min_value=0, step=1, key="num_laborers")
    if num_laborers > 0:
        base_wage = st.sidebar.number_input("1. ค่าแรงพื้นฐาน (บาท/คน)", min_value=0.0, step=50.0, format="%.2f", key="base_wage")
        early_morning_fee = st.sidebar.number_input("2. ค่าออกเช้า (บาท/คน)", min_value=0.0, step=10.0, format="%.2f", key="early_morning_fee")
        diligence_allowance = st.sidebar.number_input("3. ค่าเบี้ยขยัน (บาท/คน)", min_value=0.0, step=10.0, format="%.2f", key="diligence_allowance")
        sso_company_fee = st.sidebar.number_input("4. ค่า บ.ส่ง ประกันสังคม (บาท/คน)", min_value=0.0, step=5.0, format="%.2f", key="sso_company_fee")
    
    cost_per_laborer = base_wage + early_morning_fee + diligence_allowance + sso_company_fee
    total_labor_cost = cost_per_laborer * num_laborers

# 1.5 รถและการมอบหมายจุดส่ง
st.sidebar.subheader("🚚 เงื่อนไขการขนส่งและตั้งค่าต่อคัน")
num_trucks = st.sidebar.number_input("จำนวนรถที่ใช้ (คัน)", min_value=1, step=1, key="num_trucks")

# รูปแบบระยะทางจัดส่ง
st.sidebar.subheader("📏 เงื่อนไขระยะทางจัดส่ง")
distance_input_mode = st.sidebar.radio(
    "รูปแบบการระบุระยะทาง",
    ["แยกระยะทางตามรายคัน", "รวมระยะทางทุกคัน"],
    key="distance_input_mode"
)

truck_details, trucks_save_state, truck_routes_info, truck_stop_fees_breakdown = [], [], [], []
total_base_trip_cost, total_extra_stop_fee, auto_total_distance_km = 0.0, 0.0, 0.0

type_options = [
    "รถกระบะ 4 ล้อ", 
    "รถ 6 ล้อ", 
    "รถ 10 ล้อ", 
    "รถ 6 ล้อมีลิฟท์ท้าย", 
    "รถ 10 ล้อมีลิฟท์ท้าย", 
    "รถเทรลเลอร์"
]

ori_options = list(origin_map.keys())
dest_options = list(dest_map.keys())

sum_tanks_from_trucks = 0
sum_laborers_from_trucks = 0
sum_labor_cost_from_trucks = 0.0

for i in range(int(num_trucks)):
    st.sidebar.markdown(f"--- \n**🚛 คันที่ {i+1}**")
    color_info = ROUTE_COLORS[i % len(ROUTE_COLORS)]
    
    t_assigned_origin_key = st.sidebar.selectbox(
        f"จุดต้นทาง (คันที่ {i+1})", 
        ori_options if ori_options else ["ไม่มีจุดต้นทาง"], 
        key=f"truck_origin_{i}"
    )
    selected_origin_obj = origin_map.get(t_assigned_origin_key)

    t_type = st.sidebar.selectbox(f"ประเภทรถ (คันที่ {i+1})", type_options, key=f"truck_type_{i}")
    
    # กำหนดจำนวนถังถ้าระบุแยกรายคัน
    t_tanks = 0
    if tank_input_mode == "ระบุแยกรายคันรถ":
        t_tanks = st.sidebar.number_input(f"จำนวนถังที่บรรทุก (คันที่ {i+1}) [ถัง]", min_value=0, step=5, key=f"truck_tanks_{i}")
        sum_tanks_from_trucks += t_tanks

    calc_mode_options = ["เหมาจ่ายต่อเที่ยว", "คิดราคาต่อถัง"]
    t_calc_mode = st.sidebar.radio(f"รูปแบบการคิดค่าขนส่ง (คันที่ {i+1})", calc_mode_options, key=f"truck_mode_{i}")

    if t_calc_mode == "เหมาจ่ายต่อเที่ยว":
        t_rate = st.sidebar.number_input(f"ค่าขนส่งเหมาจ่าย (คันที่ {i+1}) [บาท]", min_value=0.0, step=100.0, format="%.2f", key=f"truck_rate_{i}")
        t_cost = t_rate
    else:
        t_rate = st.sidebar.number_input(f"ค่าขนส่งราคาต่อถัง (คันที่ {i+1}) [บาท/ถัง]", min_value=0.0, step=5.0, format="%.2f", key=f"truck_rate_{i}")
        current_truck_tanks = t_tanks if tank_input_mode == "ระบุแยกรายคันรถ" else num_tanks
        t_cost = t_rate * current_truck_tanks

    assigned_stops = st.sidebar.multiselect(
        f"จุดส่งที่รถคันที่ {i+1} วิ่งส่ง",
        options=dest_options,
        key=f"truck_stops_{i}"
    )
    
    stops_count = len(assigned_stops)
    truck_coords = []
    if selected_origin_obj and selected_origin_obj["coord"]:
        truck_coords.append(selected_origin_obj["coord"])

    for stop_label in assigned_stops:
        target_dest = dest_map.get(stop_label)
        if target_dest and target_dest["coord"]:
            truck_coords.append(target_dest["coord"])

    # คำนวณระยะทางจาก OSRM
    osrm_dist_km, t_route_pts = get_multi_stop_route(truck_coords) if len(truck_coords) >= 2 else (0.0, [])
    
    # กรณีเลือกเปิดการป้อนระยะทางแยกรายคัน
    if distance_input_mode == "แยกระยะทางตามรายคัน":
        if f"truck_dist_{i}" not in st.session_state:
            st.session_state[f"truck_dist_{i}"] = float(osrm_dist_km)

        t_dist_km = st.sidebar.number_input(
            f"ระยะทางขนส่ง คันที่ {i+1} (กิโลเมตร)", 
            min_value=0.0, 
            step=1.0, 
            format="%.2f", 
            key=f"truck_dist_{i}"
        )
        if osrm_dist_km > 0:
            st.sidebar.caption(f"📏 ระยะทางคำนวณจากแผนที่ถนนจริง: **{osrm_dist_km:,.2f} กม.**")
    else:
        t_dist_km = osrm_dist_km
    
    auto_total_distance_km += t_dist_km

    # กรณีเลือกเปิดการป้อนค่าแรงเด็กยกแยกรายคัน
    t_num_laborers = 0
    t_base_wage = t_early_morning_fee = t_diligence_allowance = t_sso_company_fee = 0.0
    if labor_input_mode == "กำหนดแยกรายคันรถ":
        st.sidebar.markdown(f"**👷 เด็กยกประจำคันที่ {i+1}**")
        t_num_laborers = st.sidebar.number_input(f"จำนวนเด็กยก (คันที่ {i+1}) [คน]", min_value=0, step=1, key=f"truck_num_laborers_{i}")
        if t_num_laborers > 0:
            t_base_wage = st.sidebar.number_input(f"ค่าแรงพื้นฐาน (คันที่ {i+1}) [บาท/คน]", min_value=0.0, step=50.0, format="%.2f", key=f"truck_base_wage_{i}")
            t_early_morning_fee = st.sidebar.number_input(f"ค่าออกเช้า (คันที่ {i+1}) [บาท/คน]", min_value=0.0, step=10.0, format="%.2f", key=f"truck_early_morning_fee_{i}")
            t_diligence_allowance = st.sidebar.number_input(f"ค่าเบี้ยขยัน (คันที่ {i+1}) [บาท/คน]", min_value=0.0, step=10.0, format="%.2f", key=f"truck_diligence_allowance_{i}")
            t_sso_company_fee = st.sidebar.number_input(f"ค่า บ.ส่ง ประกันสังคม (คันที่ {i+1}) [บาท/คน]", min_value=0.0, step=5.0, format="%.2f", key=f"truck_sso_company_fee_{i}")
        
        t_cost_per_lab = t_base_wage + t_early_morning_fee + t_diligence_allowance + t_sso_company_fee
        t_total_lab_cost = t_cost_per_lab * t_num_laborers
        
        sum_laborers_from_trucks += t_num_laborers
        sum_labor_cost_from_trucks += t_total_lab_cost

    truck_routes_info.append({
        "truck_index": i + 1,
        "truck_type": t_type,
        "origin_obj": selected_origin_obj,
        "assigned_stops": [dest_map[s] for s in assigned_stops if s in dest_map],
        "coords": truck_coords,
        "distance_km": t_dist_km,
        "route_points": t_route_pts,
        "color": color_info
    })

    t_start_fee_from = st.sidebar.number_input(
        f"เริ่มคิดค่าส่งเพิ่มคันที่ {i+1} ตั้งแต่จุดที่เท่าไร?",
        min_value=1, max_value=max(1, stops_count),
        step=1, key=f"truck_start_fee_{i}"
    )
    
    t_extra_stop_fee = st.sidebar.number_input(
        f"ค่าบริการเพิ่มต่อจุด (คันที่ {i+1}) [บาท/จุด]", 
        min_value=0.0, 
        step=100.0, format="%.2f", key=f"truck_stop_fee_{i}"
    )

    charged_stops_for_truck = max(0, stops_count - int(t_start_fee_from) + 1) if stops_count >= t_start_fee_from else 0
    truck_total_stop_fee = charged_stops_for_truck * t_extra_stop_fee
    total_extra_stop_fee += truck_total_stop_fee

    if charged_stops_for_truck > 0:
        truck_stop_fees_breakdown.append({
            "label": f"  └─ คันที่ {i+1} ({t_type}): คิด {charged_stops_for_truck} จุด (จุดที่ {t_start_fee_from} ขึ้นไป) @ {t_extra_stop_fee:,.2f} ฿",
            "cost": truck_total_stop_fee
        })

    ori_name_tag = selected_origin_obj['display'] if selected_origin_obj else 'ไม่ระบุ'
    t_tank_display = t_tanks if tank_input_mode == "ระบุแยกรายคันรถ" else num_tanks
    
    if t_calc_mode == "เหมาจ่ายต่อเที่ยว":
        truck_details.append(f"{t_type} [จาก: {ori_name_tag}] ({t_cost:,.2f} ฿ - วิ่ง {stops_count} จุด / {t_dist_km:,.2f} กม.)")
    else:
        truck_details.append(f"{t_type} [จาก: {ori_name_tag}] ({t_rate:,.2f} ฿/ถัง x {t_tank_display} ถัง = {t_cost:,.2f} ฿ - วิ่ง {stops_count} จุด / {t_dist_km:,.2f} กม.)")

    trucks_save_state.append({
        "type": t_type, 
        "calc_mode": t_calc_mode, 
        "rate": float(t_rate),
        "tanks": int(t_tanks),
        "dist_km": float(t_dist_km),
        "extra_stop_fee": float(t_extra_stop_fee), 
        "start_fee_from_stop": int(t_start_fee_from),
        "origin_key": t_assigned_origin_key,
        "stops_keys": assigned_stops,
        "num_laborers": int(t_num_laborers),
        "base_wage": float(t_base_wage),
        "early_morning_fee": float(t_early_morning_fee),
        "diligence_allowance": float(t_diligence_allowance),
        "sso_company_fee": float(t_sso_company_fee)
    })
    total_base_trip_cost += float(t_cost)

# อัปเดตค่าจำนวนถังและค่าแรงเด็กยกหากเลือกป้อนแบบแยกรายคัน
if tank_input_mode == "ระบุแยกรายคันรถ":
    num_tanks = sum_tanks_from_trucks

if labor_input_mode == "กำหนดแยกรายคันรถ":
    num_laborers = sum_laborers_from_trucks
    total_labor_cost = sum_labor_cost_from_trucks

# 1.6 การคำนวณราคาตามระยะทาง
st.sidebar.markdown("---")
if distance_input_mode == "แยกระยะทางตามรายคัน":
    distance_km = auto_total_distance_km
    st.sidebar.info(f"📊 สรุประยะทางรวมทุกคัน: **{distance_km:,.2f} กิโลเมตร**")
else:
    distance_km = st.sidebar.number_input("ระยะทางรวมทุกคัน (กิโลเมตร)", min_value=0.0, value=float(auto_total_distance_km), step=1.0, format="%.2f")

dist_options = [
    "ไม่อิงจากระยะทาง (คิดเหมา)",
    "อิงจากระยะทาง - คิดตั้งแต่กิโลเมตรแรก",
    "อิงจากระยะทาง - เหมาช่วงแรก เกินคิดเพิ่มต่อกิโลเมตร"
]
use_distance_cost = st.sidebar.radio("การคิดค่าขนส่งตามระยะทาง", dist_options, key="use_distance_cost")

base_free_km, cost_per_km, distance_cost = 0.0, 0.0, 0.0
if use_distance_cost == "อิงจากระยะทาง - คิดตั้งแต่กิโลเมตรแรก":
    cost_per_km = st.sidebar.number_input("อัตราค่าขนส่ง (บาท / กิโลเมตร)", min_value=0.0, step=0.5, format="%.2f", key="cost_per_km")
    distance_cost = distance_km * cost_per_km
    distance_detail_str = f"ค่าระยะทางรวม ({distance_km:,.2f} กม. x {cost_per_km:,.2f} บาท/กม.)"
elif use_distance_cost == "อิงจากระยะทาง - เหมาช่วงแรก เกินคิดเพิ่มต่อกิโลเมตร":
    base_free_km = st.sidebar.number_input("เหมาฟรีช่วงแรกระยะทางไม่เกิน (กิโลเมตร)", min_value=0.0, step=5.0, format="%.2f", key="base_free_km")
    cost_per_km = st.sidebar.number_input(f"ส่วนที่เกินกว่า {base_free_km:,.2f} กม. คิดเพิ่ม (บาท / กิโลเมตร)", min_value=0.0, step=0.5, format="%.2f", key="cost_per_km")
    extra_km = max(0.0, distance_km - base_free_km)
    distance_cost = extra_km * cost_per_km
    distance_detail_str = f"ค่าระยะทางส่วนเกิน (รวม {distance_km:,.2f} กม. - เหมาฟรี {base_free_km:,.2f} กม. = เกิน {extra_km:,.2f} กม. x {cost_per_km:,.2f} ฿/กม.)"
else:
    distance_detail_str = f"ค่าระยะทางรวม ({distance_km:,.2f} กม. - คิดเหมา)"

# 1.7 ค่ายกถัง
st.sidebar.subheader("📦 ค่ายกถังเพิ่มเติม")
lifting_fee_per_tank = st.sidebar.number_input("ค่ายกต่อถัง (บาท)", min_value=0.0, step=1.0, format="%.2f", key="lifting_fee_per_tank")

# 1.8 ค่าเช่ารถโฟล์คลิฟท์
st.sidebar.subheader("🚜 ค่าเช่ารถโฟล์คลิฟท์ (Forklift)")
use_forklift = st.sidebar.checkbox("มีการใช้/เช่ารถโฟล์คลิฟท์", key="use_forklift")

forklift_rental_cost = 0.0
forklift_driver_cost = 0.0
total_forklift_cost = 0.0
forklift_mode = "ค่าเช่ารวมคนขับ"
num_forklifts = 1
forklift_days = 1
forklift_rate_per_day = 0.0
forklift_driver_wage_per_day = 0.0

if use_forklift:
    forklift_mode_options = ["ค่าเช่ารวมคนขับ", "ค่าเช่าแยกกับคนขับ"]
    forklift_mode = st.sidebar.radio("รูปแบบการเช่าโฟล์คลิฟท์", forklift_mode_options, key="forklift_mode")

    num_forklifts = st.sidebar.number_input("จำนวนรถโฟล์คลิฟท์ (คัน)", min_value=1, step=1, key="num_forklifts")
    forklift_days = st.sidebar.number_input("จำนวนวันที่ใช้งาน (วัน)", min_value=1, step=1, key="forklift_days")

    if forklift_mode == "ค่าเช่ารวมคนขับ":
        forklift_rate_per_day = st.sidebar.number_input("ค่าเช่ารวมคนขับ (บาท / คัน / วัน)", min_value=0.0, step=500.0, format="%.2f", key="forklift_rate_per_day")
        forklift_rental_cost = forklift_rate_per_day * num_forklifts * forklift_days
        total_forklift_cost = forklift_rental_cost
    else:
        forklift_rate_per_day = st.sidebar.number_input("ค่าเช่าเฉพาะตัวรถ (บาท / คัน / วัน)", min_value=0.0, step=500.0, format="%.2f", key="forklift_rate_per_day")
        forklift_driver_wage_per_day = st.sidebar.number_input("ค่าแรงคนขับรถโฟล์คลิฟท์ (บาท / คน / วัน)", min_value=0.0, step=100.0, format="%.2f", key="forklift_driver_wage_per_day")
        
        forklift_rental_cost = forklift_rate_per_day * num_forklifts * forklift_days
        forklift_driver_cost = forklift_driver_wage_per_day * num_forklifts * forklift_days
        total_forklift_cost = forklift_rental_cost + forklift_driver_cost

# 1.9 ตัวเลือกการแสดงผล
st.sidebar.subheader("👁️ การแสดงผลตารางสรุปราคา")
show_sub_items = st.sidebar.checkbox("แสดงรายการย่อยในตารางสรุปราคา", value=True)

# เซฟข้อมูล
st.sidebar.markdown("---")
st.sidebar.subheader("💾 บันทึกการตั้งค่าปัจจุบัน")
save_preset_name = st.sidebar.text_input("ตั้งชื่อรายการสำหรับบันทึก", placeholder="เช่น รายการส่งถังประจำวัน")
if st.sidebar.button("💾 บันทึกข้อมูลนี้", use_container_width=True):
    if save_preset_name.strip():
        history_dict[save_preset_name.strip()] = {
            "tank_input_mode": tank_input_mode,
            "num_tanks": num_tanks,
            "origins": [{"raw": o["raw"], "custom_name": o["custom_name"]} for o in origins_data],
            "destinations": [{"raw": d["raw"], "custom_name": d["custom_name"]} for d in destinations_data],
            "trucks": trucks_save_state,
            "distance_input_mode": distance_input_mode,
            "use_distance_cost": use_distance_cost, 
            "base_free_km": base_free_km,
            "cost_per_km": cost_per_km, 
            "labor_input_mode": labor_input_mode,
            "num_laborers": num_laborers,
            "base_wage": base_wage, 
            "early_morning_fee": early_morning_fee,
            "diligence_allowance": diligence_allowance, 
            "sso_company_fee": sso_company_fee,
            "lifting_fee_per_tank": lifting_fee_per_tank, 
            "use_forklift": use_forklift, 
            "forklift_mode": forklift_mode,
            "num_forklifts": num_forklifts, 
            "forklift_days": forklift_days,
            "forklift_rate_per_day": forklift_rate_per_day,
            "forklift_driver_wage_per_day": forklift_driver_wage_per_day
        }
        save_history(history_dict)
        st.session_state["pending_preset_key"] = save_preset_name.strip()
        st.sidebar.success(f"บันทึกรายการ '{save_preset_name.strip()}' สำเร็จ!")
        st.rerun()

# --- ส่วนที่ 2 & 3: คำนวณสรุปและแสดงผลตาราง ---
total_lifting_fee = lifting_fee_per_tank * num_tanks
total_shipping_cost = (
    total_base_trip_cost + distance_cost + total_labor_cost + 
    total_lifting_fee + total_extra_stop_fee + total_forklift_cost
)
cost_per_tank = total_shipping_cost / num_tanks if num_tanks > 0 else 0.0

st.markdown("<h3 style='margin-bottom: 0.8rem;'>📊 1. ตารางราคาค่าขนส่งและรายละเอียด</h3>", unsafe_allow_html=True)
col1, col2 = st.columns([2, 1])

trucks_summary_str = f"ค่าขนส่งพื้นฐานรวม ({num_trucks} คัน: {', '.join(truck_details)})"

if labor_input_mode == "กำหนดค่าแรงแบบรวม":
    labor_detail_str = f"ค่าแรงและสวัสดิการเด็กยก รวม ({num_laborers} คน @ คนละ {cost_per_laborer:,.2f} ฿)"
else:
    labor_detail_str = f"ค่าแรงและสวัสดิการเด็กยก รวมระบุตามคันรถ ({num_laborers} คน)"

origins_summary_list = [f"คลัง {o['index']}: {o['display']}" for o in origins_data]
dest_summary_list = [f"จุด {d['index']}: {d['display']}" for d in destinations_data]
route_summary_str = f"[{', '.join(origins_summary_list)}] ➔ " + " ➔ ".join(dest_summary_list)

with col1:
    breakdown_items = [
        f"เส้นทางจัดส่ง ({len(origins_data)} คลัง ➔ {len(destinations_data)} จุดส่ง): {route_summary_str}",
        trucks_summary_str, distance_detail_str
    ]
    breakdown_costs = ["-", total_base_trip_cost, distance_cost]

    if show_sub_items and distance_input_mode == "แยกระยะทางตามรายคัน":
        for idx, tr in enumerate(trucks_save_state):
            breakdown_items.append(f"  └─ ระยะทางคันที่ {idx+1} ({tr['type']}): {tr['dist_km']:,.2f} กม.")
            breakdown_costs.append("-")

    breakdown_items.append("ค่าบริการจุดส่งเพิ่มรวมจากรถทุกคัน")
    breakdown_costs.append(total_extra_stop_fee)

    if show_sub_items:
        if truck_stop_fees_breakdown:
            for item in truck_stop_fees_breakdown:
                breakdown_items.append(item["label"])
                breakdown_costs.append(item["cost"])
        else:
            breakdown_items.append("  └─ ไม่มีค่าบริการเพิ่มจุดส่ง")
            breakdown_costs.append(0.0)

    breakdown_items.append(labor_detail_str)
    breakdown_costs.append(total_labor_cost)

    if show_sub_items:
        if labor_input_mode == "กำหนดค่าแรงแบบรวม":
            breakdown_items.extend([
                f"  └─ ค่าแรงพื้นฐาน ({num_laborers} คน x {base_wage:,.2f} ฿)",
                f"  └─ ค่าออกเช้า ({num_laborers} คน x {early_morning_fee:,.2f} ฿)",
                f"  └─ ค่าเบี้ยขยัน ({num_laborers} คน x {diligence_allowance:,.2f} ฿)",
                f"  └─ ค่า บ.ส่ง ประกันสังคม ({num_laborers} คน x {sso_company_fee:,.2f} ฿)",
            ])
            breakdown_costs.extend([
                base_wage * num_laborers,
                early_morning_fee * num_laborers,
                diligence_allowance * num_laborers,
                sso_company_fee * num_laborers
            ])
        else:
            for idx, tr in enumerate(trucks_save_state):
                tr_lab_count = tr.get("num_laborers", 0)
                tr_lab_cost = (
                    tr.get("base_wage", 0.0) + tr.get("early_morning_fee", 0.0) +
                    tr.get("diligence_allowance", 0.0) + tr.get("sso_company_fee", 0.0)
                ) * tr_lab_count
                breakdown_items.append(f"  └─ คันที่ {idx+1} ({tr['type']}): เด็กยก {tr_lab_count} คน")
                breakdown_costs.append(tr_lab_cost)

    breakdown_items.append(f"ค่ายกถังรวม ({num_tanks} ถัง x {lifting_fee_per_tank:,.2f} ฿/ถัง)")
    breakdown_costs.append(total_lifting_fee)

    if use_forklift:
        forklift_title = f"ค่าเช่าโฟล์คลิฟท์รวม ({num_forklifts} คัน x {forklift_days} วัน) - {forklift_mode}"
        breakdown_items.append(forklift_title)
        breakdown_costs.append(total_forklift_cost)

        if show_sub_items:
            if forklift_mode == "ค่าเช่ารวมคนขับ":
                breakdown_items.append(f"  └─ ค่าเช่ารวมคนขับ ({num_forklifts} คัน x {forklift_days} วัน @ {forklift_rate_per_day:,.2f} ฿)")
                breakdown_costs.append(forklift_rental_cost)
            else:
                breakdown_items.append(f"  └─ ค่าเช่ารถโฟล์คลิฟท์ ({num_forklifts} คัน x {forklift_days} วัน @ {forklift_rate_per_day:,.2f} ฿)")
                breakdown_costs.append(forklift_rental_cost)
                breakdown_items.append(f"  └─ ค่าแรงคนขับโฟล์คลิฟท์ ({num_forklifts} คน x {forklift_days} วัน @ {forklift_driver_wage_per_day:,.2f} ฿)")
                breakdown_costs.append(forklift_driver_cost)

    # แปลงรูปแบบแสดงผลตัวเลขใน DataFrame
    formatted_costs = []
    for c in breakdown_costs:
        if isinstance(c, (int, float)):
            formatted_costs.append(f"{c:,.2f}")
        else:
            formatted_costs.append(str(c))

    df_breakdown = pd.DataFrame({
        "รายการคำนวณ": breakdown_items,
        "จำนวนเงิน (บาท)": formatted_costs
    })
    
    st.table(df_breakdown)

with col2:
    st.metric(label="🚚 ค่าขนส่งรวมทั้งหมด", value=f"{total_shipping_cost:,.2f} บาท")
    st.metric(label="📦 เฉลี่ยค่าขนส่งต่อถัง", value=f"{cost_per_tank:,.2f} บาท/ถัง")
    st.metric(label="📍 ระยะทางรวมทั้งหมด", value=f"{distance_km:,.2f} กม.")
    st.metric(label="📦 จำนวนถังรวม", value=f"{num_tanks:,} ถัง")

# --- ส่วนที่ 4: แสดงผลแผนที่ Folium ---
st.markdown("---")
st.markdown("### 🗺️ แผนที่เส้นทางจัดส่งสินค้า")

# คำนวณพิกัดกลางเพื่อสร้างศูนย์กลางแผนที่
all_valid_coords = []
for o in origins_data:
    if o["coord"]:
        all_valid_coords.append(o["coord"])
for d in destinations_data:
    if d["coord"]:
        all_valid_coords.append(d["coord"])

if all_valid_coords:
    avg_lat = sum(c[0] for c in all_valid_coords) / len(all_valid_coords)
    avg_lon = sum(c[1] for c in all_valid_coords) / len(all_valid_coords)
    map_center = [avg_lat, avg_lon]
    zoom_level = 10
else:
    map_center = [13.7563, 100.5018]  # กรุงเทพมหานครเป็นค่าเริ่มต้น
    zoom_level = 6

m = folium.Map(location=map_center, zoom_start=zoom_level)

# ปักหมุดคลังสินค้า/จุดต้นทาง
for o in origins_data:
    if o["coord"]:
        folium.Marker(
            location=o["coord"],
            popup=f"<b>คลังที่ {o['index']}: {o['display']}</b><br>{o['resolved_name']}",
            tooltip=f"🏢 คลังที่ {o['index']}: {o['display']}",
            icon=folium.Icon(color="black", icon="home", prefix="fa")
        ).add_to(m)

# ปักหมุดจุดส่งปลายทาง
for d in destinations_data:
    if d["coord"]:
        folium.Marker(
            location=d["coord"],
            popup=f"<b>จุดส่งที่ {d['index']}: {d['display']}</b><br>{d['resolved_name']}",
            tooltip=f"📌 จุดส่งที่ {d['index']}: {d['display']}",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)

# วาดเส้นทางสำหรับรถแต่ละคัน
for r in truck_routes_info:
    c_line = r["color"]["line"]
    if r["route_points"]:
        folium.PolyLine(
            locations=r["route_points"],
            color=c_line,
            weight=5,
            opacity=0.8,
            tooltip=f"🚚 รถคันที่ {r['truck_index']} ({r['truck_type']}) - {r['distance_km']:,.2f} กม."
        ).add_to(m)
    elif len(r["coords"]) >= 2:
        folium.PolyLine(
            locations=r["coords"],
            color=c_line,
            weight=3,
            opacity=0.5,
            dash_array="5, 10",
            tooltip=f"🚚 รถคันที่ {r['truck_index']} ({r['truck_type']}) - เส้นตรง (ไม่พบ OSRM)"
        ).add_to(m)

st_folium(m, width="100%", height=500, returned_objects=[])
