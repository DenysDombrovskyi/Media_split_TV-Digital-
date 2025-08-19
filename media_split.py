import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from scipy.interpolate import CubicSpline
from openpyxl import load_workbook
from openpyxl.chart import BarChart, LineChart, Reference

st.title("📊 Оптимальний спліт ТБ + Digital з CPR і графіками Excel")

# --- Введення точок охоплення ---
st.subheader("Введіть 5 точок TRP → Reach % для ТБ")
tv_trp_points, tv_reach_points = [], []
for i in range(5):
    col1, col2 = st.columns(2)
    trp = col1.number_input(f"TRP ТБ, точка {i+1}", min_value=0.0, value=float(i*50+50))
    reach = col2.number_input(f"Reach_TV %, точка {i+1}", min_value=0.0, max_value=100.0, value=float(i*10+20))
    tv_trp_points.append(trp)
    tv_reach_points.append(reach/100)

st.subheader("Введіть 5 точок Impressions → Reach % для Digital")
dig_imp_points, dig_reach_points = [], []
for i in range(5):
    col1, col2 = st.columns(2)
    imp = col1.number_input(f"Impressions Digital (тис.), точка {i+1}", min_value=0.0, value=float(i*100+100))
    reach = col2.number_input(f"Reach_Digital %, точка {i+1}", min_value=0.0, max_value=100.0, value=float(i*5+10))
    dig_imp_points.append(imp)
    dig_reach_points.append(reach/100)

# --- Інтерполяція ---
tv_spline = CubicSpline(tv_trp_points, tv_reach_points)
dig_spline = CubicSpline(dig_imp_points, dig_reach_points)

# --- Параметри бюджету та тривалості ---
st.subheader("Параметри бюджету та тривалості")
budget = st.number_input("Загальний бюджет", min_value=1000, step=1000, value=50000)
flight_weeks = st.number_input("Тривалість флайту (тижні)", min_value=1, value=4)
tv_cost_per_trp = st.number_input("Вартість 1 TRP в ТБ", value=500.0)
dig_cost_per_imp = st.number_input("Вартість 1 тис. імпресій в Digital", value=5.0)
tv_weekly_clutter = st.number_input("Конкурентний тиск ТБ (ТРП/тиждень)", value=150.0)
dig_weekly_clutter = st.number_input("Конкурентний тиск Digital (тис. імпресій/тиждень)", value=300.0)
n_options = st.slider("Кількість варіантів сплітів", 5, 15, 10)

# --- Мінімальний бюджет ---
min_budget_tv = tv_weekly_clutter * flight_weeks * tv_cost_per_trp
min_budget_dig = dig_weekly_clutter * flight_weeks * dig_cost_per_imp / 1000
min_total_budget = min_budget_tv + min_budget_dig
if budget < min_total_budget:
    st.warning(f"❌ Поточний бюджет ({int(budget)}) замалий. Рекомендований мінімальний бюджет: {int(min_total_budget)}")

# --- Генерація варіантів ---
results = []
for split in np.linspace(0.1, 0.9, n_options):
    tv_budget = budget * split
    dig_budget = budget * (1 - split)

    tv_trp = tv_budget / tv_cost_per_trp
    dig_imp = dig_budget / dig_cost_per_imp * 1000

    # --- Обмеження Reach ТБ до 82%
    tv_reach = float(np.clip(tv_spline(tv_trp), 0, 0.82))
    dig_reach = float(np.clip(dig_spline(dig_imp), 0, 1))
    cross_reach = tv_reach + dig_reach - tv_reach * dig_reach

    tv_weekly = tv_trp / flight_weeks
    dig_weekly = dig_imp / flight_weeks / 1000

    tv_ok = tv_weekly >= tv_weekly_clutter
    dig_ok = dig_weekly >= dig_weekly_clutter
    overall_ok = tv_ok and dig_ok

    results.append({
        "Спліт ТБ": f"{split*100:.0f}%",
        "Бюджет ТБ": int(tv_budget),
        "Бюджет Digital": int(dig_budget),
        "TRP_TV": round(tv_trp,1),
        "Imp_Digital": int(dig_imp),
        "Reach_TV %": round(tv_reach*100,1),
        "Reach_Digital %": round(dig_reach*100,1),
        "Cross_Reach %": round(cross_reach*100,1),
        "Тиск ТБ/тижд": round(tv_weekly,1),
        "Тиск Digital/тижд": round(dig_weekly,1),
        "Ефективний": overall_ok
    })

df = pd.DataFrame(results)

# --- Додавання CPR ---
df["CPR"] = (df["Бюджет ТБ"] + df["Бюджет Digital"]) / df["Cross_Reach %"]
df["Тиск_ок"] = (df["Тиск ТБ/тижд"] >= tv_weekly_clutter) & (df["Тиск Digital/тижд"] >= dig_weekly_clutter)

if df[df["Тиск_ок"]].shape[0] > 0:
    min_cpr_idx = df[df["Тиск_ок"]]["CPR"].idxmin()
else:
    min_cpr_idx = None

# --- Підсвітка таблиці ---
def highlight(row):
    if row.name == min_cpr_idx:
        return ["background-color: deepskyblue"]*len(row)
    color = "background-color: lightgreen" if row["Ефективний"] else "background-color: lightcoral"
    return [color]*len(row)

st.subheader("Результати сплітів")
st.dataframe(df.style.apply(highlight, axis=1))

# --- Stacked графік бюджету ---
st.subheader("📊 Розподіл бюджету по варіантах спліту (stacked)")
fig, ax = plt.subplots(figsize=(10,5))
x = np.arange(len(df))
ax.bar(x, df["Бюджет ТБ"], label="ТБ")
ax.bar(x, df["Бюджет Digital"], bottom=df["Бюджет ТБ"], label="Digital")
ax.set_xticks(x)
ax.set_xticklabels(df["Спліт ТБ"])
ax.set_ylabel("Бюджет")
ax.set_title("Розподіл бюджету по сплітах (stacked)")
ax.legend()
plt.xticks(rotation=45)
st.pyplot(fig)

# --- Лінійний графік охоплення (кросмедійне + медіа) ---
st.subheader("📈 Охоплення по всіх варіантах спліту")
fig2, ax2 = plt.subplots(figsize=(10,5))
ax2.plot(df["Спліт ТБ"], df["Reach_TV %"], marker='o', label="Reach_TV %")
ax2.plot(df["Спліт ТБ"], df["Reach_Digital %"], marker='o', label="Reach_Digital %")
ax2.plot(df["Спліт ТБ"], df["Cross_Reach %"], marker='o', label="Cross_Reach %")
ax2.set_ylabel("Охоплення %")
ax2.set_title("Кросмедійне та медіа охоплення")
ax2.legend()
plt.xticks(rotation=45)
st.pyplot(fig2)

# --- Експорт Excel з графіками ---
st.subheader("⬇️ Завантаження Excel з графіками")
output = io.BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Splits")

output.seek(0)
wb = load_workbook(output)
ws = wb["Splits"]

# --- Stacked bar chart бюджету ---
budget_chart = BarChart()
budget_chart.type = "col"
budget_chart.title = "Розподіл бюджету ТБ/Digital"
budget_chart.y_axis.title = "Бюджет"
budget_chart.x_axis.title = "Спліт ТБ"
budget_chart.overlap = 100
budget_chart.grouping = "stacked"

data = Reference(ws, min_col=2, max_col=3, min_row=1, max_row=ws.max_row)
cats = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
budget_chart.add_data(data, titles_from_data=True)
budget_chart.set_categories(cats)
ws.add_chart(budget_chart, "L2")

# --- Лінійний графік охоплення (Reach_TV %, Reach_Digital %, Cross_Reach %) ---
reach_chart = LineChart()
reach_chart.title = "Охоплення по сплітах"
reach_chart.y_axis.title = "Reach %"
reach_chart.x_axis.title = "Спліт ТБ"

data = Reference(ws, min_col=7, max_col=9, min_row=1, max_row=ws.max_row)  # тільки охоплення
cats = Reference(ws, min_col=1, min_row=2, max_row=ws.max_row)
reach_chart.add_data(data, titles_from_data=True)
reach_chart.set_categories(cats)
ws.add_chart(reach_chart, "L20")

output_chart = io.BytesIO()
wb.save(output_chart)
output_chart.seek(0)

st.download_button(
    label="Скачати Excel з графіками",
    data=output_chart,
    file_name="media_split_chart.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

