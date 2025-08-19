import streamlit as st
import pandas as pd
import numpy as np
from scipy.interpolate import PchipInterpolator
from io import BytesIO
import matplotlib.pyplot as plt

st.title("Media Split Calculator")

# --- Функція введення точок ---
def input_points(media_name, max_reach=100.0, n_points=5):
    st.write(f"### Введіть {n_points} точок для {media_name}")
    cols = st.columns(n_points)
    trp_points = []
    reach_points = []
    
    for i in range(n_points):
        reach = cols[i].number_input(
            f"{media_name} Reach % точка {i+1}",
            min_value=0.0,
            max_value=float(max_reach),
            value=float(min(float(max_reach), 20.0*(i+1))),
            step=1.0,
            key=f"{media_name}_reach_{i}"
        )
        trp = cols[i].number_input(
            f"{media_name} TRP точка {i+1}",
            min_value=1.0,
            max_value=10000.0,
            value=float(20*(i+1)),
            step=1.0,
            key=f"{media_name}_trp_{i}"
        )
        reach_points.append(reach)
        trp_points.append(trp)
    
    return trp_points, reach_points

# --- Введення точок ---
tv_trp_pts, tv_reach_pts = input_points("ТБ", max_reach=82)
digital_trp_pts, digital_reach_pts = input_points("Digital", max_reach=99)

# --- Естимація охоплення через PCHIP (монотонна апроксимація) ---
tv_spline = PchipInterpolator(tv_trp_pts, tv_reach_pts)
digital_spline = PchipInterpolator(digital_trp_pts, digital_reach_pts)

# --- Введення бюджету та тривалості ---
budget = st.slider("Бюджет, грн", min_value=100_000, max_value=50_000_000, step=100_000, value=5_000_000)
flight_weeks = st.slider("Тривалість флайту, тижні", min_value=1, max_value=30, value=4)
step_percent = st.selectbox("Крок спліту бюджету, %", options=[5,10,15,20], index=1)

# --- Приклади опцій спліту ---
splits = []
for p in range(0, 101, step_percent):
    splits.append({"ТБ %": p, "Digital %": 100-p})

df = pd.DataFrame(splits)

# --- Розрахунок TRP і Reach ---
tv_max_trp = 10000
digital_max_trp = 10000

tv_reach_est = [min(82, tv_spline(tv_max_trp * row["ТБ %"]/100)) for _, row in df.iterrows()]
digital_reach_est = [min(99, digital_spline(digital_max_trp * row["Digital %"]/100)) for _, row in df.iterrows()]
cross_reach = [tv + dig - tv*dig/100 for tv,dig in zip(tv_reach_est, digital_reach_est)]

df["TV Reach %"] = tv_reach_est
df["Digital Reach %"] = digital_reach_est
df["Cross Media Reach %"] = cross_reach
df["Effective"] = df["Cross Media Reach %"]>0

# --- Вивід таблиці ---
st.subheader("Опції спліту")
st.dataframe(df)

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

# --- Експорт в Excel з графіками ---
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name='Media Split')
    
    workbook = writer.book
    ws = writer.sheets['Media Split']
    
    # Додаємо графік спліту
    chart1 = workbook.add_chart({'type':'column'})
    chart1.add_series({
        'name': 'ТБ',
        'categories': ['Media Split', 1, 0, len(df), 0],
        'values':     ['Media Split', 1, 1, len(df), 1],
        'fill': {'color': 'black'}
    })
    chart1.add_series({
        'name': 'Digital',
        'categories': ['Media Split', 1, 0, len(df), 0],
        'values':     ['Media Split', 1, 2, len(df), 2],
        'fill': {'color': 'red'}
    })
    chart1.set_title({'name':'Розподіл бюджету по медіа'})
    ws.insert_chart('G2', chart1, {'x_scale': 1.5, 'y_scale': 1.5})
    
    # Додаємо графік охоплення
    chart2 = workbook.add_chart({'type':'line'})
    chart2.add_series({
        'name': 'ТБ',
        'categories': ['Media Split', 1, 0, len(df), 0],
        'values':     ['Media Split', 1, 3, len(df), 3],
        'line': {'color': 'black'}
    })
    chart2.add_series({
        'name': 'Digital',
        'categories': ['Media Split', 1, 0, len(df), 0],
        'values':     ['Media Split', 1, 4, len(df), 4],
        'line': {'color': 'red'}
    })
    chart2.add_series({
        'name': 'Cross Media',
        'categories': ['Media Split', 1, 0, len(df), 0],
        'values':     ['Media Split', 1, 5, len(df), 5],
        'line': {'color': 'green'}
    })
    chart2.set_title({'name':'Естимоване охоплення'})
    ws.insert_chart('G20', chart2, {'x_scale': 1.5, 'y_scale': 1.5})
    
    writer.save()

st.download_button("⬇️ Завантажити результати в Excel", data=output.getvalue(),
                   file_name="media_split.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


