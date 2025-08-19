import streamlit as st
import pandas as pd
import numpy as np
from scipy.interpolate import CubicSpline
import plotly.express as px
import io
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

st.set_page_config(page_title="Media Split Dashboard", layout="wide")
st.title("🎯 Media Split Dashboard — ТБ + Digital")

# --- Sidebar ---
with st.sidebar:
    st.header("Параметри кампанії")
    budget = st.slider("Бюджет (₴)", 100_000, 50_000_000, 5_000_000, step=100_000)
    flight_weeks = st.slider("Тривалість флайту (тижні)", 1, 30, 4)
    audience_size = st.number_input("Аудиторія Digital (тис.)", 1000.0)
    tv_cost_per_trp = st.number_input("Вартість 1 TRP ТБ (₴)", 500.0)
    dig_cost_per_imp = st.number_input("Вартість 1 тис. імпр. Digital (₴)", 5.0)
    tv_weekly_clutter = st.number_input("Тиск конкурентів ТБ (ТРП/тижд.)", 150.0)
    dig_weekly_clutter = st.number_input("Тиск конкурентів Digital (TRP/тижд.)", 300.0)
    split_step_percent = st.selectbox("Крок спліту (%)", [5, 10, 15, 20])
    n_options = st.slider("Кількість варіантів сплітів", 5, 15, 10)

# --- Введення 5 точок TRP→Reach для ТБ і Digital ---
def input_points(media_name):
    st.subheader(f"{media_name} — Введіть 5 точок TRP → Reach (%)")
    trp_points = []
    reach_points = []
    for i in range(5):
        cols = st.columns(2)
        trp = cols[0].number_input(f"{media_name} TRP точка {i+1}", min_value=0.0, max_value=1000.0, value=50.0*(i+1))
        reach = cols[1].number_input(f"{media_name} Reach % точка {i+1}", min_value=0.0, max_value=100.0, value=20.0*(i+1))
        trp_points.append(trp)
        reach_points.append(reach/100)
    return CubicSpline(trp_points, reach_points)

tv_spline = input_points("ТБ")
dig_spline = input_points("Digital")

# --- Генерація сплітів ---
split_step = split_step_percent / 100.0
split_values = np.arange(split_step, 1.0, split_step)[:n_options]
results = []
budget_warning = False
min_needed_budget = 0

for i, split in enumerate(split_values, start=1):
    tv_budget = budget * split
    dig_budget = budget * (1 - split)
    tv_trp = tv_budget / tv_cost_per_trp
    dig_imp = dig_budget / dig_cost_per_imp
    dig_trp = dig_imp / audience_size * 100

    tv_reach = float(np.clip(tv_spline(tv_trp), 0, 0.82))
    dig_reach = float(np.clip(dig_spline(dig_trp), 0, 0.99))
    cross_reach = tv_reach + dig_reach - tv_reach*dig_reach

    tv_weekly = tv_trp / flight_weeks
    dig_weekly = dig_trp / flight_weeks

    overall_ok = (tv_weekly >= tv_weekly_clutter) & (dig_weekly >= dig_weekly_clutter)
    if not overall_ok:
        budget_warning = True
        min_tv_budget = tv_weekly_clutter * flight_weeks * tv_cost_per_trp
        min_dig_budget = dig_weekly_clutter * flight_weeks * dig_cost_per_imp * audience_size / 100
        min_needed_budget = max(min_needed_budget, min_tv_budget + min_dig_budget)

    cpr = (tv_budget + dig_budget) / (cross_reach*100)
    cpt_dig = dig_budget / dig_trp

    results.append({
        "Опція": f"Опція {i}",
        "Спліт ТБ %": round(split*100,0),
        "Бюджет ТБ": int(tv_budget),
        "Бюджет Digital": int(dig_budget),
        "TRP_TV": round(tv_trp,1),
        "TRP_Digital": round(dig_trp,1),
        "Imp_Digital": round(dig_imp,1),
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
df['Доля ТБ %'] = df['Бюджет ТБ'] / (df['Бюджет ТБ'] + df['Бюджет Digital']) * 100
df['Доля Digital %'] = df['Бюджет Digital'] / (df['Бюджет ТБ'] + df['Бюджет Digital']) * 100

if budget_warning:
    st.warning(f"⚠️ Мінімальний бюджет для досягнення конкурентного тиску: {int(min_needed_budget):,} ₴")

# --- Визначення найкращої опції ---
if df["Ефективний"].any():
    best_idx = df[df["Ефективний"]]["CPR"].idxmin()
else:
    best_idx = df["CPR"].idxmin()
best_option = df.loc[best_idx]

# --- KPI ---
st.subheader("🏆 KPI")
col1, col2, col3 = st.columns(3)
col1.metric("Найнижчий CPR", f"{best_option['CPR']:.2f}")
col2.metric("Cross Reach %", f"{best_option['Cross_Reach %']:.1f}%")
col3.metric("TRP Digital", f"{best_option['TRP_Digital']:.1f}")

# --- Чекбокси для точок ---
show_tv_points = st.checkbox("Показувати точки ТБ", value=True)
show_dig_points = st.checkbox("Показувати точки Digital", value=True)

# --- Графік долей бюджету ---
st.subheader("📊 Долі бюджету")
df_budget_plot = df.melt(id_vars=["Опція"], value_vars=["Доля ТБ %", "Доля Digital %"],
                         var_name="Медіа", value_name="Доля %")
df_budget_plot["Медіа"] = df_budget_plot["Медіа"].replace({"Доля ТБ %": "ТБ", "Доля Digital %": "Digital"})
color_map = {"ТБ": "black", "Digital": "red"}
fig_budget = px.bar(df_budget_plot, x="Опція", y="Доля %", color="Медіа", text="Доля %",
                    title="Долі бюджету по медіа (stacked)", color_discrete_map=color_map)
fig_budget.update_yaxes(title_text="Доля бюджету (%)")
fig_budget.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
st.plotly_chart(fig_budget, use_container_width=True)

# --- Графік охоплення ---
st.subheader("📈 Охоплення")
fig_reach = px.line(df, x="Опція", y=["Reach_TV %","Reach_Digital %","Cross_Reach %"],
                    markers=True, title="Reach TV / Digital / Cross")

if show_tv_points:
    tv_reach_pts = [tv_spline.y[i]*100 for i in range(5)]
    fig_reach.add_scatter(
        x=[f"Опція {i+1}" for i in range(5)],
        y=tv_reach_pts,
        mode="markers+text",
        name="ТБ точки",
        marker=dict(symbol="circle", color="black", size=10),
        text=[f"{r:.1f}%" for r in tv_reach_pts],
        textposition="top center"
    )

if show_dig_points:
    dig_reach_pts = [dig_spline.y[i]*100 for i in range(5)]
    fig_reach.add_scatter(
        x=[f"Опція {i+1}" for i in range(5)],
        y=dig_reach_pts,
        mode="markers+text",
        name="Digital точки",
        marker=dict(symbol="x", color="red", size=10),
        text=[f"{r:.1f}%" for r in dig_reach_pts],
        textposition="bottom center"
    )

st.plotly_chart(fig_reach, use_container_width=True)

# --- Таблиця ---
st.subheader("📋 Варіанти сплітів")
def highlight_rows(row):
    if row['Опція'] == best_option['Опція']:
        return ['background-color: lightblue']*len(row)
    elif row['Ефективний']:
        return ['background-color: lightgreen']*len(row)
    else:
        return ['background-color: salmon']*len(row)
st.dataframe(df.style.apply(highlight_rows, axis=1))

# --- Excel Export ---
def to_excel(df):
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    for r in dataframe_to_rows(df, index=False, header=True):
        ws.append(r)
    wb.save(output)
    return output

st.download_button(
    label="⬇️ Завантажити результати в Excel",
    data=to_excel(df),
    file_name="media_split_results.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

