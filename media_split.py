import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from openpyxl import Workbook
from io import BytesIO

# --- Інтерфейс ---
st.title("Оптимізація медіа спліту")

budget = st.slider("Бюджет, грн", 100000, 50000000, 1000000, step=500000)
split_step = st.selectbox("Крок спліту по бюджету (%)", [5, 10, 15, 20])
tv_cost = st.number_input("Вартість 1 TRP ТБ", value=500)
digital_cost = st.number_input("Вартість 1 CPM Digital", value=100)

# --- Дані для естимації ---
st.subheader("Введіть точки для естимації охоплень")
tv_points = [st.number_input(f"ТБ TRP точка {i+1}", 1, 10000, value=20*(i+1)) for i in range(5)]
tv_reach = [st.number_input(f"ТБ Reach % точка {i+1}", 1, 82, value=min(82, 20*(i+1))) for i in range(5)]

digital_points = [st.number_input(f"Digital TRP точка {i+1}", 1, 10000, value=20*(i+1)) for i in range(5)]
digital_reach = [st.number_input(f"Digital Reach % точка {i+1}", 1, 99, value=min(99, 20*(i+1))) for i in range(5)]

# --- Естимація охоплень через логістичну функцію ---
def logistic_estimation(x, x_points, y_points, max_reach):
    from scipy.optimize import curve_fit
    def logistic(x, a, b):
        return max_reach / (1 + np.exp(-a*(x-b)))
    popt, _ = curve_fit(logistic, x_points, y_points, maxfev=10000)
    return logistic(x, *popt)

# --- Побудова таблиці опцій ---
options = []
for step in range(0, 101, split_step):
    tv_trp = budget * step/100 / tv_cost
    digital_trp = budget * (100-step)/100 / digital_cost
    tv_reach_est = logistic_estimation(tv_trp, tv_points, tv_reach, 82)
    digital_reach_est = logistic_estimation(digital_trp, digital_points, digital_reach, 99)
    cross_reach = tv_reach_est/100 + digital_reach_est/100 - (tv_reach_est/100)*(digital_reach_est/100)
    options.append({"Option": step, "TV %": step, "Digital %": 100-step, "TV Reach": tv_reach_est,
                    "Digital Reach": digital_reach_est, "Cross Reach": cross_reach})

df = pd.DataFrame(options)

# --- Інтерактивний графік спліту ---
fig_split = px.bar(df, x="Option", y=["TV %", "Digital %"],
                   labels={"value": "Доля бюджету %", "Option": "Опції"},
                   color_discrete_map={"TV %":"black","Digital %":"red"})
st.plotly_chart(fig_split, use_container_width=True)

# --- Інтерактивні графіки естимації охоплень ---
fig_reach = px.line(df, x="Option", y=["TV Reach","Digital Reach","Cross Reach"],
                    labels={"value": "Reach %", "Option": "Опції"})
st.plotly_chart(fig_reach, use_container_width=True)

# --- Вивантаження в Excel ---
output = BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Media Split")
    writer.save()

st.download_button("⬇️ Завантажити результати в Excel", data=output.getvalue(),
                   file_name="media_split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


