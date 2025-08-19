import streamlit as st
import pandas as pd
import numpy as np
from scipy.interpolate import CubicSpline
import plotly.express as px
import io
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference

st.set_page_config(page_title="Media Split Optimizer", layout="wide")

st.title("📊 Оптимальний спліт ТБ + Digital (сучасний інтерфейс)")

# --- Введення даних ТБ ---
with st.expander("Введіть 5 точок TRP → Reach % для ТБ"):
    tv_trp_points, tv_reach_points = [], []
    for i in range(5):
        col1, col2 = st.columns(2)
        trp = col1.slider(f"TRP ТБ, точка {i+1}", 0.0, 500.0, float(i*50+50))
        reach = col2.slider(f"Reach_TV %, точка {i+1}", 0.0, 100.0, float(i*10+20))
        tv_trp_points.append(trp)
        tv_reach_points.append(reach/100)

# --- Введення даних Digital ---
with st.expander("Введіть 5 точок TRP → Reach % для Digital"):
    audience_size = st.number_input("Розмір аудиторії Digital (тис.)", min_value=1.0, value=1000.0)
    dig_trp_points, dig_reach_points = [], []
    for i in range(5):
        col1, col2 = st.columns(2)
        trp = col1.slider(f"TRP Digital, точка {i+1}", 0.0, 500.0, float(i*10+10))
        reach = col2.slider(f"Reach_Digital %, точка {i+1}", 0.0, 100.0, float(i*5+10))
        dig_trp_points.append(trp)
        dig_reach_points.append(reach/100)

# --- Інтерполяція ---
tv_spline = CubicSpline(tv_trp_points, tv_reach_points)
dig_spline = CubicSpline(dig_trp_points, dig_reach_points)

# --- Параметри бюджету ---
st.subheader("Параметри бюджету та тривалості")
budget = st.slider("Загальний бюджет", 1000, 200000, 50000, step=1000)
flight_weeks = st.slider("Тривалість флайту (тижні)", 1, 12, 4)
tv_cost_per_trp = st.number_input("Вартість 1 TRP ТБ", value=500.0)
dig_cost_per_imp = st.number_input("Вартість 1 тис. імпресій Digital", value=5.0)
tv_weekly_clutter = st.number_input("Конкурентний тиск ТБ (ТРП/тиждень)", value=150.0)
dig_weekly_clutter = st.number_input("Конкурентний тиск Digital (тис. імпресій/тиждень)", value=300.0)
n_options = st.slider("Кількість варіантів сплітів", 5, 15, 10)

# --- Генерація варіантів ---
results = []
for split in np.linspace(0.1, 0.9, n_options):
    tv_budget = budget * split
    dig_budget = budget * (1 - split)

    tv_trp = tv_budget / tv_cost_per_trp
    dig_imp = dig_budget / dig_cost_per_imp * 1000
    dig_trp = dig_imp / audience_size * 100

    tv_reach = float(np.clip(tv_spline(tv_trp), 0, 0.82))
    dig_reach = float(np.clip(dig_spline(dig_trp), 0, 0.99))
    cross_reach = tv_reach + dig_reach - tv_reach*dig_reach

    tv_weekly = tv_trp / flight_weeks
    dig_weekly = dig_trp / flight_weeks
    overall_ok = (tv_weekly >= tv_weekly_clutter) & (dig_weekly >= dig_weekly_clutter)

    cpr = (tv_budget + dig_budget) / (cross_reach*100)
    cpt_dig = dig_budget / dig_trp

    results.append({
        "Спліт ТБ": f"{split*100:.0f}%",
        "Бюджет ТБ": int(tv_budget),
        "Бюджет Digital": int(dig_budget),
        "TRP_TV": round(tv_trp,1),
        "TRP_Digital": round(dig_trp,1),
        "Imp_Digital": int(dig_imp),
        "Reach_TV %": round(tv_reach*100,1),
        "Reach_Digital %": round(dig_reach*100,1),
        "Cross_Reach %": round(cross_reach*100,1),
        "Тиск ТБ/тижд": round(tv_weekly,1),
        "Тиск Digital/тижд": round(dig_weekly,1),
        "CPR": round(cpr,2),
        "CPT_Digital": round(cpt_dig,2),
        "Ефективний": overall_ok
    })

df = pd.DataFrame(results)

# --- Найкращий варіант ---
best_idx = df[df["Ефективний"]]["CPR"].idxmin() if df[df["Ефективний"]].shape[0]>0 else df["CPR"].idxmin()
best_option = df.loc[best_idx]

# --- Вивід карток ---
st.subheader("🏆 Найкращий варіант спліту")
col1, col2, col3 = st.columns(3)
col1.metric("Найнижчий CPR", f"{best_option['CPR']:.2f}")
col2.metric("Cross Reach %", f"{best_option['Cross_Reach %']:.1f}%")
col3.metric("TRP Digital", f"{best_option['TRP_Digital']:.1f}")

# --- Таблиця ---
def highlight(row):
    if row.name == best_idx:
        return ["background-color: deepskyblue"]*len(row)
    color = "lightgreen" if row["Ефективний"] else "lightcoral"
    return [color]*len(row)
st.subheader("Результати всіх варіантів")
st.dataframe(df.style.apply(highlight, axis=1))

# --- Plotly графіки ---
st.subheader("📊 Розподіл бюджету по сплітах")
fig_budget = px.bar(df, x="Спліт ТБ", y=["Бюджет ТБ","Бюджет Digital"], 
                    title="Розподіл бюджету (stacked)", barmode="stack")
st.plotly_chart(fig_budget, use_container_width=True)

st.subheader("📈 Охоплення по всіх варіантах")
fig_reach = px.line(df, x="Спліт ТБ", y=["Reach_TV %","Reach_Digital %","Cross_Reach %"],
                    markers=True, title="Reach TV/Digital/Cross")
st.plotly_chart(fig_reach, use_container_width=True)

# --- Excel download ---
st.subheader("⬇️ Завантаження Excel з графіками")
output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Splits")
output.seek(0)
st.download_button(
    label="Скачати Excel",
    data=output,
    file_name="media_split_modern.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

