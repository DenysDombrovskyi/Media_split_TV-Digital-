import streamlit as st
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import plotly.graph_objects as go
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import BarChart, Reference, LineChart

st.set_page_config(page_title="Media Split Estimator", layout="wide")
st.title("Media Split Estimator (Logistic Reach with Points)")

# ===========================
# Функції
# ===========================
def input_points(media_name, max_reach):
    st.subheader(f"Введіть точки {media_name} (TRP → Reach %)")
    trp_points = []
    reach_points = []
    cols = st.columns(5)
    for i in range(5):
        trp = cols[i].number_input(
            f"{media_name} TRP точка {i+1}",
            min_value=1.0,
            max_value=10000.0,
            value=float(50*(i+1)),
            step=1.0
        )
        reach = cols[i].number_input(
            f"{media_name} Reach % точка {i+1}",
            min_value=0.0,
            max_value=float(max_reach),
            value=min(float(max_reach), 20.0*(i+1)),
            step=0.1
        )
        trp_points.append(trp)
        reach_points.append(reach)
    return np.array(trp_points), np.array(reach_points)

def logistic(TRP, k, x0, MaxReach):
    return MaxReach / (1 + np.exp(-k * (TRP - x0)))

def fit_logistic(TRP_points, Reach_points, MaxReach):
    params, _ = curve_fit(lambda TRP, k, x0: logistic(TRP, k, x0, MaxReach),
                          TRP_points, Reach_points, p0=[0.01, np.median(TRP_points)])
    return params  # k, x0

# ===========================
# Параметри
# ===========================
tv_max_reach = 82
dig_max_reach = 99

tv_trp_pts, tv_reach_pts = input_points("ТБ", tv_max_reach)
dig_trp_pts, dig_reach_pts = input_points("Digital", dig_max_reach)

tv_k, tv_x0 = fit_logistic(tv_trp_pts, tv_reach_pts, tv_max_reach)
dig_k, dig_x0 = fit_logistic(dig_trp_pts, dig_reach_pts, dig_max_reach)

st.subheader("Бюджет та тривалість флайту")
budget = st.slider("Бюджет (грн)", 100_000, 50_000_000, 5_000_000, step=100_000)
flight_weeks = st.slider("Тривалість флайту (тижнів)", 1, 30, 4)

st.subheader("Ціна за 1 TRP")
tv_cpt = st.number_input("ТБ CPR (грн)", min_value=1.0, value=500.0)
dig_cpt = st.number_input("Digital CPR (грн)", min_value=1.0, value=500.0)

# ===========================
# Варіанти спліту
# ===========================
st.subheader("Варіанти спліту")
splits = np.linspace(0,1,10)
options = []

for s in splits:
    tv_budget = budget * s
    dig_budget = budget * (1-s)
    tv_trp = tv_budget / tv_cpt
    dig_trp = dig_budget / dig_cpt

    tv_reach = logistic(tv_trp, tv_k, tv_x0, tv_max_reach)/100
    dig_reach = logistic(dig_trp, dig_k, dig_x0, dig_max_reach)/100
    cross_reach = tv_reach + dig_reach - tv_reach*dig_reach

    total_cpr = budget / (cross_reach*100) if cross_reach>0 else np.nan
    effective = True if cross_reach>0 else False

    options.append({
        "Опція": f"{int(s*100)}% ТБ",
        "TV_TRP": tv_trp,
        "Digital_TRP": dig_trp,
        "TV_Reach %": tv_reach*100,
        "Digital_Reach %": dig_reach*100,
        "Cross_Reach %": cross_reach*100,
        "CPR": total_cpr,
        "Ефективний": effective,
        "TV_бюджет": tv_budget,
        "Digital_бюджет": dig_budget
    })

df = pd.DataFrame(options)

def highlight(row):
    color = ''
    if row["Ефективний"]:
        color = 'background-color: #b6fcd5'
    return [color]*len(row)

st.dataframe(df.style.apply(highlight, axis=1))

# ===========================
# Графіки
# ===========================
st.subheader("Графіки спліту та охоплень")
fig1 = go.Figure()
fig1.add_trace(go.Bar(name='ТБ', x=df["Опція"], y=df["TV_бюджет"]/budget*100, marker_color='black'))
fig1.add_trace(go.Bar(name='Digital', x=df["Опція"], y=df["Digital_бюджет"]/budget*100, marker_color='red'))
fig1.update_layout(barmode='stack', yaxis_title="Доля бюджету %")
st.plotly_chart(fig1, use_container_width=True)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(name='ТБ', x=df["Опція"], y=df["TV_Reach %"], mode='lines+markers', line=dict(color='black')))
fig2.add_trace(go.Scatter(name='Digital', x=df["Опція"], y=df["Digital_Reach %"], mode='lines+markers', line=dict(color='red')))
fig2.add_trace(go.Scatter(name='Cross Reach', x=df["Опція"], y=df["Cross_Reach %"], mode='lines+markers', line=dict(color='blue')))
fig2.update_layout(yaxis_title="Reach %")
st.plotly_chart(fig2, use_container_width=True)

# ===========================
# Excel
# ===========================
output = BytesIO()
wb = Workbook()
ws = wb.active
ws.title = "Media Split"

for r in dataframe_to_rows(df, index=False, header=True):
    ws.append(r)

# Додаємо графіки в Excel
bar = BarChart()
bar.type = "col"
bar.style = 10
bar.title = "Розподіл бюджету"
bar_data = Reference(ws, min_col=df.columns.get_loc("TV_бюджет")+1,
                     max_col=df.columns.get_loc("Digital_бюджет")+1,
                     min_row=1, max_row=len(df)+1)
cats = Reference(ws, min_col=df.columns.get_loc("Опція")+1, min_row=2, max_row=len(df)+1)
bar.add_data(bar_data, titles_from_data=True)
bar.set_categories(cats)
bar.y_axis.title = "Доля бюджету"
ws.add_chart(bar, "L2")

line = LineChart()
line.title = "Reach TV / Digital / Cross"
line.width = 20
line.height = 10
line_data = Reference(ws, min_col=df.columns.get_loc("TV_Reach %")+1,
                      max_col=df.columns.get_loc("Cross_Reach %")+1,
                      min_row=1, max_row=len(df)+1)
line_cats = Reference(ws, min_col=df.columns.get_loc("Опція")+1, min_row=2, max_row=len(df)+1)
line.add_data(line_data, titles_from_data=True)
line.set_categories(line_cats)
ws.add_chart(line, "P2")

wb.save(output)
st.download_button("⬇️ Завантажити Excel", output.getvalue(),
                   file_name="media_split.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


