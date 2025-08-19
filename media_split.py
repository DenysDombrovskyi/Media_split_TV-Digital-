import streamlit as st
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator
from io import BytesIO
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.styles import PatternFill

st.title("Media Split Calculator")

# --- Введення точок ---
def input_points(media_name, max_reach=100.0, n_points=5):
    st.write(f"### Введіть {n_points} точок для {media_name}")
    cols = st.columns(n_points)
    trp_points, reach_points = [], []
    for i in range(n_points):
        reach = cols[i].number_input(
            f"{media_name} Reach % точка {i+1}",
            min_value=0.0, max_value=float(max_reach), value=float(min(float(max_reach), 20*(i+1))), step=1.0,
            key=f"{media_name}_reach_{i}"
        )
        trp = cols[i].number_input(
            f"{media_name} TRP точка {i+1}",
            min_value=1.0, max_value=10000.0, value=float(20*(i+1)), step=1.0,
            key=f"{media_name}_trp_{i}"
        )
        reach_points.append(reach)
        trp_points.append(trp)
    return trp_points, reach_points

tv_trp_pts, tv_reach_pts = input_points("ТБ", 82)
digital_trp_pts, digital_reach_pts = input_points("Digital", 99)

# --- Естимація охоплення через PCHIP ---
tv_spline = PchipInterpolator(tv_trp_pts, tv_reach_pts)
digital_spline = PchipInterpolator(digital_trp_pts, digital_reach_pts)

# --- Бюджет та тривалість ---
budget = st.slider("Бюджет, грн", 100_000, 50_000_000, 5_000_000, step=100_000)
flight_weeks = st.slider("Тривалість флайту, тижні", 1, 30, 4)
step_percent = st.selectbox("Крок спліту бюджету, %", [5,10,15,20], index=1)

# --- Генерація варіантів спліту ---
splits = [{"ТБ %": p, "Digital %": 100-p} for p in range(0, 101, step_percent)]
df = pd.DataFrame(splits)

# --- Розрахунок Reach ---
tv_max_trp = 10000
digital_max_trp = 10000
df["TV Reach %"] = [min(82, tv_spline(tv_max_trp*row["ТБ %"]/100)) for _, row in df.iterrows()]
df["Digital Reach %"] = [min(99, digital_spline(digital_max_trp*row["Digital %"]/100)) for _, row in df.iterrows()]
df["Cross Media Reach %"] = df["TV Reach %"] + df["Digital Reach %"] - df["TV Reach %"]*df["Digital Reach %"]/100
best_idx = df["Cross Media Reach %"].idxmax()
df["Effective"] = False
df.loc[best_idx, "Effective"] = True

# --- Вивід таблиці ---
def highlight_best(row):
    return ['background-color: lightgreen' if row["Effective"] else '' for _ in row]

st.subheader("Опції спліту")
st.dataframe(df.style.apply(highlight_best, axis=1))

# --- Графік спліту ---
fig, ax = plt.subplots()
ax.bar([str(i+1) for i in range(len(df))], df["ТБ %"], label="ТБ", color="black")
ax.bar([str(i+1) for i in range(len(df))], df["Digital %"], bottom=df["ТБ %"], label="Digital", color="red")
ax.set_ylabel("Доля бюджету %")
ax.set_xlabel("Опція")
ax.set_title("Розподіл бюджету по медіа")
ax.legend()
st.pyplot(fig)

# --- Графік охоплення ---
fig2, ax2 = plt.subplots()
ax2.plot(range(1,len(df)+1), df["TV Reach %"], marker="o", color="black", label="ТБ")
ax2.plot(range(1,len(df)+1), df["Digital Reach %"], marker="o", color="red", label="Digital")
ax2.plot(range(1,len(df)+1), df["Cross Media Reach %"], marker="o", color="green", label="Cross Media")
ax2.set_ylabel("Охоплення %")
ax2.set_xlabel("Опція")
ax2.set_title("Естимоване охоплення")
ax2.legend()
st.pyplot(fig2)

# --- Експорт в Excel ---
output = BytesIO()
wb = Workbook()
ws = wb.active
ws.title = "Media Split"

# Запис таблиці
for r_idx, row in enumerate(df.itertuples(), 1):
    ws.cell(row=r_idx+1, column=1, value=r_idx)  # опція
    ws.cell(row=r_idx+1, column=2, value=row._1) # ТБ %
    ws.cell(row=r_idx+1, column=3, value=row._2) # Digital %
    ws.cell(row=r_idx+1, column=4, value=row._3) # TV Reach %
    ws.cell(row=r_idx+1, column=5, value=row._4) # Digital Reach %
    ws.cell(row=r_idx+1, column=6, value=row._5) # Cross Media Reach %
    if row.Effective:
        for c in range(1,7):
            ws.cell(row=r_idx+1, column=c).fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")

# Заголовки
headers = ["Option","ТБ %","Digital %","TV Reach %","Digital Reach %","Cross Media Reach %"]
for c_idx, val in enumerate(headers,1):
    ws.cell(row=1, column=c_idx, value=val)

wb.save(output)
st.download_button("⬇️ Завантажити Excel з графіками та таблицею", data=output.getvalue(),
                   file_name="media_split.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



