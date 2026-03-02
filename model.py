import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_squared_error

# ===============================
# ตั้งค่าหน้าเว็บ
# ===============================
st.set_page_config(layout="wide")
st.title("พยากรณ์ปริมาณฝนรายเดือน")

# ===============================
# Upload File
# ===============================
file = st.file_uploader("📂 อัปโหลดไฟล์ Excel", type=["xlsx"])

if file is not None:

    # ===============================
    # อ่านไฟล์
    # ===============================
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    required_cols = ["วันที่", "ชื่อเขต", "ปริมาณฝนรายวัน"]
    for col in required_cols:
        if col not in df.columns:
            st.error(f"ไม่พบคอลัมน์: {col}")
            st.stop()

    df["วันที่"] = pd.to_datetime(df["วันที่"])
    df = df.sort_values("วันที่")

    # ===============================
    # Sidebar
    # ===============================
    st.sidebar.header("ตั้งค่า")

    forecast_months = st.sidebar.slider(
        "พยากรณ์ล่วงหน้า (เดือน)",
        1, 12, 12
    )

    view_type = st.sidebar.radio(
        "มุมมอง",
        ["ภาพรวมโรงงาน", "รายเขต"]
    )

    if view_type == "รายเขต":
        region = st.sidebar.selectbox(
            "เลือกเขต",
            df["ชื่อเขต"].unique()
        )
        df = df[df["ชื่อเขต"] == region]

    # ===============================
    # สร้างข้อมูลรายเดือน
    # ===============================
    if view_type == "ภาพรวมโรงงาน":

        monthly_per_region = (
            df.groupby(["ชื่อเขต", pd.Grouper(key="วันที่", freq="M")])["ปริมาณฝนรายวัน"]
            .sum()
            .reset_index()
        )

        df_monthly = (
            monthly_per_region
            .groupby("วันที่")["ปริมาณฝนรายวัน"]
            .mean()
            .reset_index()
        )

    else:
        df_monthly = (
            df.resample("M", on="วันที่")["ปริมาณฝนรายวัน"]
            .sum()
            .reset_index()
        )

    df_monthly = df_monthly.dropna()

    st.subheader("📈 ข้อมูลรายเดือนย้อนหลัง")
    st.dataframe(df_monthly.tail(), use_container_width=True)

    # ===============================
    # Train/Test
    # ===============================
    train_size = int(len(df_monthly) * 0.8)

    if train_size < 12:
        st.warning("ข้อมูลย้อนหลังน้อยเกินไป (ควรมีอย่างน้อย 2 ปี)")
        st.stop()

    train = df_monthly["ปริมาณฝนรายวัน"][:train_size]
    test = df_monthly["ปริมาณฝนรายวัน"][train_size:]

    # ===============================
    # SARIMA
    # ===============================
    model = SARIMAX(
        train,
        order=(1,0,1),
        seasonal_order=(1,1,0,12),
        enforce_stationarity=True,
        enforce_invertibility=True
    )

    result = model.fit(disp=False)
    pred_test = result.forecast(len(test))
    rmse = np.sqrt(mean_squared_error(test, pred_test))

    # ===============================
    # Final Forecast
    # ===============================
    final_model = SARIMAX(
        df_monthly["ปริมาณฝนรายวัน"],
        order=(1,0,1),
        seasonal_order=(1,1,0,12),
        enforce_stationarity=True,
        enforce_invertibility=True
    )

    final_result = final_model.fit(disp=False)
    forecast = final_result.forecast(forecast_months)

    # กันค่าติดลบ
    forecast = np.maximum(forecast, 0)

    # smoothing ลดความแกว่ง
    forecast = pd.Series(forecast).rolling(2, min_periods=1).mean()

    # จำกัดไม่ให้เกิน 120% ของค่าสูงสุดในอดีต
    historical_max = df_monthly["ปริมาณฝนรายวัน"].max()
    forecast = np.minimum(forecast, historical_max * 1.2)

    future_dates = pd.date_range(
        start=df_monthly["วันที่"].max(),
        periods=forecast_months+1,
        freq="M"
    )[1:]

    # ===============================
    # เดือนภาษาไทย
    # ===============================
    thai_months = {
        1: "มกราคม",
        2: "กุมภาพันธ์",
        3: "มีนาคม",
        4: "เมษายน",
        5: "พฤษภาคม",
        6: "มิถุนายน",
        7: "กรกฎาคม",
        8: "สิงหาคม",
        9: "กันยายน",
        10: "ตุลาคม",
        11: "พฤศจิกายน",
        12: "ธันวาคม"
    }

    thai_labels = [thai_months[m] for m in future_dates.month]

    forecast_df = pd.DataFrame({
        "เดือน": thai_labels,
        "พยากรณ์ฝน (มม.)": forecast.values
    })

    # ===============================
    # แปลผล (รายเดือน)
    # ===============================
    def interpret_rain(mm):
        if mm <= 0:
            return "ไม่ตก"
        elif mm <= 50:
            return "ฝนเล็กน้อย"
        elif mm <= 200:
            return "ฝนปานกลาง"
        elif mm <= 400:
            return "ฝนหนัก"
        else:
            return "ฝนหนักมาก"

    forecast_df["แปลผล"] = forecast_df["พยากรณ์ฝน (มม.)"].apply(interpret_rain)

    # ===============================
    # Confidence
    # ===============================
    mean_rain = df_monthly["ปริมาณฝนรายวัน"].mean()
    confidence = max(0, 100 * (1 - (rmse / mean_rain)))
    forecast_df["ความเชื่อมั่น (%)"] = round(confidence, 2)

    forecast_df = forecast_df[
        ["เดือน", "พยากรณ์ฝน (มม.)", "แปลผล", "ความเชื่อมั่น (%)"]
    ]

    # ===============================
    # แสดงผล
    # ===============================
    st.subheader("📅 ผลพยากรณ์ล่วงหน้า")
    st.dataframe(
        forecast_df.style.format({"พยากรณ์ฝน (มม.)": "{:.2f}"}),
        use_container_width=True
    )

    # ===============================
    # กราฟเฉพาะ Forecast
    # ===============================
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=thai_labels,
        y=forecast,
        mode="lines+markers",
        name="Forecast",
        line=dict(width=3)
    ))

    fig.update_layout(
        title="พยากรณ์ปริมาณฝนรายเดือน",
        xaxis_title="เดือน",
        yaxis_title="ปริมาณฝน (มม.)",
        template="plotly_white"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("กรุณาอัปโหลดไฟล์ก่อน")
