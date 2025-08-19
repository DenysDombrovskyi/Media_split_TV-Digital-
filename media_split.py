import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import interp1d
import io
import plotly.graph_objects as go

st.set_page_config(page_title="Media Split Optimizer", layout="wide")

st.title("Media Split Optimizer: ТБ + Діджитал")

# --- Бічна панель ---
st.sidebar.header("Параметри кампанії")

budget = st.sidebar.number_input("Бюджет кампанії, грн", min_value=100000, max_value=50000000, value=5000000, step=100000)
step = st.sidebar.selectbox("Крок спліту по бюджету (%)", options=[5,10,15,20], index=1)
tv_price = st.sidebar.number_input("Вартість 1 TRP ТБ, грн", min_value=100, value=500)
digital_price = st.sidebar.number_input("Вартість 1000 імпресій, грн", min_value=1, value=50)
tv_clutter = st.sidebar.number_input("Клаттер конкурентів ТБ (TRP/тиждень)", min_value=0, value=100)
digital_clutter = st.sidebar.number_input("Клаттер конкурентів Діджитал (імпр.)", min_value=0, value=500000)
num_options = st.sidebar.number_input("Кількість опцій", min_value=1, max_value=20, value=10)

st.sidebar.header("Метод естимації охоплення")
method = st.sidebar.selectbox("Вибір методу", ["Лінійна", "Логістична", "Апроксимація"], index=2)
st.sidebar.info("Рекомендовано: логістична або апроксимація для точнішої оцінки охоплень")

# --- Введення точок для естимації ---
st.subheader("Введіть точки ТРП та охоплень")

def input_points(media_name, max_reach):
    trp_points = []
    reach_points = []
    cols = st.columns(5)
    for i in range(5):
        with cols[i]:
            trp = st.number_input(f"{media_name} TRP точка {i+1}", min_value=1.0, max_value=10000.0, value=20*(i+1), step=1.0)
            reach = st.number_input(f"{media_name} Reach % точка {i+1}", min_value=1.0, max_value=max_reach, value=min(max_reach,20.0*(i+1)), step=1.0)
            trp_points.append(trp)
            reach_points.append(reach)
    return trp_points, reach_points

tv_max_reach = 82
digital_max_reach = 99

st.markdown("### ТБ точки")
tv_trp_points, tv_reach_points = input_points("ТБ", tv_max_reach)
st.markdown("### Діджитал точки")
digital_trp_points, digital_reach_points = input_points("Діджитал", digital_max_reach)

# --- Функція естимації ---
def estimate_reach(trp_points, reach_points, trp_target, method="Логістична", max_reach=100):
    trp_points = np.array(trp_points)
    reach_points = np.array(reach_points)
    if method=="Лінійна":
        f = interp1d(trp_points, reach_points, fill_value="extrapolate")
        reach_est = f(trp_target)
    elif method=="Логістична":
        # логістична апроксимація: R = max_reach / (1 + exp(-k*(TRP - x0)))
        from scipy.optimize import curve_fit
        def logistic(x, k, x0):
            return max_reach / (1 + np.exp(-k*(x - x0)))
        try:
            popt, _ = curve_fit(logistic, trp_points, reach_points, maxfev=10000, p0=[0.001, np.median(trp_points)])
            reach_est = logistic(trp_target, *popt)
        except:
            f = interp1d(trp_points, reach_points, fill_value="extrapolate")
            reach_est = f(trp_target)
    else:  # апроксимація
        f = interp1d(trp_points, reach_points, kind='quadratic', fill_value="extrapolate")
        reach_est = f(trp_target)
    reach_est = np.clip(reach_est, 0, max_reach)
    return reach_est

# --- Генерація опцій ---
options = []
for i in range(num_options):
    tv_trp = budget * (step/100) / tv_price * (i+1)/num_options
    digital_trp = budget * (step/100) / digital_price * (i+1)/num_options
    tv_reach = estimate_reach(tv_trp_points, tv_reach_points, tv_trp, method, max_reach=tv_max_reach)
    digital_reach = estimate_reach(digital_trp_points, digital_reach_points, digital_trp, method, max_reach=digital_max_reach)
    cross_reach = tv_reach + digital_reach - tv_reach*digital_reach/100
    cpr = budget / (tv_trp + digital_trp)
    effective = (tv_trp>=tv_clutter) and (digital_trp>=digital_clutter)
    options.append([i+1, tv_trp, digital_trp, tv_reach, digital_reach, cross_reach, cpr, effective])

df = pd.DataFrame(options, columns=["Опція","TRP ТБ","TRP Діджитал","TV Reach %","Digital Reach %","Кросмедійне %","CPR","Ефективний"])

# --- Виділення ефективних ---
def highlight(row):
    color = 'background-color: lightgreen' if row["Ефективний"] else 'background-color: lightcoral'
    return [color]*len(row)

st.subheader("Опції медіа спліту")
st.dataframe(df.style.apply(highlight, axis=1))

# --- Графіки ---
st.subheader("Графіки спліту і охоплень")

fig_split = go.Figure()
fig_split.add_trace(go.Bar(
    x=df["Опція"],
    y=df["TRP ТБ"],
    name="ТБ",
    marker_color='black'
))
fig_split.add_trace(go.Bar(
    x=df["Опція"],
    y=df["TRP Діджитал"],
    name="Діджитал",
    marker_color='red'
))
fig_split.update_layout(barmode='stack', xaxis_title="Опція", yaxis_title="TRP / Долі бюджету")
st.plotly_chart(fig_split, use_container_width=True)

fig_reach = go.Figure()
fig_reach.add_trace(go.Bar(
    x=df["Опція"],
    y=df["Кросмедійне %"],
    name="Кросмедіа",
    marker_color='blue'
))
fig_reach.update_layout(xaxis_title="Опція", yaxis_title="Кросмедійне охоплення %")
st.plotly_chart(fig_reach, use_container_width=True)

# --- Експорт в Excel ---
st.subheader("Експорт результатів")
output = io.BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name="Опції", index=False)
    workbook = writer.book
    worksheet = writer.sheets["Опції"]

    # Графік спліту
    chart1 = workbook.add_chart({'type':'column', 'subtype':'stacked'})
    for i, col in enumerate(['TRP ТБ','TRP Діджитал']):
        chart1.add_series({
            'name': col,
            'categories': f'=Опції!$A$2:$A${len(df)+1}',
            'values': f'=Опції!${chr(66+i)}$2:${chr(66+i)}${len(df)+1}',
        })
    chart1.set_title({'name': 'Розподіл спліту ТБ/Діджитал'})
    worksheet.insert_chart('J2', chart1)

    # Графік кросмедіа
    chart2 = workbook.add_chart({'type':'column'})
    chart2.add_series({
        'name': 'Кросмедійне',
        'categories': f'=Опції!$A$2:$A${len(df)+1}',
        'values': f'=Опції!$F$2:$F${len(df)+1}',
        'fill': {'color': 'blue'}
    })
    chart2.set_title({'name':'Кросмедійне охоплення'})
    worksheet.insert_chart('J20', chart2)

    writer.save()
st.download_button(
    label="⬇️ Завантажити результати в Excel",
    data=output.getvalue(),
    file_name="media_split.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


