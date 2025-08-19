import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from io import BytesIO

st.set_page_config(page_title="Media Split", layout="wide")

st.title("Оптимізація спліту ТБ + Діджитал")

# --- Параметри флайту ---
flight_weeks = st.sidebar.slider("Тривалість флайту (тижні)", 1, 30, 4)
total_budget = st.sidebar.slider("Бюджет (грн)", 100_000, 50_000_000, 5_000_000, step=100_000)
split_step = st.sidebar.selectbox("Крок спліту (%)", [5, 10, 15, 20])

# --- Вартість медіа ---
st.sidebar.header("Вартість медіа")
tv_price = st.sidebar.number_input("Вартість 1 TRP ТБ (грн)", 1_000, 1_000_000, 500_000, step=1000)
dig_cpm = st.sidebar.number_input("CPM Діджитал (грн за 1000 імпр.)", 10, 100_000, 500, step=10)
audience_dig = st.sidebar.number_input("Розмір аудиторії Digital (тис.)", 1, 10_000, 1000)

# --- Введення точок ТБ ---
st.subheader("Точки ТБ")
tv_points = []
for i in range(5):
    trp = st.number_input(f"ТБ TRP точка {i+1}", 1, 10_000, 20*(i+1))
    reach = st.number_input(f"ТБ Reach % точка {i+1}", 1, 82, min(20*(i+1), 82))
    tv_points.append((trp, reach))

# --- Введення точок Діджитал ---
st.subheader("Точки Діджитал")
dig_points = []
for i in range(5):
    trp = st.number_input(f"Digital TRP точка {i+1}", 1, 10_000, 20*(i+1))
    reach = st.number_input(f"Digital Reach % точка {i+1}", 1, 99, min(20*(i+1), 99))
    dig_points.append((trp, reach))

# --- Естимація охоплення (апроксимація) ---
def estimate_reach(points, max_reach):
    # Логістична крива
    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])
    # Форма логістики: y = max_reach / (1 + exp(-k*(x-x0)))
    from scipy.optimize import curve_fit
    def logistic(x, k, x0):
        return max_reach / (1 + np.exp(-k*(x-x0)))
    popt, _ = curve_fit(logistic, x, y, p0=[0.001, np.mean(x)])
    return lambda trp: logistic(trp, *popt)

tv_estimator = estimate_reach(tv_points, 82)
dig_estimator = estimate_reach(dig_points, 99)

# --- Генерація варіантів спліту ---
options = []
for tv_share in range(0, 101, split_step):
    dig_share = 100 - tv_share
    tv_reach = tv_estimator(10_000)
    dig_reach = dig_estimator(10_000)
    cross_reach = tv_reach + dig_reach - (tv_reach * dig_reach / 100)
    # CPR
    CPR_TV = tv_price * 10_000 / flight_weeks
    CPR_Digital = dig_cpm * 10_000 * audience_dig / 1000 / flight_weeks
    options.append({
        "TV %": tv_share,
        "Digital %": dig_share,
        "TV Reach %": round(tv_reach,1),
        "Digital Reach %": round(dig_reach,1),
        "Cross Reach %": round(cross_reach,1),
        "CPR_TV": round(CPR_TV,1),
        "CPR_Digital": round(CPR_Digital,1),
        "CPR_Total": round(CPR_TV+CPR_Digital,1)
    })

df = pd.DataFrame(options)

# --- Відображення ---
st.subheader("Варіанти спліту")
def highlight(row):
    if row["TV %"] < 20 or row["Digital %"] < 20:  # просте правило ефективності
        return ["background-color: salmon"]*len(row)
    return ["background-color: lightgreen"]*len(row)

st.dataframe(df.style.apply(highlight, axis=1))

# --- Графік спліту ---
fig, ax = plt.subplots(figsize=(10,4))
ax.bar(df.index, df["TV %"], color="black", label="ТБ")
ax.bar(df.index, df["Digital %"], bottom=df["TV %"], color="red", label="Діджитал")
ax.set_xticks(df.index)
ax.set_xticklabels([str(i+1) for i in df.index])
ax.set_ylabel("Доля бюджету %")
ax.set_xlabel("Опції")
ax.legend()
st.pyplot(fig)

# --- Графік охоплення ---
fig2, ax2 = plt.subplots(figsize=(10,4))
ax2.plot(df.index, df["TV Reach %"], label="ТБ Reach %", color="black", marker='o')
ax2.plot(df.index, df["Digital Reach %"], label="Діджитал Reach %", color="red", marker='o')
ax2.plot(df.index, df["Cross Reach %"], label="Кросмедіа Reach %", color="green", marker='o')
ax2.set_xticks(df.index)
ax2.set_xticklabels([str(i+1) for i in df.index])
ax2.set_ylabel("Reach %")
ax2.set_xlabel("Опції")
ax2.legend()
st.pyplot(fig2)

# --- Завантаження Excel ---
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name="Options", index=False)
    workbook  = writer.book
    worksheet = writer.sheets["Options"]
    
    # Додаємо графіки
    chart1 = workbook.add_chart({'type': 'column'})
    chart1.add_series({'name': 'ТБ', 'values': f'=Options!C2:C{len(df)+1}', 'categories': f'=Options!A2:A{len(df)+1}', 'fill': {'color': 'black'}})
    chart1.add_series({'name': 'Діджитал', 'values': f'=Options!D2:D{len(df)+1}', 'categories': f'=Options!A2:A{len(df)+1}', 'fill': {'color': 'red'}})
    chart1.set_title({'name':'Долі бюджету по опціях'})
    worksheet.insert_chart('J2', chart1)
    
    chart2 = workbook.add_chart({'type': 'line'})
    chart2.add_series({'name':'ТБ Reach', 'values': f'=Options!C2:C{len(df)+1}', 'categories': f'=Options!A2:A{len(df)+1}', 'line': {'color':'black'}})
    chart2.add_series({'name':'Діджитал Reach', 'values': f'=Options!D2:D{len(df)+1}', 'categories': f'=Options!A2:A{len(df)+1}', 'line': {'color':'red'}})
    chart2.add_series({'name':'Кросмедіа Reach', 'values': f'=Options!E2:E{len(df)+1}', 'categories': f'=Options!A2:A{len(df)+1}', 'line': {'color':'green'}})
    chart2.set_title({'name':'Охоплення по опціях'})
    worksheet.insert_chart('J20', chart2)

    writer.save()
st.download_button("Завантажити Excel", data=output.getvalue(), file_name="media_split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


