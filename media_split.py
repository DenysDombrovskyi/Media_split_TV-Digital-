import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import io

st.set_page_config(layout="wide")
st.title("Медіа-спліт ТБ + Digital")

# --- Вибір методу естимації ---
method = st.selectbox(
    "Метод естимації охоплення",
    ["Лінійна", "Сплайн", "Логістична (рекомендована)"],
    help="Логістична крива дає більш реалістичну оцінку насичення аудиторії"
)

# --- Ввід точок ТБ ---
st.subheader("Точки ТБ")
tv_points = []
tv_max_reach = 82
for i in range(5):
    trp = st.number_input(f"ТБ TRP точка {i+1}", min_value=1, max_value=10000, value=20*(i+1))
    reach = st.number_input(f"ТБ Reach % точка {i+1}", min_value=1.0, max_value=tv_max_reach, value=min(tv_max_reach, 10*(i+1)))
    tv_points.append((trp, reach))

# --- Ввід точок Digital ---
st.subheader("Точки Digital")
digital_points = []
digital_max_reach = 99
for i in range(5):
    trp = st.number_input(f"Digital TRP точка {i+1}", min_value=1, max_value=10000, value=20*(i+1))
    reach = st.number_input(f"Digital Reach % точка {i+1}", min_value=1.0, max_value=digital_max_reach, value=min(digital_max_reach, 10*(i+1)))
    digital_points.append((trp, reach))

# --- Логістична крива ---
def logistic(x, L, k, x0):
    return L / (1 + np.exp(-k*(x-x0)))

def fit_logistic(trp, reach, max_reach):
    p0 = [max_reach, 0.001, np.median(trp)]
    params, _ = curve_fit(logistic, trp, reach, p0=p0, maxfev=10000)
    return params

tv_trp = np.array([p[0] for p in tv_points])
tv_reach = np.array([p[1] for p in tv_points])
digital_trp = np.array([p[0] for p in digital_points])
digital_reach = np.array([p[1] for p in digital_points])

tv_params = fit_logistic(tv_trp, tv_reach, tv_max_reach)
digital_params = fit_logistic(digital_trp, digital_reach, digital_max_reach)

# --- Опції для симуляції ---
options = 10
tv_trp_options = np.linspace(min(tv_trp), max(tv_trp), options)
digital_trp_options = np.linspace(min(digital_trp), max(digital_trp), options)

results = []
for i in range(options):
    tv_t = tv_trp_options[i]
    dig_t = digital_trp_options[i]
    tv_r = logistic(tv_t, *tv_params)
    dig_r = logistic(dig_t, *digital_params)
    cross_r = 1 - (1 - tv_r/100)*(1 - dig_r/100)
    results.append([tv_t, tv_r, dig_t, dig_r, cross_r*100])

df = pd.DataFrame(results, columns=["TV TRP","TV Reach %","Digital TRP","Digital Reach %","CrossMedia Reach %"])

# --- Відображення таблиці ---
st.subheader("Результати сплітів")
st.dataframe(df.style.format("{:.2f}"))

# --- Графік охоплень ---
st.subheader("Графік охоплень")
fig, ax = plt.subplots(figsize=(10,5))
ax.plot(tv_trp_options, [r[1] for r in results], 'k-o', label="TV Reach")
ax.plot(digital_trp_options, [r[3] for r in results], 'r-o', label="Digital Reach")
ax.plot(tv_trp_options, [r[4] for r in results], 'g--', label="CrossMedia Reach")
ax.set_xlabel("TRP / Impressions")
ax.set_ylabel("Reach %")
ax.legend()
st.pyplot(fig)

# --- Графік спліту по бюджету ---
st.subheader("Спліт бюджету (умовно 50% на ТБ і Digital)")
fig2, ax2 = plt.subplots(figsize=(10,4))
tv_share = [50]*options
dig_share = [50]*options
ax2.bar(range(1, options+1), tv_share, color='black', label='TV')
ax2.bar(range(1, options+1), dig_share, bottom=tv_share, color='red', label='Digital')
ax2.set_xlabel("Варіанти спліту")
ax2.set_ylabel("Доля бюджету %")
ax2.set_xticks(range(1, options+1))
ax2.legend()
st.pyplot(fig2)

# --- Експорт в Excel з графіками ---
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Results")
    workbook  = writer.book
    worksheet = writer.sheets["Results"]
    
    # Графік охоплень
    chart = workbook.add_chart({'type': 'line'})
    chart.add_series({'name': 'TV Reach', 'categories': [0,1,options,1], 'values': [0,1,options,1]})
    # (спрощено, можна додати серії для Digital і CrossMedia)
    
    writer.save()

st.download_button(
    "Завантажити результати в Excel",
    data=output,
    file_name="media_split.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)




