import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.optimize import curve_fit
from io import BytesIO

# ===========================
# Перевірка xlsxwriter
# ===========================
try:
    import xlsxwriter
    XLSX_AVAILABLE = True
except ImportError:
    st.warning("Бібліотека xlsxwriter не встановлена. Завантаження Excel недоступне.")
    XLSX_AVAILABLE = False

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
# Введення точок TRP ↔ Reach
# ===========================
st.subheader("Введіть точки TRP ↔ Reach для естимації")
tv_points = []
dig_points = []

st.markdown("**ТБ**")
tv_cols = st.columns(5)
for i in range(5):
    trp = tv_cols[i].number_input(f"ТБ TRP точка {i+1}", min_value=1.0, max_value=10000.0, value=20*(i+1))
    reach = tv_cols[i].number_input(f"ТБ Reach % точка {i+1}", min_value=0.0, max_value=tv_max_reach, value=min(tv_max_reach, 20*(i+1)))
    tv_points.append((trp, reach))

st.markdown("**Digital**")
dig_cols = st.columns(5)
for i in range(5):
    trp = dig_cols[i].number_input(f"Digital TRP точка {i+1}", min_value=1.0, max_value=10000.0, value=20*(i+1))
    reach = dig_cols[i].number_input(f"Digital Reach % точка {i+1}", min_value=0.0, max_value=dig_max_reach, value=min(dig_max_reach, 20*(i+1)))
    dig_points.append((trp, reach))

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
# Excel з точками і графіками
# ===========================
if XLSX_AVAILABLE:
    st.subheader("Завантажити результати в Excel")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
        pd.DataFrame(tv_points, columns=["TRP", "Reach"]).to_excel(writer, index=False, sheet_name="TV_Points")
        pd.DataFrame(dig_points, columns=["TRP", "Reach"]).to_excel(writer, index=False, sheet_name="Digital_Points")
        # Можна додати графіки через plotly, якщо потрібно
    st.download_button(
        "⬇️ Завантажити Excel",
        data=output.getvalue(),
        file_name="media_split.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Щоб завантажити Excel, встановіть бібліотеку xlsxwriter: pip install xlsxwriter")


