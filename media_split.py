import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from scipy.interpolate import interp1d
from io import BytesIO

st.set_page_config(page_title="Media Split Optimizer", layout="wide")

st.title("Media Split Optimizer: TV + Digital")

# --------------------------
# Параметри бюджету та крок спліту
# --------------------------
st.sidebar.header("Параметри кампанії")
budget = st.sidebar.slider("Бюджет (грн)", min_value=100_000, max_value=50_000_000, value=5_000_000, step=100_000)
flight_weeks = st.sidebar.slider("Тривалість флайту (тижнів)", min_value=1, max_value=30, value=4)
split_step = st.sidebar.selectbox("Крок спліту (%)", [5,10,15,20])

# --------------------------
# Введення даних про медіа та клаттер конкурентів
# --------------------------
st.sidebar.subheader("Вхідні дані медіа")
cpm_tv = st.sidebar.number_input("Вартість ТБ (грн/ТРП)", value=500.0, min_value=1.0)
cpm_dig = st.sidebar.number_input("Вартість Digital (грн/1000 імпресій)", value=500.0, min_value=1.0)

clutter_tv = st.sidebar.number_input("Клаттер конкурентів ТБ (ТРП/тиждень)", value=150.0, min_value=1.0)
clutter_dig = st.sidebar.number_input("Клаттер конкурентів Digital (тис імпр.)", value=200.0, min_value=1.0)

# --------------------------
# Введення точок для естимації охоплення
# --------------------------
st.header("Введіть точки для естимації охоплення")

tv_points = []
dig_points = []

st.subheader("ТБ")
cols = st.columns(5)
for i, col in enumerate(cols):
    trp = col.number_input(f"ТРП точка {i+1}", min_value=1.0, max_value=10000.0, value=20*(i+1))
    reach = col.number_input(f"Reach % точка {i+1}", min_value=1.0, max_value=82.0, value=min(20*(i+1), 82))
    tv_points.append((trp, reach/100))

st.subheader("Digital")
cols = st.columns(5)
for i, col in enumerate(cols):
    imp = col.number_input(f"Імпресії точка {i+1} (тис)", min_value=1.0, max_value=10000.0, value=20*(i+1))
    reach = col.number_input(f"Reach % точка {i+1}", min_value=1.0, max_value=99.0, value=min(20*(i+1), 99))
    dig_points.append((imp, reach/100))

# --------------------------
# Вибір методу естимації
# --------------------------
st.subheader("Метод естимації охоплення")
method = st.selectbox("Виберіть метод естимації", ["Лінійна", "Сплайн", "Логістична"], index=2)
st.info("Логістична крива та сплайн зазвичай точніше для насичення аудиторії")

# --------------------------
# Функції естимації охоплення
# --------------------------
def estimate_reach(points, max_reach, method="Логістична"):
    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])
    
    x_eval = np.linspace(min(x), max(x), 100)
    
    if method=="Лінійна":
        f = interp1d(x, y, fill_value="extrapolate")
    elif method=="Сплайн":
        f = interp1d(x, y, kind='cubic', fill_value="extrapolate")
    else:  # Логістична
        from scipy.optimize import curve_fit
        def logistic(x, L, k, x0):
            return L / (1 + np.exp(-k*(x-x0)))
        p0 = [max(y),1,np.median(x)]
        try:
            popt, _ = curve_fit(logistic, x, y, p0, maxfev=10000)
        except:
            popt = [max(y),1,np.median(x)]
        f = lambda x_eval: np.minimum(logistic(x_eval,*popt), max_reach)
    return f

tv_estimator = estimate_reach(tv_points, 0.82, method)
dig_estimator = estimate_reach(dig_points, 0.99, method)

# --------------------------
# Генерація варіантів спліту
# --------------------------
splits = np.arange(0, 1+split_step/100, split_step/100)
results = []

for tv_share in splits:
    dig_share = 1-tv_share
    tv_trp = budget*tv_share / cpm_tv
    dig_imp = budget*dig_share / cpm_dig
    tv_reach = tv_estimator(tv_trp)
    dig_reach = dig_estimator(dig_imp)
    cross_reach = 1-(1-tv_reach)*(1-dig_reach)
    cpr = budget/(tv_trp+dig_imp)  # простий приклад
    eff = (tv_trp/flight_weeks >= clutter_tv) and (dig_imp/flight_weeks >= clutter_dig)
    results.append({
        "TV %": tv_share*100,
        "Digital %": dig_share*100,
        "TV TRP": tv_trp,
        "Digital Imp": dig_imp,
        "TV Reach %": tv_reach*100,
        "Digital Reach %": dig_reach*100,
        "Cross Reach %": cross_reach*100,
        "CPR": cpr,
        "Ефективний": eff
    })

df = pd.DataFrame(results)

# --------------------------
# Відображення таблиці з підсвічуванням
# --------------------------
def highlight(row):
    if row["Ефективний"]:
        return ["background-color: lightgreen"]*len(row)
    else:
        return ["background-color: lightcoral"]*len(row)

st.subheader("Результати сплітів")
st.dataframe(df.style.apply(highlight, axis=1))

# --------------------------
# Графік бюджету по медіа
# --------------------------
st.subheader("Розподіл бюджету по медіа")
fig, ax = plt.subplots(figsize=(8,4))
ax.bar("Бюджет", df["TV %"], label="ТБ", color='black', bottom=0)
ax.bar("Бюджет", df["Digital %"], label="Digital", color='red', bottom=df["TV %"])
ax.set_ylabel("Доля бюджету (%)")
ax.legend()
st.pyplot(fig)

# --------------------------
# Графік естимованих охоплень
# --------------------------
st.subheader("Естимовані охоплення медіа")
fig2, ax2 = plt.subplots(figsize=(8,4))
x_eval = np.linspace(0, max(df["TV TRP"].max(), df["Digital Imp"].max()),100)
ax2.plot(x_eval, tv_estimator(x_eval)*100, label="ТБ Reach %", color="black")
ax2.plot(x_eval, dig_estimator(x_eval)*100, label="Digital Reach %", color="red")
ax2.set_xlabel("ТРП / Digital тис імпр.")
ax2.set_ylabel("Reach %")
ax2.legend()
st.pyplot(fig2)

# --------------------------
# Експорт в Excel
# --------------------------
st.subheader("Експорт результатів")
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Results")
    workbook  = writer.book
    worksheet = writer.sheets["Results"]
    
    # Додаємо графік бюджету
    chart1 = workbook.add_chart({'type': 'column'})
    chart1.add_series({
        'name': 'ТБ',
        'categories': ['Results', 1,0, len(df),0],
        'values':     ['Results', 1,2, len(df),2],
        'fill': {'color': 'black'}
    })
    chart1.add_series({
        'name': 'Digital',
        'categories': ['Results', 1,0, len(df),0],
        'values':     ['Results', 1,3, len(df),3],
        'fill': {'color': 'red'}
    })
    worksheet.insert_chart('J2', chart1)
    
    # Додаємо графік охоплення
    chart2 = workbook.add_chart({'type': 'line'})
    chart2.add_series({
        'name': 'ТБ Reach %',
        'categories': ['Results', 1,0, len(df),0],
        'values': ['Results',1,5,len(df),5],
        'line': {'color': 'black'}
    })
    chart2.add_series({
        'name': 'Digital Reach %',
        'categories': ['Results',1,0,len(df),0],
        'values': ['Results',1,6,len(df),6],
        'line': {'color': 'red'}
    })
    worksheet.insert_chart('J20', chart2)
    
    writer.save()
    processed_data = output.getvalue()

st.download_button(
    label="⬇️ Завантажити результати в Excel",
    data=processed_data,
    file_name="media_split.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)



