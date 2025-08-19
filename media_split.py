import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from io import BytesIO
import plotly.graph_objects as go

st.set_page_config(page_title="Media Split TV + Digital", layout="wide")
st.title("Media Split TV + Digital")

# ===========================
# Вхідні дані
# ===========================
budget = st.slider("Бюджет (грн)", 100_000, 50_000_000, 5_000_000, step=100_000)
flight_weeks = st.slider("Тривалість флайту (тижні)", 1, 30, 4)
split_step = st.selectbox("Крок спліту (%)", options=[5, 10, 15, 20], index=1)

tv_max_reach = 82
dig_max_reach = 99

# ===========================
# Введення точок TRP ↔ Reach
# ===========================
st.subheader("Введіть точки TRP ↔ Reach для естимації")

def input_points(media_name, max_reach):
    points = []
    cols = st.columns(5)
    for i in range(5):
        trp = cols[i].number_input(
            f"{media_name} TRP точка {i+1}",
            min_value=1.0,
            max_value=10000.0,
            value=float(20*(i+1)),
            step=1.0
        )
        reach = cols[i].number_input(
            f"{media_name} Reach % точка {i+1}",
            min_value=0.0,
            max_value=max_reach,
            value=float(min(max_reach, 20*(i+1))),
            step=1.0
        )
        points.append((trp, reach))
    return points

tv_points = input_points("ТБ", tv_max_reach)
dig_points = input_points("Digital", dig_max_reach)

# ===========================
# Логістична естимація
# ===========================
def logistic(x, k, x0, ymax):
    return ymax / (1 + np.exp(-k*(x-x0)))

def fit_logistic(points, max_reach):
    trp_vals, reach_vals = zip(*points)
    p0 = [0.001, np.median(trp_vals), max_reach]
    popt, _ = curve_fit(logistic, trp_vals, reach_vals, p0=p0, maxfev=10000)
    return popt

tv_k, tv_x0, tv_ymax = fit_logistic(tv_points, tv_max_reach)
dig_k, dig_x0, dig_ymax = fit_logistic(dig_points, dig_max_reach)

# ===========================
# Генерація сплітів
# ===========================
splits = np.arange(0, 1+split_step/100, split_step/100)
options = []
for s in splits:
    tv_budget = budget * s
    dig_budget = budget * (1-s)
    
    tv_trp = tv_budget / 500
    dig_trp = dig_budget / 50

    tv_reach = logistic(tv_trp, tv_k, tv_x0, tv_ymax)
    dig_reach = logistic(dig_trp, dig_k, dig_x0, dig_ymax)
    cross_reach = tv_reach + dig_reach - tv_reach*dig_reach/100

    total_cpr = budget / (cross_reach*100) if cross_reach>0 else np.nan
    effective = cross_reach>0

    options.append({
        "Опція": f"{int(s*100)}% ТБ",
        "TV_TRP": tv_trp,
        "Digital_TRP": dig_trp,
        "TV_Reach %": tv_reach,
        "Digital_Reach %": dig_reach,
        "Cross_Reach %": cross_reach,
        "CPR": total_cpr,
        "Ефективний": effective,
        "TV_бюджет": tv_budget,
        "Digital_бюджет": dig_budget
    })

df = pd.DataFrame(options)
best_idx = df[df["Ефективний"]]["CPR"].idxmin() if df["Ефективний"].any() else df["CPR"].idxmin()

# ===========================
# Таблиця в інтерфейсі
# ===========================
def highlight(row):
    color = ['']*len(row)
    if row["CPR"] == df.loc[best_idx, "CPR"]:
        color = ['background-color: lightgreen']*len(row)
    elif not row["Ефективний"]:
        color = ['background-color: lightcoral']*len(row)
    return color

st.subheader("Варіанти сплітів")
st.dataframe(df.style.apply(highlight, axis=1))

# ===========================
# Графіки в Streamlit
# ===========================
st.subheader("Графік спліту бюджету")
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df["Опція"],
    y=df["TV_бюджет"]/budget*100,
    name="ТБ",
    marker_color='black'
))
fig.add_trace(go.Bar(
    x=df["Опція"],
    y=df["Digital_бюджет"]/budget*100,
    name="Digital",
    marker_color='red'
))
fig.update_layout(barmode='stack', yaxis_title="Доля бюджету (%)")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Графік естимованого охоплення")
reach_fig = go.Figure()
reach_fig.add_trace(go.Scatter(x=df["Опція"], y=df["TV_Reach %"], mode='lines+markers', name='ТБ', line=dict(color='black')))
reach_fig.add_trace(go.Scatter(x=df["Опція"], y=df["Digital_Reach %"], mode='lines+markers', name='Digital', line=dict(color='red')))
reach_fig.add_trace(go.Scatter(x=df["Опція"], y=df["Cross_Reach %"], mode='lines+markers', name='Кросмедійне', line=dict(color='green')))
reach_fig.update_layout(yaxis_title="Reach %")
st.plotly_chart(reach_fig, use_container_width=True)

# ===========================
# Завантаження в Excel
# ===========================
st.subheader("Завантажити результати в Excel")
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Results")
    pd.DataFrame(tv_points, columns=["TRP", "Reach"]).to_excel(writer, index=False, sheet_name="TV_Points")
    pd.DataFrame(dig_points, columns=["TRP", "Reach"]).to_excel(writer, index=False, sheet_name="Digital_Points")
    
    # Додаємо графік спліту
    workbook = writer.book
    ws = writer.sheets["Results"]
    chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
    chart.add_series({'name': 'ТБ', 'categories': ['Results', 1, 0, len(df), 0], 'values': ['Results', 1, 8, len(df), 8], 'fill': {'color': 'black'}})
    chart.add_series({'name': 'Digital', 'categories': ['Results', 1, 0, len(df), 0], 'values': ['Results', 1, 9, len(df), 9], 'fill': {'color': 'red'}})
    chart.set_title({'name': 'Спліт бюджету (%)'})
    chart.set_y_axis({'name': 'Доля бюджету (%)'})
    ws.insert_chart('L2', chart)
    
st.download_button(
    "⬇️ Завантажити Excel",
    data=output.getvalue(),
    file_name="media_split.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


