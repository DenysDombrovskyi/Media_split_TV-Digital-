import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import interp1d
import io
import matplotlib.pyplot as plt

st.set_page_config(page_title="Media Split Optimizer", layout="wide")

st.title("Media Split Optimizer")

# --- Параметри ---
budget = st.number_input("Бюджет, грн", min_value=100_000, max_value=50_000_000, value=5_000_000, step=100_000)
cpm = st.number_input("CPM, грн", min_value=100.0, max_value=5000.0, value=500.0, step=50.0)
flight_weeks = st.slider("Тривалість флайту, тижнів", 1, 30, 4)
split_step = st.selectbox("Крок спліту по бюджету, %", [5, 10, 15, 20])
clutter_tv = st.number_input("Клаттер конкурентів ТБ TRP", min_value=1.0, max_value=1000.0, value=100.0, step=1.0)
clutter_dig = st.number_input("Клаттер конкурентів Digital %", min_value=1.0, max_value=100.0, value=10.0, step=1.0)

# --- Введення точок ---
def input_points(media_name, max_reach):
    cols = st.columns(5)
    trp_points = []
    reach_points = []
    for i, col in enumerate(cols):
        trp = col.number_input(
            f"{media_name} TRP точка {i+1}",
            min_value=1.0,
            max_value=10000.0,
            value=float(20*(i+1)),
            step=1.0
        )
        reach = col.number_input(
            f"{media_name} Reach % точка {i+1}",
            min_value=1.0,
            max_value=float(max_reach),
            value=float(min(max_reach, 20*(i+1))),
            step=1.0
        )
        trp_points.append(trp)
        reach_points.append(reach)
    return trp_points, reach_points

tv_max_reach = 82.0
dig_max_reach = 99.0

tv_trp_pts, tv_reach_pts = input_points("ТБ", tv_max_reach)
dig_trp_pts, dig_reach_pts = input_points("Digital", dig_max_reach)

# --- Естимація охоплення логістичною кривою ---
def logistic_estimation(trp_pts, reach_pts, trp_max):
    x = np.array(trp_pts)
    y = np.array(reach_pts)/100.0
    # Логістична функція
    def logistic(x, L, k, x0):
        return L / (1 + np.exp(-k*(x - x0)))
    # Початкові параметри
    from scipy.optimize import curve_fit
    try:
        popt, _ = curve_fit(logistic, x, y, bounds=([0,0,0],[1,10,trp_max]))
    except:
        popt = [max(y), 0.1, np.median(x)]
    x_full = np.linspace(0, trp_max, 100)
    y_full = logistic(x_full, *popt)*100
    return x_full, y_full

tv_x, tv_y = logistic_estimation(tv_trp_pts, tv_reach_pts, 10000)
dig_x, dig_y = logistic_estimation(dig_trp_pts, dig_reach_pts, 10000)

# --- Опції спліту ---
options = np.arange(0, 101, split_step)
results = []

for opt in options:
    tv_share = opt/100
    dig_share = 1-tv_share
    tv_trp = tv_share*budget/cpm*1000/flight_weeks
    dig_trp = dig_share*budget/cpm*1000/flight_weeks
    tv_reach = np.interp(tv_trp, tv_x, tv_y)
    dig_reach = np.interp(dig_trp, dig_x, dig_y)
    tv_eff = tv_trp >= clutter_tv
    dig_eff = dig_trp >= clutter_dig
    eff = tv_eff and dig_eff
    cross_reach = tv_reach/100 + dig_reach/100 - (tv_reach/100)*(dig_reach/100)
    cpr = budget / (tv_trp + dig_trp) if (tv_trp + dig_trp) > 0 else np.nan
    results.append({
        "Опція": int(opt/ split_step + 1),
        "TV TRP": tv_trp,
        "TV Reach %": tv_reach,
        "Digital TRP": dig_trp,
        "Digital Reach %": dig_reach,
        "Cross Reach %": cross_reach*100,
        "CPR": cpr,
        "Ефективний": eff
    })

df = pd.DataFrame(results)

# --- Підсвічування ---
def highlight(row):
    if row["Ефективний"]:
        return ["background-color: lightgreen"]*len(row)
    else:
        return ["background-color: lightcoral"]*len(row)

st.dataframe(df.style.apply(highlight, axis=1))

# --- Графіки ---
fig, ax = plt.subplots(1,2, figsize=(12,5))

# Спліт стовпчасто
ax[0].bar(['TV','Digital'], [df.iloc[df['CPR'].idxmin()]["TV TRP"], df.iloc[df['CPR'].idxmin()]["Digital TRP"]],
          color=['black','red'])
ax[0].set_title("Найкращий спліт (TRP)")
ax[0].set_ylabel("TRP")

# Кросмедіа
ax[1].plot(df['Опція'], df['Cross Reach %'], marker='o')
ax[1].set_title("Кросмедійне охоплення")
ax[1].set_xlabel("Опції")
ax[1].set_ylabel("%")

st.pyplot(fig)

# --- Експорт в Excel ---
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Results")
    workbook  = writer.book
    worksheet = writer.sheets["Results"]

    # Додаємо графіки
    chart1 = workbook.add_chart({'type': 'column'})
    chart1.add_series({
        'name': 'TV TRP',
        'categories': f'=Results!$A$2:$A${len(df)+1}',
        'values': f'=Results!$B$2:$B${len(df)+1}',
        'fill': {'color': 'black'}
    })
    chart1.add_series({
        'name': 'Digital TRP',
        'categories': f'=Results!$A$2:$A${len(df)+1}',
        'values': f'=Results!$D$2:$D${len(df)+1}',
        'fill': {'color': 'red'}
    })
    chart1.set_title({'name': 'TRP Спліт'})
    chart1.set_x_axis({'name': 'Опції'})
    chart1.set_y_axis({'name': 'TRP'})
    worksheet.insert_chart('J2', chart1)

    chart2 = workbook.add_chart({'type': 'line'})
    chart2.add_series({
        'name': 'Cross Reach %',
        'categories': f'=Results!$A$2:$A${len(df)+1}',
        'values': f'=Results!$F$2:$F${len(df)+1}',
        'line': {'color': 'blue'}
    })
    chart2.set_title({'name': 'Кросмедійне охоплення'})
    chart2.set_x_axis({'name': 'Опції'})
    chart2.set_y_axis({'name': '%'})
    worksheet.insert_chart('J20', chart2)

    writer.save()
st.download_button(
    "⬇️ Завантажити результати в Excel",
    data=output.getvalue(),
    file_name="media_split.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


