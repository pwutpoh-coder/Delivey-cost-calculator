import streamlit as st

# ตั้งค่าหน้าตาของแอป
try:
    st.set_page_config(
        page_title="ระบบคำนวณและจัดการค่าขนส่ง",
        page_layout="wide"
    )
except Exception:
    pass

import pandas as pd
import json
import io

# เปลี่ยนชื่อแอปแล้วตามที่ขอครับ
st.title("🚛 ระบบคำนวณและจัดการค่าขนส่ง")
st.markdown("---")

# Initialize Session State
if 'records' not in st.session_state:
    st.session_state.records = []

# ==========================================
# ส่วนที่ 1: ระบบบันทึก (Save) & เปิดไฟล์เดิม (Load)
# ==========================================
st.sidebar.header("📁 จัดการไฟล์ข้อมูล (Save / Load)")

# ปุ่มบันทึกข้อมูลออกเป็น JSON
if st.session_state.records:
    json_data = json.dumps(st.session_state.records, ensure_ascii=False, indent=2)
    st.sidebar.download_button(
        label="💾 บันทึกข้อมูลโครงการ (Save JSON)",
        data=json_data,
        file_name="transport_data.json",
        mime="application/json"
    )

# อัปโหลดไฟล์ JSON เพื่อเปิดข้อมูลเดิม
uploaded_file = st.sidebar.file_uploader("📂 เปิดไฟล์โครงการเดิม (Load JSON)", type=["json"])
if uploaded_file is not None:
    try:
        loaded_data = json.load(uploaded_file)
        if st.sidebar.button("ยืนยันการนำเข้าข้อมูล"):
            st.session_state.records = loaded_data
            st.sidebar.success("นำเข้าข้อมูลเรียบร้อยแล้ว!")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"เกิดข้อผิดพลาดในการโหลดไฟล์: {e}")

st.sidebar.markdown("---")

# ==========================================
# ส่วนที่ 2: ฟอร์มป้อนข้อมูล
# ==========================================
st.header("📝 ป้อนข้อมูลการประเมินราคา")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("1. ข้อมูลรถขนส่ง")
    
    vehicle_types = [
        "รถกระบะ4ล้อ",
        "รถ6ล้อ",
        "รถ10ล้อ",
        "รถ6ล้อมีลิฟท์ท้าย",
        "รถ10ล้อมีลิฟท์ท้าย",
        "รถเทรลเลอร์"
    ]
    selected_vehicle = st.selectbox("เลือกชนิดรถขนส่ง", vehicle_types)
    vehicle_count = st.number_input("จำนวนรถ (คัน)", min_value=0, value=1, step=1)
    vehicle_price_per_unit = st.number_input("ค่าบริการขนส่งต่อคัน (บาท)", min_value=0.0, value=0.0, step=100.0)
    
    total_vehicle_cost = vehicle_count * vehicle_price_per_unit
    st.info(f"💰 รวมค่าบริการขนส่ง: **{total_vehicle_cost:,.2f}** บาท")

with col_right:
    st.subheader("2. ข้อมูลรถโฟล์คลิฟท์")
    
    forklift_option = st.radio(
        "ตัวเลือกการเช่ารถโฟล์คลิฟท์",
        ["ไม่ต้องการเช่า", "ค่าเช่ารถโฟล์คลิฟท์รวมคนขับรถ", "ค่าเช่ารถโฟล์คลิฟท์แยกกับคนขับรถ"]
    )
    
    forklift_count = 0
    forklift_days = 0
    forklift_price_per_day = 0.0
    driver_fee_per_day = 0.0
    total_forklift_cost = 0.0
    
    if forklift_option != "ไม่ต้องการเช่า":
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            forklift_count = st.number_input("จำนวนรถโฟล์คลิฟท์ (คัน)", min_value=1, value=1, step=1)
            forklift_days = st.number_input("จำนวนวันที่ใช้งาน (วัน)", min_value=1, value=1, step=1)
        with f_col2:
            forklift_price_per_day = st.number_input("ค่าเช่ารถโฟล์คลิฟท์ต่อคัน/วัน (บาท)", min_value=0.0, value=0.0, step=500.0)
            if forklift_option == "ค่าเช่ารถโฟล์คลิฟท์แยกกับคนขับรถ":
                driver_fee_per_day = st.number_input("ค่าคนขับรถต่อคน/วัน (บาท)", min_value=0.0, value=0.0, step=300.0)
        
        if forklift_option == "ค่าเช่ารถโฟล์คลิฟท์รวมคนขับรถ":
            total_forklift_cost = forklift_count * forklift_days * forklift_price_per_day
        else:
            total_forklift_cost = (forklift_count * forklift_days * forklift_price_per_day) + (forklift_count * forklift_days * driver_fee_per_day)
            
    st.info(f"🏗️ รวมค่าเช่ารถโฟล์คลิฟท์: **{total_forklift_cost:,.2f}** บาท")

st.markdown("---")
customer_name = st.text_input("ชื่อลูกค้า / ชื่อโครงการ", placeholder="กรอกชื่อลูกค้าหรือหมายเลขอ้างอิง")
grand_total = total_vehicle_cost + total_forklift_cost

st.markdown(f"### 💵 ราคารวมสุทธิรายการนี้: :green[{grand_total:,.2f}] บาท")

if st.button("➕ เพิ่มรายการลงในตารางสรุป", type="primary"):
    if not customer_name:
        st.warning("กรุณากรอกชื่อลูกค้า / ชื่อโครงการก่อนทำการบันทึก")
    else:
        new_entry = {
            "ชื่อลูกค้า/โครงการ": customer_name,
            "ชนิดรถขนส่ง": selected_vehicle,
            "จำนวนรถ (คัน)": vehicle_count,
            "ค่าขนส่งต่อคัน (บาท)": vehicle_price_per_unit,
            "รวมค่าขนส่ง (บาท)": total_vehicle_cost,
            "ประเภทเช่าโฟล์คลิฟท์": forklift_option,
            "จำนวนโฟล์คลิฟท์ (คัน)": forklift_count,
            "จำนวนวันใช้งาน": forklift_days,
            "ค่าเช่าโฟล์คลิฟท์/วัน": forklift_price_per_day,
            "ค่าคนขับ/วัน": driver_fee_per_day if forklift_option == "ค่าเช่ารถโฟล์คลิฟท์แยกกับคนขับรถ" else 0.0,
            "รวมค่าโฟล์คลิฟท์ (บาท)": total_forklift_cost,
            "ราคารวมสุทธิ (บาท)": grand_total
        }
        st.session_state.records.append(new_entry)
        st.success("บันทึกรายการเรียบร้อยแล้ว!")

# ==========================================
# ส่วนที่ 3: แสดงผลตารางและ Export ไฟล์
# ==========================================
st.markdown("---")
st.header("📊 ตารางรายการสรุปทั้งหมด")

if st.session_state.records:
    df = pd.DataFrame(st.session_state.records)
    
    st.dataframe(df, use_container_width=True)
    
    total_all_projects = df["ราคารวมสุทธิ (บาท)"].sum()
    st.metric("ราคารวมสุทธิทุกโครงการ", f"{total_all_projects:,.2f} บาท")
    
    st.subheader("📥 Export ไฟล์รายงาน")
    exp_col1, exp_col2, exp_col3 = st.columns(3)
    
    # Export CSV
    csv_data = df.to_csv(index=False).encode('utf-8-sig')
    exp_col1.download_button(
        label="📄 Export เป็นไฟล์ CSV",
        data=csv_data,
        file_name="transport_summary_report.csv",
        mime="text/csv"
    )
    
    # Export Excel (.xlsx)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Summary')
    excel_data = excel_buffer.getvalue()
    
    exp_col2.download_button(
        label="📊 Export เป็นไฟล์ Excel (.xlsx)",
        data=excel_data,
        file_name="transport_summary_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    if exp_col3.button("🗑️ ล้างข้อมูลตารางทั้งหมด"):
        st.session_state.records = []
        st.rerun()
else:
    st.info("ยังไม่มีข้อมูลรายการในตาราง กรุณาป้อนข้อมูลด้านบนแล้วกดเพิ่มรายการ")
