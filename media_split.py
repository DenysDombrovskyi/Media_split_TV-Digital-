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
st.sidebar.header("Параметри кампанії")

# Бюджет кампанії
budget = st.sidebar.number_input("Бюджет кампанії (грн)", min_value=100_000, max_value=50_000_000, value=5_000_000, step=100_000)
# Крок спліту
split_step = st.sidebar.selectbox("Крок спліту (%)", [5, 10, 15, 20])
# Ціна 1 TRP ТБ
tb_price = st.sidebar.number_input("Ціна 1 TRP ТБ (грн)", min_value=1, max_value=1_000_000, value=500)
# Ціна 1000 імпр. Діджитал
digital_price = st.sidebar.number_input("Ціна 1000 імпр. Діджитал (грн)", min_value=1, max_value=1_000_000, value=1000)
# Клаттер ТБ TRP
tb_clutter = st.sidebar.number_input("Клаттер ТБ TRP", min_value=0, max_value=5000, value=300)
# Клаттер Діджитал імпр.
digital_clutter = st.sidebar.number_input("Клаттер Діджитал імпр. (тис. імпр.)", min_value=0, max_value=5_000_000, value=500_000) # Додано "(тис. імпр.)"
# Кількість опцій для генерації
num_options = st.sidebar.number_input("Кількість опцій", min_value=3, max_value=20, value=10)

st.sidebar.header("Метод естимації охоплень")
# Метод естимації охоплень
est_method = st.sidebar.selectbox("Оберіть метод естимації", ["Логістична крива", "Апроксимація", "Лінійна (для тесту)"])
st.sidebar.markdown("Більш точний метод: Логістична крива")

# --- Input points for TV ---
st.subheader("Точки для ТБ")
tb_points = []
# Збір точок для ТБ (ТРП та Охоплення %)
for i in range(5):
    col1, col2 = st.columns(2)
    trp = col1.number_input(f"ТРП точка {i+1} ТБ", min_value=1.0, max_value=10000.0, value=float(20*(i+1)))
    reach = col2.number_input(f"Охоплення % точка {i+1} ТБ", min_value=1.0, max_value=82.0, value=float(min(20*(i+1), 82)))
    tb_points.append((trp, reach))

# --- Input points for Digital ---
st.subheader("Точки для Діджитал")
digital_points = []
# Збір точок для Діджитал (Імпр. та Охоплення %)
for i in range(5):
    col1, col2 = st.columns(2)
    imp = col1.number_input(f"Імпр. точка {i+1} Діджитал (тис.)", min_value=1.0, max_value=10000.0, value=float(100*(i+1)))
    reach = col2.number_input(f"Охоплення % точка {i+1} Діджитал", min_value=1.0, max_value=99.0, value=float(min(15*(i+1), 99)))
    digital_points.append((imp, reach))

# --- Function for estimation ---
def estimate_reach(points, max_reach, method="Логістична крива"):
    """
    Оцінює охоплення на основі заданих точок та методу.
    :param points: Список кортежів (значення, охоплення %)
    :param max_reach: Максимальне можливе охоплення
    :param method: Метод естимації ("Логістична крива", "Апроксимація", "Лінійна")
    :return: Функція, яка приймає нове значення і повертає оцінене охоплення
    """
    x = np.array([p[0] for p in points])
    y = np.array([p[1] for p in points])
    if method == "Логістична крива":
        from scipy.optimize import curve_fit
        # Функція логістичної кривої
        def logistic(x, k, x0):
            return max_reach / (1 + np.exp(-k*(x - x0)))
        # Підгонка кривої до точок
        try:
            # Збільшено верхню межу для x0, та встановлено меншу min_value для k щоб дозволити більш "пласкі" криві
            popt, _ = curve_fit(logistic, x, y, bounds=([0., -np.inf], [5., np.inf]))
        except RuntimeError:
            st.warning("Не вдалося підігнати логістичну криву. Спробуйте змінити вхідні точки або метод естимації.")
            # Повернення лінійної інтерполяції як резервного варіанту
            f_linear = interp1d(x, y, kind='linear', fill_value="extrapolate")
            return lambda x_new: np.clip(f_linear(x_new), 0, max_reach)
        except ValueError as e:
            st.error(f"Помилка при підгонці логістичної кривої: {e}. Перевірте вхідні точки.")
            f_linear = interp1d(x, y, kind='linear', fill_value="extrapolate")
            return lambda x_new: np.clip(f_linear(x_new), 0, max_reach)


        def f(x_new):
            return np.clip(logistic(x_new, *popt), 0, max_reach)
        return f
    elif method == "Апроксимація":
        # Кубічна інтерполяція
        f = interp1d(x, y, kind='cubic', fill_value=(y[0], max_reach), bounds_error=False)
        return lambda x_new: np.clip(f(x_new), 0, max_reach)
    else:  # Лінійна
        # Лінійна інтерполяція
        f = interp1d(x, y, kind='linear', fill_value="extrapolate")
        return lambda x_new: np.clip(f(x_new), 0, max_reach)

# Оцінка охоплення для ТБ та Діджитал
tb_est = estimate_reach(tb_points, 82, est_method)
digital_est = estimate_reach(digital_points, 99, est_method)

# --- Generate options ---
options = []
# Генерація опцій розподілу бюджету
for i in range(num_options):
    # Розрахунок долі бюджету для поточної опції
    budget_share = (i + 1) * split_step / 100
    
    # Розрахунок TRP ТБ та Impressions Діджитал
    tb_trp = budget_share * (budget / tb_price)
    digital_imp = budget_share * (budget / digital_price)

    # Розрахунок охоплення для ТБ та Діджитал
    tb_reach = tb_est(tb_trp)
    digital_reach = digital_est(digital_imp)

    # Розрахунок кросмедійного охоплення (формула охоплення для двох незалежних медіа)
    cross_reach = tb_reach/100 + digital_reach/100 - (tb_reach/100)*(digital_reach/100)
    
    # Додавання опції до списку
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
# Додаємо стовпці для клатера
df["TB Clutter TRP"] = tb_clutter
df["Digital Clutter IMP (тис)"] = digital_clutter

# Логіка ефективності: опція ефективна, якщо показники вище клатера
df["Ефективний"] = (df["TB TRP"] >= tb_clutter) & (df["Digital IMP (тис)"] >= digital_clutter)

# Розрахунок CPR (Cost Per Reach)
# Перевірка ділення на нуль для CrossMedia Reach
# Якщо CrossMedia Reach дорівнює 0, CPR вважається нескінченним
df["CPR"] = budget / df["CrossMedia Reach %"]
df.loc[df["CrossMedia Reach %"] == 0, "CPR"] = np.inf


# Знаходження найкращої опції (ефективна і найнижчий CPR)
effective_options_df = df[df["Ефективний"]]
if not effective_options_df.empty:
    # Якщо є ефективні опції, знаходимо найкращу серед них
    best_idx = effective_options_df["CPR"].idxmin()
else:
    # Якщо ефективних опцій немає, вибираємо опцію з найнижчим CPR серед усіх (навіть неефективних)
    best_idx = df["CPR"].idxmin()

df["Найкраща"] = False
df.loc[best_idx, "Найкраща"] = True

# --- Display Best Option Summary ---
st.subheader("Найкраща опція")
best_option = df.loc[best_idx]
st.markdown(f"""
    **Опція {int(best_option['Опція'])}** (Найнижчий СПР серед ефективних):
    * **TB TRP**: {best_option['TB TRP']:.2f}
    * **Digital IMP (тис)**: {best_option['Digital IMP (тис)']:.2f}
    * **CrossMedia Reach %**: {best_option['CrossMedia Reach %']:.2f}%
    * **СПР**: {best_option['CPR']:.2f} грн за % охоплення
""")
st.markdown("---")

# --- Display Effective Options ---
st.subheader("Ефективні опції (показники вище клатера)")
# Фільтруємо DataFrame, щоб показати лише ефективні опції
effective_df = df[df["Ефективний"]].copy() # Створюємо копію, щоб уникнути SettingWithCopyWarning
if not effective_df.empty:
    st.dataframe(effective_df.style.apply(highlight, axis=1))
else:
    st.info("Немає опцій, що відповідають критеріям клатера для обох медіа.")
st.markdown("---")


# --- Display all options dataframe ---
def highlight(row):
    """
    Функція для виділення рядків у DataFrame.
    Виділяє найкращу опцію синім, неефективні - світло-червоним.
    """
    if row["Найкраща"]:
        return ['background-color: lightblue']*len(row) # Синя заливка для найкращої опції
    elif not row["Ефективний"]:
        return ['background-color: lightcoral']*len(row) # Світло-червона для неефективних
    else:
        return ['']*len(row)

st.subheader("Усі опції та ефективність")
# Відображення DataFrame з застосованим стилем
st.dataframe(df.style.apply(highlight, axis=1))
st.markdown("---")

# --- Plotly graphs ---
# Графік розподілу бюджету
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

# Графік охоплення по опціях
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=df["Опція"], y=df["TB Reach %"], name="ТБ", mode="lines+markers"))
fig2.add_trace(go.Scatter(x=df["Опція"], y=df["Digital Reach %"], name="Діджитал", mode="lines+markers"))
fig2.add_trace(go.Scatter(x=df["Опція"], y=df["CrossMedia Reach %"], name="Кросмедіа", mode="lines+markers"))
fig2.update_layout(title="Охоплення по опціях", xaxis_title="Опції", yaxis_title="Reach %")
st.plotly_chart(fig2)

# --- Export to Excel ---
output = BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer: # Змінено рушій на 'openpyxl'
    df.to_excel(writer, index=False, sheet_name="Options")
    workbook  = writer.book
    worksheet = writer.sheets["Options"]

    # Create charts in Excel
    # Графік розподілу бюджету
    chart = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
    # Додаємо серії даних для ТБ та Діджитал
    chart.add_series({
        'name': 'ТБ',
        'categories': f'=Options!$A$2:$A${num_options+1}',
        'values': f'=Options!$B$2:$B${num_options+1}',
        'fill': {'color': 'black'}
    })
    chart.add_series({
        'name': 'Діджитал',
        'categories': f'=Options!$A$2:$A${num_options+1}',
        'values': f'=Options!$D$2:$D${num_options+1}',
        'fill': {'color': 'red'}
    })
    chart.set_title({'name': 'Розподіл бюджету'})
    chart.set_y_axis({'name': 'Доля бюджету'})
    worksheet.insert_chart('H2', chart) # Розміщення графіку в Excel

    # writer.save() # Цей рядок був видалений, оскільки 'with' оператор автоматично зберігає та закриває
st.download_button("⬇️ Завантажити результати в Excel", data=output.getvalue(), file_name="media_split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
