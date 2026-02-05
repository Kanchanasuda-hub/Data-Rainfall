import os
from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_error, mean_squared_error


# ==================================================
# ภาษาไทย / ฤดูกาล / การแปลผล
# ==================================================
THAI_MONTH = [
    "มกราคม","กุมภาพันธ์","มีนาคม","เมษายน",
    "พฤษภาคม","มิถุนายน","กรกฎาคม","สิงหาคม",
    "กันยายน","ตุลาคม","พฤศจิกายน","ธันวาคม"
]

def thai_month(m): 
    return THAI_MONTH[m-1]

def season_name(m):
    if m in [5,6,7,8,9,10]:
        return "ฤดูฝน"
    if m in [11,12,1,2]:
        return "ฤดูหนาว"
    return "ฤดูร้อน"

def interpret_rain(mm):
    if mm >= 150:
        return "ตกมาก"
    if mm >= 60:
        return "ตกปานกลาง"
    if mm > 0:
        return "ตกน้อย"
    return "ไม่ตก"


# ==================================================
# เตรียมข้อมูล
# ==================================================
def prepare_data(file):
    df = pd.read_excel(file)
    df.columns = [c.strip() for c in df.columns]

    need = {"วันที่","โรงงาน","หมายเขตเขต","ชื่อเขต","ปริมาณฝนรายวัน"}
    if not need.issubset(df.columns):
        st.error("❌ คอลัมน์ในไฟล์ Excel ไม่ครบ")
        st.stop()

    df["วันที่"] = pd.to_datetime(df["วันที่"])
    df["ปริมาณฝนรายวัน"] = pd.to_numeric(
        df["ปริมาณฝนรายวัน"], errors="coerce"
    ).fillna(0)

    df["เขต"] = (
        df["หมายเขตเขต"].astype(str).str.strip()
        + " - "
        + df["ชื่อเขต"].astype(str).str.strip()
    )

    df["เดือน"] = df["วันที่"].dt.to_period("M").dt.to_timestamp()
    return df


def monthly_by_district(df):
    return (
        df.groupby(["โรงงาน","เขต","เดือน"], as_index=False)
          .agg(ฝนรวม=("ปริมาณฝนรายวัน","sum"))
    )


# ==================================================
# โมเดล + ความเชื่อมั่น
# ==================================================
def forecast_with_confidence(y, steps):
    model = SARIMAX(
        y,
        order=(1,1,1),
        seasonal_order=(1,1,1,12),
        enforce_stationarity=False,
        enforce_invertibility=False
    )
    res = model.fit(disp=False)

    fc = res.get_forecast(steps)
    mean = fc.predicted_mean.clip(lower=0)

    # ---------- ความเชื่อมั่น ----------
    if len(y) >= 24:
        train = y[:-12]
        test = y[-12:]
        pred = res.predict(start=test.index[0], end=test.index[-1]).clip(lower=0)
        rmse = np.sqrt(mean_squared_error(test, pred))
        conf = max(0, 100 - (rmse / (y.mean()+1e-6)) * 100)
    else:
        conf = 60  # default ถ้าข้อมูลสั้น

    return mean, round(conf, 1)


# ==================================================
# Export Excel
# ==================================================
def export_excel(df):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Forecast")
    bio.seek(0)
    return bio


# ==================================================
# UI
# ==================================================
st.set_page_config(page_title="พยากรณ์น้ำฝน", layout="wide")

# ---------- โลโก้ ----------
# ---------- Header + โลโก้ ----------
# ---------- Header + โลโก้ ----------
logo_url = "https://raw.githubusercontent.com/Kanchanasuda-hub/Data-Rainfall/7ed2cf8806a54c62c7cbbbd802077b68ae125f64/logo.png.jpg"

c1, c2 = st.columns([1, 6])

with c1:
    st.image(logo_url, width=120)

with c2:
    st.markdown(
        """
        <div style='display:flex; flex-direction:column; justify-content:center; height:120px;'>
            <h2 style='margin:0;'> พยากรณ์น้ำฝนรายโรงงานและเขตส่งเสริม</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

st.divider()

# ---------- Sidebar ----------
with st.sidebar:
    file = st.file_uploader("📂 อัปโหลดไฟล์ Excel", type=["xlsx"])
    steps = st.slider("พยากรณ์ล่วงหน้า (เดือน)", 3, 24, 12)
    view = st.radio("มุมมอง", ["ภาพรวมโรงงาน","รายเขต"])

if not file:
    st.info("⬅️ กรุณาอัปโหลดไฟล์ Excel")
    st.stop()

# ---------- Process ----------
df = prepare_data(file)
md = monthly_by_district(df)

factory = st.selectbox("เลือกโรงงาน", sorted(md["โรงงาน"].unique()))

if view == "รายเขต":
    district = st.selectbox(
        "เลือกเขต",
        sorted(md[md["โรงงาน"]==factory]["เขต"].unique())
    )
    data = md[(md["โรงงาน"]==factory) & (md["เขต"]==district)]
else:
    data = (
        md[md["โรงงาน"]==factory]
        .groupby("เดือน", as_index=False)
        .agg(ฝนรวม=("ฝนรวม","mean"))
    )

y = data.sort_values("เดือน").set_index("เดือน")["ฝนรวม"].asfreq("MS").fillna(0)

forecast_mean, confidence = forecast_with_confidence(y, steps)

# ---------- เฉพาะปีที่พยากรณ์ ----------
year = forecast_mean.index[0].year
plot_df = forecast_mean[forecast_mean.index.year == year]

# ---------- กราฟ ----------
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=[thai_month(d.month) for d in plot_df.index],
    y=plot_df.values,
    mode="lines+markers",
    name="Forecast"
))
fig.update_layout(
    title=f"พยากรณ์น้ำฝน ปี {year+543}",
    xaxis_title="เดือน",
    yaxis_title="ปริมาณฝน (มม.)"
)
st.plotly_chart(fig, width="stretch")

# ---------- ตาราง ----------
table = pd.DataFrame({
    "เดือน": [thai_month(d.month) for d in plot_df.index],
    "ฤดู": [season_name(d.month) for d in plot_df.index],
    "พยากรณ์ฝน (มม.)": plot_df.values.round(2),
    "แปลผล": [interpret_rain(v) for v in plot_df.values],
    "ความเชื่อมั่น (%)": confidence
})

st.dataframe(table, width="stretch")

# ---------- Export ----------
st.download_button(
    "📥 ดาวน์โหลดผลพยากรณ์ (Excel)",
    export_excel(table),
    file_name=f"Rainfall_Forecast_{factory}_{year+543}.xlsx"
)

