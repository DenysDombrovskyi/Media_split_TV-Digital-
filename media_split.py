import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize

# --- Вхідні параметри ---
st.title("📊 Оптимальний спліт ТБ + Digital")

budget = st.number_input("Загальний бюджет", min_value=1000, step=1000, value=50000)
flight_weeks = st.number_input("Тривалість флайту (тижні)", min_value=1, value=4)

# --- TV параметри ---
tv_cost_per_reach = st.number_input("Вартість 1 охоплення в ТБ", value=5.0)
tv_weekly_clutter = st.number_input("Клаттер конкурентів (ТРП/тиждень в ТБ)", value=100.0)

# --- Digital параметри ---
digital_cost_per_reach = st.number_input("Вартість 1 охоплення в Digital", value=2.0)
digital_weekly_clutter = st.number_input("Клаттер конкурентів (імпресії/тиждень)", value=50000.0)

# --- Скільки варіантів ---
n_options = st.slider("Кількість варіантів сплітів", 5, 15, 10)

# --- Генерація варіантів ---
results = []
for split in np.linspace(0.1, 0.9, n_options):  # від 10% до 90%
    tv_budget = budget * split
    digital_budget = budget * (1 - split)

    # Охоплення
    tv_reach = tv_budget / tv_cost_per_reach
    digital_reach = digital_budget / digital_cost_per_reach

    # Ймовірність крос-медійного охоплення
    cross_reach = 1 - (1 - tv_reach/1e6) * (1 - digital_reach/1e6)  # нормалізація

    # Тиск (TV = TRP, Digital = імпресії)
    tv_pressure = tv_reach / flight_weeks
    digital_pressure = digital_reach / flight_weeks

    # Перевірка конкурентів
    tv_ok = tv_pressure >= tv_weekly_clutter
    digital_ok = digital_pressure >= digital_weekly_clutter
    overall_ok = tv_ok and digital_ok

    results.append({
        "Спліт ТБ": f"{split*100:.0f}%",
        "Бюджет ТБ": int(tv_budget),
        "Бюджет Digital": int(digital_budget),
        "Охоплення ТБ": int(tv_reach),
        "Охоплення Digital": int(digital_reach),
        "Крос-охоплення": f"{cross_reach*100:.1f}%",
        "Тиск ТБ/тижд": int(tv_pressure),
        "Тиск Digital/тижд": int(digital_pressure),
        "Ефективний": overall_ok
    })

df = pd.DataFrame(results)

# --- Підсвітка кольорами ---
def highlight(row):
    color = "background-color: lightgreen" if row["Ефективний"] else "background-color: lightcoral"
    return [color] * len(row)

st.subheader("📑 Результати")
st.dataframe(df.style.apply(highlight, axis=1))

# --- Графік ---
st.subheader("📈 Візуалізація сплітів")
fig, ax = plt.subplots()
ax.plot(df["Спліт ТБ"], [float(x[:-1]) for x in df["Крос-охоплення"]], marker="o")
ax.set_ylabel("Крос-охоплення %")
ax.set_xlabel("Спліт ТБ")
ax.set_title("Крос-медійне охоплення залежно від спліта")
plt.xticks(rotation=45)
st.pyplot(fig)

# --- Експорт ---
st.download_button(
    "⬇️ Завантажити результати в Excel",
    data=df.to_excel("results.xlsx", index=False, engine="openpyxl"),
    file_name="media_split.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

