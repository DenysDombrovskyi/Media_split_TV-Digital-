import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.optimize import curve_fit
from io import BytesIO

st.title("Media Split TV + Digital")

# ===========================
# Вхідні дані
# ===========================
budget = st.slider("Бюджет (грн)", 100_000, 50_000_000, 5_000_000, step=100_000)
flight_weeks = st.slider("Тривалість флайту (тижні)", 1, 30, 4)
split_step = st.selectbox("Крок спліту (%)", options=[5,10,15,20], index=1)

tv_max_reach = 82
dig_max_reach = 99

# ===========================
# Точки введення користувачем
# ===========================
st.subheader("Введіть точки для естимації охоплень")
cols = st.columns(5)
tv_points = []
dig_points = []
for i in range(5):
    tv_points.append(cols[i].number_input(f"ТБ TRP точка {i+1}", min_value=1.0, max_value=10000.0, value=20.0*(i+1)))
    dig_points.append(cols[i].number_input(f"Digital TRP точка {i+1}", min_value=1.0, max_value=10000.0, value=20.0*(i+1)))

tv_reach_input = [min(tv_max_reach, 20*(i+1)) for i in range(5)]
dig_reach_input = [min(dig_max_reach, 20*(i+1)) for i in range(5)]

# ===========================
# Логістична функція
# ===========================
def logistic(x, k, x0, ymax):
    return ymax / (1 + np.exp(-k*(x-x0)))

# Підгонка логістичної кривої
def fit_logistic(trp_points, reach_points, max_reach):
    p0 = [0.001, np.median(trp_points), max_reach]
    popt, _ = curve_fit(logistic, trp_points, reach_points, p0=p0, maxfev=10000)
    return popt

tv_k, tv_x0, tv_ymax = fit_logistic(tv_points, tv_reach_input, tv_max_reach)
dig_k, dig_x0, dig_ymax = fit_logistic(dig_points, dig_reach_input, dig_max_reach)

# ===========================
# Генерація сплітів
# ===========================
splits = np.arange(0, 1+split_step/100, split_step/100)
options = []
for s in splits:
    tv_budget = budget * s
    dig_budget = budget * (1-s)
    
    tv_trp = tv_budget / 500  # Приклад: CPT_TV=500 грн
    dig_trp = dig_budget / 50  # Приклад: CPT_Digital=50 грн

    tv_reach = logistic(tv_trp, tv_k, tv_x0, tv_ymax)
    dig_reach = logistic(dig_trp, dig_k, dig_x0, dig_ymax)
    cross_reach = tv_reach + dig_reach - tv_reach*dig_reach/100

    total_cpr = budget / (cross_reach*100) if cross_reach>0 else np.nan
    effective = True if cross_reach>0 else False

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
# Таблиця
# ===========================
def highlight(row):
    color = ['']*len(row)
    if row["CPR"] == df.loc[best_idx, "CPR"]:
        color = ['background-color: lightgreen']*len(row)
    elif not row["Ефективний"]:
        color = ['background-color: lightcoral']*len(row)
    return color

st.dataframe(df.style.apply(highlight, axis=1))

# ===========================
# Графік спліту (stacked bar)
# ===========================
fig1 = go.Figure()
fig1.add_trace(go.Bar(name='ТБ', x=df["Опція"], y=df["TV_бюджет"]/budget*100, marker_color='black'))
fig1.add_trace(go.Bar(name='Digital', x=df["Опція"], y=df["Digital_бюджет"]/budget*100, marker_color='red'))
fig1.update_layout(barmode='stack', yaxis_title="Доля бюджету %")
st.plotly_chart(fig1, use_container_width=True)

# ===========================
# Графік охоплень
# ===========================
fig2 = go.Figure()
fig2.add_trace(go.Scatter(name='ТБ', x=df["Опція"], y=df["TV_Reach %"], mode='lines+markers', line=dict(color='black')))
fig2.add_trace(go.Scatter(name='Digital', x=df["Опція"], y=df["Digital_Reach %"], mode='lines+markers', line=dict(color='red')))
fig2.add_trace(go.Scatter(name='Cross Reach', x=df["Опція"], y=df["Cross_Reach %"], mode='lines+markers', line=dict(color='blue')))
fig2.update_layout(yaxis_title="Reach %")
st.plotly_chart(fig2, use_container_width=True)

# ===========================
# Естимовані логістичні криві
# ===========================
st.subheader("Естимовані логістичні криві охоплень")
x_vals = np.linspace(0, 10000, 100)
tv_est = logistic(x_vals, tv_k, tv_x0, tv_ymax)
dig_est = logistic(x_vals, dig_k, dig_x0, dig_ymax)

fig3 = go.Figure()
fig3.add_trace(go.Scatter(name='ТБ', x=x_vals, y=tv_est, mode='lines', line=dict(color='black')))
fig3.add_trace(go.Scatter(name='Digital', x=x_vals, y=dig_est, mode='lines', line=dict(color='red')))
fig3.update_layout(xaxis_title="TRP", yaxis_title="Reach %")
st.plotly_chart(fig3, use_container_width=True)

# ===========================
# Завантаження в Excel
# ===========================
st.subheader("Завантажити результати в Excel")
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Results")
    
    workbook = writer.book
    ws = writer.sheets["Results"]

    # Додаємо графіки в Excel
    fig1.write_image("fig1.png")
    fig2.write_image("fig2.png")
    fig3.write_image("fig3.png")
    
st.download_button("⬇️ Завантажити Excel", data=output.getvalue(), file_name="media_split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



