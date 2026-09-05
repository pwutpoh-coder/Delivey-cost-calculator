import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import ArcGIS
import requests
import json
import os

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="ระบบคำนวณค่าขนส่งถัง", layout="wide")
st.title("🚚 แพลตฟอร์มคำนวณค่าขนส่งและวางแผนเส้นทาง")

# Initialize geolocator
geolocator = ArcGIS(timeout=10)
HISTORY_FILE = "history_data.json"

# จานสีสำหรับรถแต่ละคัน (รองรับสูงสุด 10 สี และวนซ้ำได้)
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

# --- ฟังก์ชันจัดการไฟล์ JSON บันทึก/โหลด ประวัติ ---
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

# --- ฟังก์ชันแปลงพิกัดกลับเป็นชื่อสถานที่ (Reverse Geocoding) ---
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

# --- ฟังก์ชันแปลงชื่อ/พิกัด เป็น (lat, lon) และคืนค่าชื่อสถานที่ ---
@st.cache_data(ttl=86400)
def parse_and_resolve_location(text_input):
    if not text_input:
        return None, ""
    text = text_input.strip()
    if not text:
        return None, ""
    
    if "," in text:
        try:
            parts = text.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
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

# --- ฟังก์ชันคำนวณระยะทางและเส้นทางหลายจุด (Multi-stop Routing) ---
def get_multi_stop_route(coords_list):
    if len(coords_list) < 2:
        return 0.0, []
    
    loc_str = ";".join([f"{c[1]},{c[0]}" for c in coords_list])
    try:
        osrm_url = f"http://router.project-osrm.org/route/v1/driving/{loc_str}?overview=full&geometries=geojson"
        response = requests.get(osrm_url, timeout=10)
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

# โหลดประวัติที่มีอยู่
history_dict = load_history()

# --- ส่วนจัดการประวัติและเซฟข้อมูล (Sidebar - Top) ---
st.sidebar.header("📁 จัดการและบันทึกประวัติ")

selected_preset_name = st.sidebar.selectbox(
    "📂 เลือกรายการที่เคยบันทึกไว้", 
    options=["-- เลือกรายการเพื่อโหลด --"] + list(history_dict.keys())
)

loaded_data = None
if selected_preset_name != "-- เลือกรายการเพื่อโหลด --":
    loaded_data = history_dict.get(selected_preset_name)
    st.sidebar.success(f"โหลดข้อมูล '{selected_preset_name}' เรียบร้อยแล้ว")

col_save, col_del = st.sidebar.columns(2)
if loaded_data and col_del.button("🗑️ ลบรายการนี้", use_container_width=True):
    del history_dict[selected_preset_name]
    save_history(history_dict)
    st.sidebar.warning(f"ลบรายการ '{selected_preset_name}' แล้ว")
    st.rerun()

st.sidebar.markdown("---")

# --- ส่วนที่ 1: แถบข้างสำหรับกรอกข้อมูลและตั้งค่า (Sidebar) ---
st.sidebar.header("⚙️ กำหนดค่าและปัจจัยการคำนวณ")

# 1.1 รับจำนวนถังสินค้าหลักก่อน
st.sidebar.subheader("📦 จำนวนสินค้าหลัก")
default_num_tanks = loaded_data.get("num_tanks", 0) if loaded_data else 0
num_tanks = st.sidebar.number_input("จำนวนถังที่ส่งทั้งหมด (ถัง)", min_value=0, value=int(default_num_tanks), step=10)

# 1.2 จุดต้นทาง
st.sidebar.subheader("📍 จุดต้นทาง (คลัง/ศูนย์กระจายสินค้า)")
default_raw_origin = loaded_data.get("raw_origin", "") if loaded_data else ""
default_origin_custom_name = loaded_data.get("origin_custom_name", "") if loaded_data else ""

raw_origin = st.sidebar.text_input("พิกัด/ชื่อสถานที่ต้นทาง", default_raw_origin, placeholder="เช่น 13.7563, 100.5018 หรือ กรุงเทพ")
loc_origin, resolved_origin_name = parse_and_resolve_location(raw_origin)

origin_custom_name = st.sidebar.text_input("ตั้งชื่อจุดต้นทาง (ถ้าต้องการเปลี่ยน)", default_origin_custom_name, placeholder="เช่น คลังสินค้าหลัก บางนา")

if origin_custom_name.strip():
    origin_display = origin_custom_name.strip()
elif resolved_origin_name:
    origin_display = resolved_origin_name
else:
    origin_display = "จุดต้นทาง"

if raw_origin and loc_origin:
    st.sidebar.caption(f"📍 พิกัดระบบพบ: **{resolved_origin_name}**")

# 1.3 จุดจัดส่งปลายทาง
st.sidebar.subheader("📍 จุดจัดส่งปลายทาง")
default_num_dest = loaded_data.get("num_destinations", 1) if loaded_data else 1
num_destinations = st.sidebar.number_input("จำนวนจุดจัดส่งปลายทางทั้งหมด (จุด)", min_value=1, value=int(default_num_dest), step=1)

destinations_data = []
saved_dest_list = loaded_data.get("destinations", []) if loaded_data else []

for j in range(int(num_destinations)):
    stop_num = j + 1
    
    # อ่านค่าเริ่มต้นของสถานที่และชื่อที่เคยบันทึกไว้
    default_raw = ""
    default_custom_name = ""
    if j < len(saved_dest_list):
        if isinstance(saved_dest_list[j], dict):
            default_raw = saved_dest_list[j].get("raw", "")
            default_custom_name = saved_dest_list[j].get("custom_name", "")
        else:
            default_raw = saved_dest_list[j]

    st.sidebar.markdown(f"**📌 จุดส่งที่ {stop_num}**")
    raw_dest = st.sidebar.text_input(f"ค้นหาด้วย พิกัด / ชื่อสถานที่ #{stop_num}", default_raw, key=f"dest_input_{j}", placeholder="เช่น 14.35, 100.57 หรือ อยุธยา")
    loc_dest, resolved_dest_name = parse_and_resolve_location(raw_dest)
    
    custom_name = st.sidebar.text_input(f"ตั้งชื่อจุดส่งที่ {stop_num} (ถ้าต้องการเปลี่ยน)", default_custom_name, key=f"dest_name_{j}", placeholder="เช่น สาขาอยุธยา หรือ คลัง B")

    if custom_name.strip():
        final_display_name = custom_name.strip()
    elif resolved_dest_name:
        final_display_name = resolved_dest_name
    else:
        final_display_name = f"จุดส่งที่ {stop_num}"

    if raw_dest and loc_dest:
        st.sidebar.caption(f"📍 แปลงพิกัดเป็น: **{resolved_dest_name}**")
    
    destinations_data.append({
        "index": stop_num,
        "raw": raw_dest,
        "custom_name": custom_name,
        "coord": loc_dest,
        "resolved_name": resolved_dest_name,
        "display": final_display_name
    })

# Map จุดส่งเพื่อให้ค้นหาได้ง่ายขึ้นตาม string label
dest_map = {f"จุดส่งที่ {d['index']}: {d['display']}": d for d in destinations_data}

# 1.4 รถและการมอบหมายจุดส่ง พร้อมค่าบริการเพิ่มต่อจุด
st.sidebar.subheader("🚚 เงื่อนไขการขนส่งและตั้งค่าต่อคัน")
default_num_trucks = loaded_data.get("num_trucks", 1) if loaded_data else 1
num_trucks = st.sidebar.number_input("จำนวนรถที่ใช้ (คัน)", min_value=1, value=int(default_num_trucks), step=1)

saved_trucks_list = loaded_data.get("trucks", []) if loaded_data else []

truck_details = []
trucks_save_state = []
truck_routes_info = [] # เก็บพิกัดและเส้นทาง OSRM รายคัน
total_base_trip_cost = 0.0
total_extra_stop_fee = 0.0
truck_stop_fees_breakdown = []
auto_total_distance_km = 0.0

for i in range(int(num_trucks)):
    st.sidebar.markdown(f"--- \n**🚛 คันที่ {i+1}**")
    color_info = ROUTE_COLORS[i % len(ROUTE_COLORS)]
    
    saved_truck = saved_trucks_list[i] if i < len(saved_trucks_list) else {}
    default_truck_type = saved_truck.get("type", "รถกระบะ 4 ล้อ")
    default_calc_mode = saved_truck.get("calc_mode", "เหมาจ่ายต่อเที่ยว")
    default_rate = saved_truck.get("rate", 0.0)
    default_stop_fee = saved_truck.get("extra_stop_fee", 0.0)
    default_start_fee = saved_truck.get("start_fee_from_stop", 2)
    
    type_options = ["รถกระบะ 4 ล้อ", "รถ 6 ล้อ", "รถ 10 ล้อ"]
    type_index = type_options.index(default_truck_type) if default_truck_type in type_options else 0

    t_type = st.sidebar.selectbox(f"ประเภทรถ (คันที่ {i+1})", type_options, index=type_index, key=f"truck_type_{i}")
    
    calc_mode_options = ["เหมาจ่ายต่อเที่ยว", "คิดราคาต่อถัง"]
    mode_index = calc_mode_options.index(default_calc_mode) if default_calc_mode in calc_mode_options else 0
    t_calc_mode = st.sidebar.radio(f"รูปแบบการคิดค่าขนส่ง (คันที่ {i+1})", calc_mode_options, index=mode_index, key=f"truck_mode_{i}")

    if t_calc_mode == "เหมาจ่ายต่อเที่ยว":
        t_rate = st.sidebar.number_input(f"ค่าขนส่งเหมาจ่าย (คันที่ {i+1}) [บาท]", min_value=0.0, value=float(default_rate), step=100.0, format="%.2f", key=f"truck_rate_{i}")
        t_cost = t_rate
    else:
        t_rate = st.sidebar.number_input(f"ค่าขนส่งราคาต่อถัง (คันที่ {i+1}) [บาท/ถัง]", min_value=0.0, value=float(default_rate), step=5.0, format="%.2f", key=f"truck_rate_{i}")
        t_cost = t_rate * num_tanks

    dest_options = list(dest_map.keys())
    assigned_stops = st.sidebar.multiselect(
        f"จุดส่งที่รถคันที่ {i+1} วิ่งส่ง",
        options=dest_options,
        default=dest_options if num_trucks == 1 else [],
        key=f"truck_stops_{i}"
    )
    
    stops_count = len(assigned_stops)
    
    # คำนวณเส้นทางและระยะทางเฉพาะคันนี้
    truck_coords = []
    if loc_origin:
        truck_coords.append(loc_origin)
    for stop_label in assigned_stops:
        target_dest = dest_map.get(stop_label)
        if target_dest and target_dest["coord"]:
            truck_coords.append(target_dest["coord"])

    if len(truck_coords) >= 2:
        t_dist_km, t_route_pts = get_multi_stop_route(truck_coords)
    else:
        t_dist_km, t_route_pts = 0.0, []

    auto_total_distance_km += t_dist_km

    truck_routes_info.append({
        "truck_index": i + 1,
        "truck_type": t_type,
        "assigned_stops": [dest_map[s] for s in assigned_stops if s in dest_map],
        "coords": truck_coords,
        "distance_km": t_dist_km,
        "route_points": t_route_pts,
        "color": color_info
    })

    t_start_fee_from = st.sidebar.number_input(
        f"เริ่มคิดค่าส่งเพิ่มคันที่ {i+1} ตั้งแต่จุดที่เท่าไร?",
        min_value=1,
        max_value=max(1, stops_count),
        value=min(int(default_start_fee), max(1, stops_count)),
        step=1,
        key=f"truck_start_fee_{i}"
    )
    
    t_extra_stop_fee = st.sidebar.number_input(
        f"ค่าบริการเพิ่มต่อจุด (คันที่ {i+1}) [บาท/จุด]", 
        min_value=0.0, 
        value=float(default_stop_fee), 
        step=100.0, 
        format="%.2f", 
        key=f"truck_stop_fee_{i}"
    )

    charged_stops_for_truck = max(0, stops_count - int(t_start_fee_from) + 1) if stops_count >= t_start_fee_from else 0
    truck_total_stop_fee = charged_stops_for_truck * t_extra_stop_fee
    total_extra_stop_fee += truck_total_stop_fee

    if charged_stops_for_truck > 0:
        truck_stop_fees_breakdown.append({
            "label": f"  └─ คันที่ {i+1} ({t_type}): คิด {charged_stops_for_truck} จุด (จุดที่ {t_start_fee_from} ขึ้นไป) @ {t_extra_stop_fee:,.2f} ฿",
            "cost": truck_total_stop_fee
        })

    if t_calc_mode == "เหมาจ่ายต่อเที่ยว":
        truck_details.append(f"{t_type} ({t_cost:,.2f} ฿ [เหมา] - วิ่ง {stops_count} จุด / {t_dist_km:,.2f} กม.)")
    else:
        truck_details.append(f"{t_type} ({t_rate:,.2f} ฿/ถัง x {num_tanks} ถัง = {t_cost:,.2f} ฿ - วิ่ง {stops_count} จุด / {t_dist_km:,.2f} กม.)")

    trucks_save_state.append({
        "type": t_type,
        "calc_mode": t_calc_mode,
        "rate": float(t_rate),
        "extra_stop_fee": float(t_extra_stop_fee),
        "start_fee_from_stop": int(t_start_fee_from)
    })

    total_base_trip_cost += float(t_cost)

# 1.5 คำนวณระยะทางรวมอัตโนมัติ
st.sidebar.subheader("📏 เงื่อนไขระยะทาง")
distance_km = st.sidebar.number_input(
    "ระยะทางรวมทุกคัน (กิโลเมตร)", 
    min_value=0.0, 
    value=float(auto_total_distance_km), 
    step=1.0,
    format="%.2f"
)

dist_options = [
    "ไม่อิงจากระยะทาง (คิดเหมา)",
    "อิงจากระยะทาง - คิดตั้งแต่กิโลเมตรแรก",
    "อิงจากระยะทาง - เหมาช่วงแรก เกินคิดเพิ่มต่อกิโลเมตร"
]

default_dist_mode = loaded_data.get("use_distance_cost", "ไม่อิงจากระยะทาง (คิดเหมา)") if loaded_data else "ไม่อิงจากระยะทาง (คิดเหมา)"
dist_index = dist_options.index(default_dist_mode) if default_dist_mode in dist_options else 0

use_distance_cost = st.sidebar.radio(
    "การคิดค่าขนส่งตามระยะทาง",
    dist_options,
    index=dist_index
)

base_free_km = 0.0
cost_per_km = 0.0
distance_cost = 0.0
distance_detail_str = ""

if use_distance_cost == "อิงจากระยะทาง - คิดตั้งแต่กิโลเมตรแรก":
    default_cost_per_km = loaded_data.get("cost_per_km", 0.0) if loaded_data else 0.0
    cost_per_km = st.sidebar.number_input("อัตราค่าขนส่ง (บาท / กิโลเมตร)", min_value=0.0, value=float(default_cost_per_km), step=0.5, format="%.2f")
    distance_cost = distance_km * cost_per_km
    distance_detail_str = f"ค่าระยะทางรวม ({distance_km:,.2f} กม. x {cost_per_km:,.2f} บาท/กม.)"

elif use_distance_cost == "อิงจากระยะทาง - เหมาช่วงแรก เกินคิดเพิ่มต่อกิโลเมตร":
    default_free_km = loaded_data.get("base_free_km", 0.0) if loaded_data else 0.0
    default_cost_per_km = loaded_data.get("cost_per_km", 0.0) if loaded_data else 0.0
    
    base_free_km = st.sidebar.number_input("เหมาฟรีช่วงแรกระยะทางไม่เกิน (กิโลเมตร)", min_value=0.0, value=float(default_free_km), step=5.0, format="%.2f")
    cost_per_km = st.sidebar.number_input(f"ส่วนที่เกินกว่า {base_free_km:,.2f} กม. คิดเพิ่ม (บาท / กิโลเมตร)", min_value=0.0, value=float(default_cost_per_km), step=0.5, format="%.2f")
    
    extra_km = max(0.0, distance_km - base_free_km)
    distance_cost = extra_km * cost_per_km
    distance_detail_str = f"ค่าระยะทางส่วนเกิน (รวม {distance_km:,.2f} กม. - เหมาฟรี {base_free_km:,.2f} กม. = เกิน {extra_km:,.2f} กม. x {cost_per_km:,.2f} ฿/กม.)"

else:
    distance_cost = 0.0
    distance_detail_str = f"ค่าระยะทางรวม ({distance_km:,.2f} กม. - คิดเหมา)"

# 1.6 รายละเอียดค่าแรงเด็กยก
st.sidebar.subheader("👷 รายละเอียดค่าแรงและสวัสดิการเด็กยก")
default_laborers = loaded_data.get("num_laborers", 0) if loaded_data else 0
num_laborers = st.sidebar.number_input("จำนวนเด็กยกทั้งหมด (คน)", min_value=0, value=int(default_laborers), step=1)

if num_laborers > 0:
    b_wage = loaded_data.get("base_wage", 0.0) if loaded_data else 0.0
    e_fee = loaded_data.get("early_morning_fee", 0.0) if loaded_data else 0.0
    d_allow = loaded_data.get("diligence_allowance", 0.0) if loaded_data else 0.0
    s_fee = loaded_data.get("sso_company_fee", 0.0) if loaded_data else 0.0

    base_wage = st.sidebar.number_input("1. ค่าแรงพื้นฐาน (บาท/คน)", min_value=0.0, value=float(b_wage), step=50.0, format="%.2f")
    early_morning_fee = st.sidebar.number_input("2. ค่าออกเช้า (บาท/คน)", min_value=0.0, value=float(e_fee), step=10.0, format="%.2f")
    diligence_allowance = st.sidebar.number_input("3. ค่าเบี้ยขยัน (บาท/คน)", min_value=0.0, value=float(d_allow), step=10.0, format="%.2f")
    sso_company_fee = st.sidebar.number_input("4. ค่า บ.ส่ง ประกันสังคม (บาท/คน)", min_value=0.0, value=float(s_fee), step=5.0, format="%.2f")
else:
    base_wage = early_morning_fee = diligence_allowance = sso_company_fee = 0.0

cost_per_laborer = base_wage + early_morning_fee + diligence_allowance + sso_company_fee
total_labor_cost = cost_per_laborer * num_laborers

# 1.7 ค่ายกถัง
st.sidebar.subheader("📦 ค่ายกถังเพิ่มเติม")
default_lifting_fee = loaded_data.get("lifting_fee_per_tank", 0.0) if loaded_data else 0.0
lifting_fee_per_tank = st.sidebar.number_input("ค่ายกต่อถัง (บาท)", min_value=0.0, value=float(default_lifting_fee), step=1.0, format="%.2f")

# 1.8 ตั้งค่าการแสดงผลตารางราคา
st.sidebar.subheader("👁️ การแสดงผลตารางสรุปราคา")
show_sub_items = st.sidebar.checkbox("แสดงรายการย่อยในตารางสรุปราคา (จุดส่งเพิ่ม / รายละเอียดค่าแรง)", value=True)

# --- ส่วนเซฟข้อมูลลงไฟล์ ---
st.sidebar.markdown("---")
st.sidebar.subheader("💾 บันทึกการตั้งค่าปัจจุบัน")
save_preset_name = st.sidebar.text_input("ตั้งชื่อรายการสำหรับบันทึก", placeholder="เช่น รายการส่งถังประจำวัน")
if st.sidebar.button("💾 บันทึกข้อมูลนี้", use_container_width=True):
    if save_preset_name.strip():
        save_payload = {
            "raw_origin": raw_origin,
            "origin_custom_name": origin_custom_name,
            "num_destinations": num_destinations,
            "destinations": [
                {"raw": d["raw"], "custom_name": d["custom_name"]} 
                for d in destinations_data
            ],
            "num_trucks": num_trucks,
            "trucks": trucks_save_state,
            "use_distance_cost": use_distance_cost,
            "base_free_km": base_free_km,
            "cost_per_km": cost_per_km,
            "num_laborers": num_laborers,
            "base_wage": base_wage,
            "early_morning_fee": early_morning_fee,
            "diligence_allowance": diligence_allowance,
            "sso_company_fee": sso_company_fee,
            "lifting_fee_per_tank": lifting_fee_per_tank,
            "num_tanks": num_tanks
        }
        history_dict[save_preset_name.strip()] = save_payload
        save_history(history_dict)
        st.sidebar.success(f"บันทึกรายการ '{save_preset_name.strip()}' สำเร็จ!")
        st.rerun()

# --- ส่วนที่ 2: ประมวลผลคำนวณสรุปราคา ---
total_lifting_fee = lifting_fee_per_tank * num_tanks
total_shipping_cost = total_base_trip_cost + distance_cost + total_labor_cost + total_lifting_fee + total_extra_stop_fee
cost_per_tank = total_shipping_cost / num_tanks if num_tanks > 0 else 0.0

# --- ส่วนที่ 3: แสดงผลตารางสรุปราคา ---
st.header("📊 1. ตารางราคาค่าขนส่งและรายละเอียด")

col1, col2 = st.columns([2.2, 1])

trucks_summary_str = f"ค่าขนส่งพื้นฐานรวม ({num_trucks} คัน: {', '.join(truck_details)})"
labor_detail_str = f"ค่าแรงและสวัสดิการเด็กยก ({num_laborers} คน @ คนละ {cost_per_laborer:,.2f} ฿)"

dest_summary_list = [f"จุด {d['index']}: {d['display']}" for d in destinations_data]
route_summary_str = f"{origin_display} ➔ " + " ➔ ".join(dest_summary_list)

with col1:
    breakdown_items = [
        f"เส้นทางจัดส่ง ({len(destinations_data)} จุดส่ง): {route_summary_str}",
        trucks_summary_str,
        distance_detail_str,
        f"ค่าบริการจุดส่งเพิ่มรวมจากรถทุกคัน",
    ]
    breakdown_costs = [
        "-",
        total_base_trip_cost,
        distance_cost,
        total_extra_stop_fee
    ]

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
            sso_company_fee * num_laborers,
        ])

    breakdown_items.extend([
        f"ค่ายกถัง ({num_tanks} ถัง x {lifting_fee_per_tank:,.2f} ฿)",
        "รวมค่าขนส่งสุทธิ"
    ])

    breakdown_costs.extend([
        total_lifting_fee,
        total_shipping_cost
    ])

    formatted_costs = []
    formatted_per_tank = []

    for c in breakdown_costs:
        if isinstance(c, (int, float)):
            formatted_costs.append(f"{c:,.2f}")
            if num_tanks > 0:
                per_tank_val = c / num_tanks
                formatted_per_tank.append(f"{per_tank_val:,.2f}")
            else:
                formatted_per_tank.append("0.00")
        else:
            formatted_costs.append(str(c))
            formatted_per_tank.append("-")

    df_breakdown = pd.DataFrame({
        "รายการ": breakdown_items,
        "จำนวนเงินรวม (บาท)": formatted_costs,
        "ราคาต่อถัง (บาท/ถัง)": formatted_per_tank
    })
    st.table(df_breakdown)

with col2:
    st.metric(label="🎯 ค่าขนส่งรวมทั้งหมด", value=f"{total_shipping_cost:,.2f} บาท")
    st.metric(
        label="🏷️ ค่าขนส่งต่อถัง (เฉลี่ยรวม)", 
        value=f"{cost_per_tank:,.2f} ฿/ถัง",
        delta=f"ส่งทั้งหมด {num_tanks} ถัง ({num_trucks} คัน / {len(destinations_data)} จุดส่ง)",
        delta_color="off"
    )

st.markdown("---")

# --- ส่วนที่ 4: แสดงผลแผนที่ ---
st.header("🗺️ 2. แผนที่แสดงจุดจัดส่งและเส้นทางถนนจริง (แยกสีตามคันรถ)")

all_valid_coords = []
if loc_origin:
    all_valid_coords.append(loc_origin)
for d in destinations_data:
    if d["coord"]:
        all_valid_coords.append(d["coord"])

# กำหนดค่าเริ่มต้นแผนที่
if len(all_valid_coords) >= 1:
    avg_lat = sum(c[0] for c in all_valid_coords) / len(all_valid_coords)
    avg_lon = sum(c[1] for c in all_valid_coords) / len(all_valid_coords)
    zoom_level = 9
else:
    avg_lat, avg_lon = 13.7563, 100.5018  # พิกัดกรุงเทพมหานคร
    zoom_level = 6

m = folium.Map(location=[avg_lat, avg_lon], zoom_start=zoom_level)

# 1. หมุดจุดต้นทาง
if loc_origin:
    folium.Marker(
        loc_origin, 
        popup=f"ต้นทาง: {origin_display}", 
        tooltip=f"ต้นทาง: {origin_display}", 
        icon=folium.Icon(color="black", icon="play", prefix="fa")
    ).add_to(m)

# 2. วาดเส้นทางและปักหมุดจุดส่งแยกตามคันรถ
for t_info in truck_routes_info:
    t_idx = t_info["truck_index"]
    t_type = t_info["truck_type"]
    color_line = t_info["color"]["line"]
    color_marker = t_info["color"]["marker"]
    
    # วาดเส้นทาง OSRM ของรถคันนี้
    if t_info["route_points"]:
        folium.PolyLine(
            t_info["route_points"], 
            color=color_line, 
            weight=5, 
            opacity=0.8, 
            tooltip=f"คันที่ {t_idx} ({t_type}): {t_info['distance_km']:,.2f} กม."
        ).add_to(m)
    elif len(t_info["coords"]) >= 2:
        folium.PolyLine(
            t_info["coords"], 
            color=color_line, 
            weight=3, 
            opacity=0.5, 
            dash_array="5, 10",
            tooltip=f"คันที่ {t_idx} ({t_type}) - เส้นตรงจำลอง"
        ).add_to(m)

    # ปักหมุดเฉพาะจุดส่งที่รถคันนี้ได้รับมอบหมาย
    for stop_item in t_info["assigned_stops"]:
        if stop_item["coord"]:
            folium.Marker(
                stop_item["coord"], 
                popup=f"รถคันที่ {t_idx} ({t_type}) <br>จุดส่งที่ {stop_item['index']}: {stop_item['display']}", 
                tooltip=f"คันที่ {t_idx} ➔ จุดส่งที่ {stop_item['index']}: {stop_item['display']}", 
                icon=folium.Icon(color=color_marker, icon="flag")
            ).add_to(m)

# ปักหมุดจุดส่งที่ยังไม่ถูกมอบหมายให้รถคันใดเลย (ถ้ามี)
assigned_dest_indices = set()
for t_info in truck_routes_info:
    for s in t_info["assigned_stops"]:
        assigned_dest_indices.add(s["index"])

for d in destinations_data:
    if d["index"] not in assigned_dest_indices and d["coord"]:
        folium.Marker(
            d["coord"], 
            popup=f"ยังไม่ได้มอบหมายรถ <br>จุดส่งที่ {d['index']}: {d['display']}", 
            tooltip=f"⚠️ ยังไม่ได้เลือก คันที่จะส่งจุดที่ {d['index']}", 
            icon=folium.Icon(color="gray", icon="info-sign")
        ).add_to(m)

# แสดงผลแผนที่
st_folium(m, width=1000, height=450)
