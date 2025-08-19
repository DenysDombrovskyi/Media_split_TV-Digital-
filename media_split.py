import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

# --- Бічна панель ---
st.sidebar.header("Параметри кампанії")
budget = st.sidebar.number_input("Бюджет кампанії, грн", 100000, 50000000, 5000000, step=100000)
step = st.sidebar.selectbox("Крок спліту по бюджету (%)", [5,10,15,20], index=1)
tv_price = st.sidebar.number_input("Вартість 1 TRP ТБ, грн", 100, 5000, 500)
digital_price = st.sidebar.number_input("Вартість 1000 імпресій, грн", 1, 1000, 50)
tv_clutter = st.sidebar.number_input("Клаттер конкурентів ТБ (TRP/тиждень)", 0, 10000, 100)
digital_clutter = st.sidebar.number_input("Клаттер конкурентів Діджитал (імпр.)", 0, 10000000, 500000)
num_options = st.sidebar.number_input("Кількість опцій", 1, 20, 10)
estimation_method = st.sidebar.selectbox("Метод естимації охоплень", ["Логістична крива", "Апроксимація"], index=0)

# --- Введення точок для ТБ ---
st.header("Точки ТБ")
tv_trp_points = []
tv_reach_points = []
for i in range(5):
    cols = st.columns(2)
    tv_trp_points.append(cols[0].number_input(f"ТРП точка {i+1}", 1, 10000, 20*(i+1)))
    tv_reach_points.append(cols[1].number_input(f"Охоплення % точка {i+1}", 1, 82, 20*(i+1)))

# --- Введення точок для Діджитал ---
st.header("Точки Діджитал")
dig_trp_points = []
dig_reach_points = []
for i in range(5):
    cols = st.columns(2)
    dig_trp_points.append(cols[0].number_input(f"TRP Діджитал точка {i+1}", 1, 10000, 100*(i+1)))
    dig_reach_points.append(cols[1].number_input(f"Охоплення % точка {i+1}", 1, 99, 10*(i+1)))

# --- Естимація охоплень (приклад для логістичної кривої) ---
def estimate_reach(trp_points, reach_points, max_reach):
    trp = np.array(trp_points)
    reach = np.array(reach_points)/100
    # Логістична апроксимація
    from scipy.optimize import curve_fit
    def logistic(x, a, b):
        return max_reach / (1 + np.exp(-a*(x-b)))
    params, _ = curve_fit(logistic, trp, reach, maxfev=10000)
    return lambda x: logistic(x, *params)

tv_reach_func = estimate_reach(tv_trp_points, tv_reach_points, 82)
dig_reach_func = estimate_reach(dig_trp_points, dig_reach_points, 99)

# --- Створення опцій ---
options = []
for i in range(num_options):
    tv_trp = int((i+1)*step/100*budget/tv_price)
    dig_trp = int((i+1)*step/100*budget/digital_price)
    tv_reach = tv_reach_func(tv_trp)
    dig_reach = dig_reach_func(dig_trp)
    cross_reach = tv_reach + dig_reach - tv_reach*dig_reach
    cpr = (tv_trp*tv_price + dig_trp*digital_price)/cross_reach
    effective = (tv_trp>=tv_clutter) and (dig_trp>=digital_clutter)
    options.append([i+1, tv_trp, dig_trp, tv_reach*100, dig_reach*100, cross_reach*100, cpr, effective])

df = pd.DataFrame(options, columns=["Опція","ТРП ТБ","ТРП Діджитал","Охопл. ТБ %","Охопл. Діджитал %","Кросмедіа %","CPR","Ефективний"])
st.dataframe(df.style.apply(lambda x: ['background-color: lightgreen' if v else 'background-color: salmon' for v in x=='Ефективний'], axis=1))

# --- Графік спліту ---
fig, ax = plt.subplots()
ax.bar(df["Опція"], df["ТРП ТБ"], color='black', label='ТБ')
ax.bar(df["Опція"], df["ТРП Діджитал"], bottom=df["ТРП ТБ"], color='red', label='Діджитал')
ax.set_ylabel("Долі бюджету")
ax.set_xlabel("Опція")
ax.legend()
st.pyplot(fig)

# --- Вивантаження в Excel ---
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name="Опції", index=False)
st.download_button("Завантажити в Excel", data=output.getvalue(), file_name="media_split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

