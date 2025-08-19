import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

st.title("Оптимальний спліт ТБ / Digital")

# Вхідні дані
budget = st.number_input("Загальний бюджет", min_value=1000, step=1000)
weeks = st.number_input("Тривалість флайту (тижні)", min_value=1, value=4)

# ТВ параметри
st.subheader("Телебачення")
tv_cpt = st.number_input("Вартість 1 TRP (грн)", min_value=1.0, value=10000.0)
comp_tv_trp_week = st.number_input("Тиск конкурентів у ТБ (TRP/тиждень)", min_value=0, value=50)

# Digital параметри
st.subheader("Digital")
dig_cpm = st.number_input("Вартість 1000 цільових імпресій (грн)", min_value=1.0, value=200.0)
comp_dig_imp_week = st.number_input("Тиск конкурентів у Digital (тис. імпресій/тиждень)", min_value=0, value=500)

# Функції охоплення
def reach_tv(trp):
    return 1 - np.exp(-0.015 * trp)

def reach_digital(imps_mln):
    return 1 - np.exp(-0.25 * imps_mln)

options = []
for share in np.linspace(0.1, 0.9, 9):  # 9 опцій від 10% до 90%
    tv_budget = budget * share
    dig_budget = budget * (1 - share)

    tv_trp = tv_budget / tv_cpt
    dig_imps = dig_budget / dig_cpm * 1000  # бо CPM

    # Тижневий тиск
    tv_weekly_trp = tv_trp / weeks
    dig_weekly_imp = dig_imps / weeks / 1000  # в тис.

    # Мінімальні вимоги
    if tv_weekly_trp < comp_tv_trp_week or dig_weekly_imp < comp_dig_imp_week:
        continue

    # Охоплення
    r_tv = reach_tv(tv_trp)
    r_dig = reach_digital(dig_imps / 1e6)  # в млн

    r_cross = 1 - (1 - r_tv) * (1 - r_dig)

    # SPP
    som_tv = share
    som_dig = 1 - share
    sov_tv = tv_weekly_trp / (tv_weekly_trp + comp_tv_trp_week) if (tv_weekly_trp + comp_tv_trp_week) > 0 else 0
    sov_dig = dig_weekly_imp / (dig_weekly_imp + comp_dig_imp_week) if (dig_weekly_imp + comp_dig_imp_week) > 0 else 0

    spp_tv = sov_tv / som_tv if som_tv > 0 else 0
    spp_dig = sov_dig / som_dig if som_dig > 0 else 0

    # Статус
    status = "✅ ОК"
    if tv_weekly_trp < comp_tv_trp_week and dig_weekly_imp < comp_dig_imp_week:
        status = "❌ Нижче конкурентів у ТБ та Digital"
    elif tv_weekly_trp < comp_tv_trp_week:
        status = "❌ Нижче конкурентів у ТБ"
    elif dig_weekly_imp < comp_dig_imp_week:
        status = "❌ Нижче конкурентів у Digital"

    options.append({
        "ТБ %": round(share*100),
        "Digital %": round((1-share)*100),
        "TRP total": round(tv_trp, 1),
        "TRP/week": round(tv_weekly_trp, 1),
        "Imp (млн)": round(dig_imps/1e6, 2),
        "Imp/week (тис.)": round(dig_weekly_imp, 1),
        "Reach TV": round(r_tv*100, 1),
        "Reach Dig": round(r_dig*100, 1),
        "Cross Reach": round(r_cross*100, 1),
        "SPP TV": round(spp_tv, 2),
        "SPP Dig": round(spp_dig, 2),
        "Status": status
    })

# --- Перевірка бюджету ---
min_budget_tv = comp_tv_trp_week * weeks * tv_cpt  # мін. бюджет на ТБ
min_budget_dig = comp_dig_imp_week * weeks * dig_cpm  # мін. бюджет на Digital (тис. CPM → множимо)
min_total_budget = min_budget_tv + min_budget_dig

if not options:
    st.error(f"Ваш бюджет = {budget:,.0f} грн\n"
             f"Мінімальний бюджет = {min_total_budget:,.0f} грн\n"
             f"Недостатньо: треба +{(min_total_budget - budget):,.0f} грн\n\n"
             f"👉 Спробуйте скоротити тривалість флайту (зараз {weeks} тижнів).")
else:
    df = pd.DataFrame(options)
    st.dataframe(df)

    # Завантаження в Excel
    excel_file = "split_results.xlsx"
    df.to_excel(excel_file, index=False)

    with open(excel_file, "rb") as f:
        st.download_button("⬇️ Завантажити Excel", f, file_name=excel_file)

    # --- Візуалізація ---
    st.subheader("Візуалізація Cross Reach")
    fig, ax = plt.subplots()

    for i, row in df.iterrows():
        color = "green" if "✅" in row["Status"] else "red"
        ax.scatter(row["ТБ %"], row["Cross Reach"], color=color, s=100)
        ax.text(row["ТБ %"], row["Cross Reach"]+0.5, row["Status"], fontsize=8, ha="center")

    ax.set_xlabel("Частка бюджету на ТБ (%)")
    ax.set_ylabel("Cross Reach (%)")
    ax.set_title("Кросмедійне охоплення за різних сплітів")
    st.pyplot(fig)
