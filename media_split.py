import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from itertools import product

# -------------------------------
# Допоміжні функції
# -------------------------------

def cross_media_reach(reach_tv, reach_digital):
    """Кросмедійне охоплення як ймовірність двох незалежних подій"""
    return reach_tv + reach_digital - (reach_tv * reach_digital)

def calculate_option(budget, cost_tv, cost_digital, 
                     clutter_tv, clutter_digital,
                     competitor_tv, competitor_digital,
                     weeks, share_tv):
    """
    Розрахунок одного спліта ТВ/Діджитал
    """
    spend_tv = budget * share_tv
    spend_digital = budget * (1 - share_tv)

    # Якщо немає грошей
    if spend_tv < cost_tv or spend_digital < cost_digital:
        return None

    # Розрахунок тиску
    trp_tv = spend_tv / cost_tv
    trp_digital = spend_digital / cost_digital

    # Клаттер
    eff_trp_tv = max(0, trp_tv - clutter_tv)
    eff_trp_digital = max(0, trp_digital - clutter_digital)

    # Охоплення (умовно: saturating function)
    reach_tv = 1 - np.exp(-eff_trp_tv / (weeks * 100))
    reach_digital = 1 - np.exp(-eff_trp_digital / (weeks * 100))

    # Кросмедійне охоплення
    cross_reach = cross_media_reach(reach_tv, reach_digital)

    # Перевірка конкурентів
    tv_vs_comp = "OK" if eff_trp_tv >= competitor_tv else "Нижче конкурентів"
    dig_vs_comp = "OK" if eff_trp_digital >= competitor_digital else "Нижче конкурентів"

    return {
        "Share TV": round(share_tv * 100, 1),
        "Spend TV": round(spend_tv, 0),
        "Spend Digital": round(spend_digital, 0),
        "TRP TV": round(eff_trp_tv, 1),
        "TRP Digital": round(eff_trp_digital, 1),
        "Reach TV": round(reach_tv * 100, 1),
        "Reach Digital": round(reach_digital * 100, 1),
        "Cross Reach": round(cross_reach * 100, 1),
        "TV vs Competitors": tv_vs_comp,
        "Digital vs Competitors": dig_vs_comp
    }

# -------------------------------
# Streamlit UI
# -------------------------------

st.title("📊 Оптимальний спліт ТВ / Діджитал")

budget = st.number_input("Загальний бюджет, $", min_value=1000, value=100000, step=1000)
cost_tv = st.number_input("Вартість 1 TRP на ТБ, $", min_value=1, value=500)
cost_digital = st.number_input("Вартість 1000 цільових імпресій, $", min_value=1, value=5)

clutter_tv = st.number_input("Клаттер (ТРП на тиждень)", min_value=0, value=50)
clutter_digital = st.number_input("Клаттер (тис. імпресій на тиждень)", min_value=0, value=100)

competitor_tv = st.number_input("Конкурентний тиск на ТБ (ТРП на тиждень)", min_value=0, value=150)
competitor_digital = st.number_input("Конкурентний тиск у Digital (тис. імпресій на тиждень)", min_value=0, value=300)

weeks = st.number_input("Тривалість флайту (тижні)", min_value=1, value=4)
num_options = st.slider("Кількість варіантів", min_value=5, max_value=10, value=5)

# -------------------------------
# Генерація варіантів
# -------------------------------
results = []
splits = np.linspace(0.1, 0.9, num_options)  # частки ТВ

for share_tv in splits:
    option = calculate_option(
        budget, cost_tv, cost_digital,
        clutter_tv, clutter_digital,
        competitor_tv, competitor_digital,
        weeks, share_tv
    )
    if option:
        results.append(option)

if results:
    df = pd.DataFrame(results)
    st.dataframe(df)

    # Графік
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(df["Share TV"], df["Cross Reach"], marker="o")
    ax.set_xlabel("Частка ТВ, %")
    ax.set_ylabel("Кросмедійне охоплення, %")
    ax.set_title("Залежність охоплення від спліту")
    st.pyplot(fig)

    # Експорт
    if st.button("📥 Завантажити Excel"):
        file_path = "media_split_results.xlsx"
        df.to_excel(file_path, index=False)
        with open(file_path, "rb") as f:
            st.download_button("Скачати файл", f, file_name=file_path)
else:
    st.error("❌ Недостатньо бюджету для запуску кампанії. Спробуйте збільшити бюджет або скоротити тривалість флайту.")

