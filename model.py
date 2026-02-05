# ==================================================
# UI THEME STYLE
# ==================================================
st.set_page_config(page_title="พยากรณ์น้ำฝน", layout="wide")

st.markdown("""
<style>
    .main { background-color: #F4F8FF; }

    h1, h2, h3 { color: #0B3C8C; }

    .block-container { padding-top: 1rem; }

    .css-1aumxhk {
        background-color: #0B3C8C;
        color: white;
    }

    div.stButton > button {
        background-color: #0B3C8C;
        color: white;
        border-radius: 10px;
    }

    div[data-testid="stMetric"] {
        background: #E8F0FF;
        padding: 10px;
        border-radius: 12px;
        border-left: 5px solid #0B3C8C;
    }

    table {
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)


# ---------- Header + โลโก้ ----------
logo_url = "https://raw.githubusercontent.com/Kanchanasuda-hub/Data-Rainfall/7ed2cf8806a54c62c7cbbbd802077b68ae125f64/logo.png.jpg"

c1, c2 = st.columns([1, 6])

with c1:
    st.image(logo_url, width=120)

with c2:
    st.markdown("""
    <div style='background:#0B3C8C; padding:20px; border-radius:15px;'>
        <h2 style='color:white; margin:0;'>
        🌧️ พยากรณ์น้ำฝนรายโรงงานและเขตส่งเสริม
        </h2>
        <p style='color:#D9E6FF;'>ระบบวิเคราะห์และคาดการณ์ปริมาณฝนด้วย SARIMAX</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("## ⚙️ ตั้งค่าการวิเคราะห์")
    file = st.file_uploader("📂 อัปโหลดไฟล์ Excel", type=["xlsx"])
    steps = st.slider("พยากรณ์ล่วงหน้า (เดือน)", 3, 24, 12)
    view = st.radio("มุมมอง", ["ภาพรวมโรงงาน","รายเขต"])

if not file:
    st.info("⬅️ กรุณาอัปโหลดไฟล์ Excel เพื่อเริ่มต้น")
    st.stop()

# ---------- Process ----------
df = prepare_data(file)
md = monthly_by_district(df)

factory = st.selectbox("🏭 เลือกโรงงาน", sorted(md["โรงงาน"].unique()))

if view == "รายเขต":
    district = st.selectbox(
        "📍 เลือกเขต",
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

year = forecast_mean.index[0].year
plot_df = forecast_mean[forecast_mean.index.year == year]


# ==================================================
# DASHBOARD METRIC
# ==================================================
c1, c2, c3 = st.columns(3)

with c1:
    st.metric("🎯 ความเชื่อมั่นโมเดล", f"{confidence}%")

with c2:
    st.metric("🌧️ ฝนเฉลี่ยพยากรณ์",
              f"{round(plot_df.mean(),2)} มม.")

with c3:
    st.metric("📅 ปีพยากรณ์", f"พ.ศ. {year+543}")


# ==================================================
# กราฟ
# ==================================================
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=[thai_month(d.month) for d in plot_df.index],
    y=plot_df.values,
    mode="lines+markers",
    line=dict(color="#0B3C8C", width=3),
    marker=dict(size=8, color="#1F77FF"),
    name="Forecast"
))

fig.update_layout(
    title=f"พยากรณ์น้ำฝน ปี {year+543}",
    xaxis_title="เดือน",
    yaxis_title="ปริมาณฝน (มม.)",
    plot_bgcolor="white",
    paper_bgcolor="#F4F8FF"
)

st.plotly_chart(fig, use_container_width=True)


# ==================================================
# ตารางสวยงาม
# ==================================================
table = pd.DataFrame({
    "เดือน": [thai_month(d.month) for d in plot_df.index],
    "ฤดู": [season_name(d.month) for d in plot_df.index],
    "พยากรณ์ฝน (มม.)": plot_df.values.round(2),
    "แปลผล": [interpret_rain(v) for v in plot_df.values],
    "ความเชื่อมั่น (%)": confidence
})

st.markdown("### 📋 ตารางผลพยากรณ์")

st.dataframe(
    table.style.background_gradient(
        subset=["พยากรณ์ฝน (มม.)"],
        cmap="Blues"
    ),
    use_container_width=True
)


# ==================================================
# Export
# ==================================================
st.download_button(
    "📥 ดาวน์โหลดผลพยากรณ์ (Excel)",
    export_excel(table),
    file_name=f"Rainfall_Forecast_{factory}_{year+543}.xlsx"
)


