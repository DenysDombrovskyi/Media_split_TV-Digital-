import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import interp1d
import plotly.graph_objects as go
from io import BytesIO

st.set_page_config(page_title="Media Split Dashboard", layout="wide")

st.title("Media Split Dashboard")

# --- Sidebar for inputs ---
st.sidebar.header("Кампанія параметри")

budget = st.sidebar.number_input("Бюджет кампанії", min_value=100_000, max_value=50_000_000, value=5_000_000, step=100_000)
split_step = st.sidebar.selectbox("Крок спліту (%)", [5, 10, 15, 20])
tb_price = st.sidebar.number_input("Ціна 1 TRP ТБ (грн)", min_value=1_000, max_value=1_000_000, value=500)
digital_price = st.sidebar.number_input("Ціна 1000 імпр. Діджитал (грн)", min_value=100, max_value=1_000_000, value=1000)
tb_clutter = st.sidebar.number_input("Клаттер ТБ TRP", min_value=0, max_value=5000, value=300)
digital_clutter = st.sidebar.number_input("Клаттер Діджитал імпр.", min_value=0, max_value=5_000_000, value=500_000)
num_options = st.sidebar.number_input("Кількість опцій", min_value=3, max_value=20, value=10)

st.sidebar.header("Метод естимації охоплень")
est_method = st.sidebar.selectbox("Оберіть метод естимації", ["Логістична крива", "Апроксимація", "Лінійна (для тесту)"])
st.sidebar.markdown("Більш точний метод: Логістична крива")

# --- Input points for TV ---
st.subheader("Точки для ТБ")
tb_points = []
for i in range(5):
    col1, col2 = st.columns(2)
    trp = col1.number_input(f"ТРП точка {i+1} ТБ", min_value=1.0, max_value=10000.0, value=20*(i+1))
    reach = col2.number_input(f"Охоплення % точка {i+1} ТБ", min_value=1.0, max_value=82.0, value=min(20*(i+1), 82))
    tb_points.append((trp, reach))

# --- Input points for Digital ---
st.subheader("Точки для Діджитал")
digital_points = []
for i in range(5):
    col1, col2 = st.columns(2)
    imp = col1.number_input(f"Імпр. точка {i+1} Діджитал (тис.)", min_value=1.0, max_value=10000.0, value=100*(i+1))
    reach = col2.number_input(f"Охоплення % точка {i+1} Діджитал", min_value=1.0, max_value=99.0, value=min(15*(i+1), 99))
    digital_points.append((imp, reach))

# --- Function for estimation ---
def estimate_reach(points, max_reach, method="Логістична крива"):
    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])
    if method == "Логістична крива":
        # Fit logistic curve: y = max_reach / (1 + exp(-k*(x-x0)))
        from scipy.optimize import curve_fit
        def logistic(x, k, x0):
            return max_reach / (1 + np.exp(-k*(x - x0)))
        popt, _ = curve_fit(logistic, x, y, bounds=(0, [5., max(x)]))
        def f(x_new):
            return np.clip(logistic(x_new, *popt), 0, max_reach)
        return f
    elif method == "Апроксимація":
        f = interp1d(x, y, kind='cubic', fill_value=(y[0], max_reach), bounds_error=False)
        return lambda x_new: np.clip(f(x_new), 0, max_reach)
    else:  # Лінійна
        f = interp1d(x, y, kind='linear', fill_value="extrapolate")
        return lambda x_new: np.clip(f(x_new), 0, max_reach)

tb_est = estimate_reach(tb_points, 82, est_method)
digital_est = estimate_reach(digital_points, 99, est_method)

# --- Generate options ---
options = []
for i in range(num_options):
    tb_trp = (i+1) * split_step / 100 * (budget / tb_price)
    digital_imp = (i+1) * split_step / 100 * (budget / digital_price)
    tb_reach = tb_est(tb_trp)
    digital_reach = digital_est(digital_imp)
    cross_reach = tb_reach/100 + digital_reach/100 - (tb_reach/100)*(digital_reach/100)
    options.append({
        "Опція": i+1,
        "TB TRP": tb_trp,
        "TB Reach %": tb_reach,
        "Digital IMP (тис)": digital_imp,
        "Digital Reach %": digital_reach,
        "CrossMedia Reach %": cross_reach*100
    })

df = pd.DataFrame(options)

# --- Calculate efficiency ---
df["Ефективний"] = (df["TB TRP"] >= tb_clutter) & (df["Digital IMP (тис)"] >= digital_clutter)
df["CPR"] = budget / (df["TB TRP"] + df["Digital IMP (тис)"]/1000)
best_idx = df[df["Ефективний"]]["CPR"].idxmin() if df["Ефективний"].any() else df["CPR"].idxmin()
df["Best"] = False
df.loc[best_idx, "Best"] = True

# --- Display dataframe ---
def highlight(row):
    if row["Best"]:
        return ['background-color: lightgreen']*len(row)
    elif not row["Ефективний"]:
        return ['background-color: lightcoral']*len(row)
    else:
        return ['']*len(row)

st.subheader("Опції та ефективність")
st.dataframe(df.style.apply(highlight, axis=1))

# --- Plotly graphs ---
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df["Опція"],
    y=(df["TB TRP"]*tb_price)/(budget),
    name="ТБ",
    marker_color='black'
))
fig.add_trace(go.Bar(
    x=df["Опція"],
    y=(df["Digital IMP (тис)"]*digital_price)/(budget),
    name="Діджитал",
    marker_color='red'
))
fig.update_layout(barmode='stack', title="Розподіл бюджету (долі)", xaxis_title="Опції", yaxis_title="Доля бюджету")
st.plotly_chart(fig)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=df["Опція"], y=df["TB Reach %"], name="ТБ", mode="lines+markers"))
fig2.add_trace(go.Scatter(x=df["Опція"], y=df["Digital Reach %"], name="Діджитал", mode="lines+markers"))
fig2.add_trace(go.Scatter(x=df["Опція"], y=df["CrossMedia Reach %"], name="Кросмедіа", mode="lines+markers"))
fig2.update_layout(title="Охоплення по опціях", xaxis_title="Опції", yaxis_title="Reach %")
st.plotly_chart(fig2)

# --- Export to Excel ---
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name="Options")
    workbook  = writer.book
    worksheet = writer.sheets["Options"]

    # Create charts
    chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
    chart.add_series({'name': 'ТБ', 'categories': f'=Options!$A$2:$A${num_options+1}', 'values': f'=Options!$B$2:$B${num_options+1}', 'fill': {'color': 'black'}})
    chart.add_series({'name': 'Діджитал', 'categories': f'=Options!$A$2:$A${num_options+1}', 'values': f'=Options!$D$2:$D${num_options+1}', 'fill': {'color': 'red'}})
    chart.set_title({'name': 'Розподіл бюджету'})
    chart.set_y_axis({'name': 'Доля бюджету'})
    worksheet.insert_chart('H2', chart)

    writer.save()
st.download_button("⬇️ Завантажити результати в Excel", data=output.getvalue(), file_name="media_split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
