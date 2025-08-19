import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from scipy.interpolate import CubicSpline

st.title("📊 Оптимальний спліт ТБ + Digital з інтерполяцією охоплення")

# --- Завантаження даних ---
st.subheader("1️⃣ Завантажте CSV або Excel з точками охоплення")
uploaded_file = st.file_uploader("Файл з точками охоплення", type=["csv","xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df_points = pd.read_csv(uploaded_file)
    else:
        df_points = pd.read_excel(uploaded_file)

    st.write("Дані з файлу:")
    st.dataframe(df_points)

    # Перевірка колонок
    if all(col in df_points.columns for col in ["TRP_TV","Reach_TV","Imp_Digital","Reach_Digital"]):
        # --- Інтерполяція ---
        tv_spline = CubicSpline(df_points["TRP_TV"], df_points["Reach_TV"])
        dig_spline = CubicSpline(df_points["Imp_Digital"], df_points["Reach_Digital"])

        # --- Вхідні параметри ---
        budget = st.number_input("Загальний бюджет", min_value=1000, step=1000, value=50000)
        flight_weeks = st.number_input("Тривалість флайту (тижні)", min_value=1, value=4)
        tv_cost_per_trp = st.number_input("Вартість 1 TRP в ТБ", value=500.0)
        dig_cost_per_imp = st.number_input("Вартість 1 тис. імпресій в Digital", value=5.0)
        tv_weekly_clutter = st.number_input("Конкурентний тиск ТБ (ТРП/тиждень)", value=150.0)
        dig_weekly_clutter = st.number_input("Конкурентний тиск Digital (тис. імпресій/тиждень)", value=300.0)
        n_options = st.slider("Кількість варіантів сплітів", 5, 15, 10)

        # --- Розрахунок мінімального бюджету ---
        min_budget_tv = tv_weekly_clutter * flight_weeks * tv_cost_per_trp
        min_budget_dig = dig_weekly_clutter * flight_weeks * dig_cost_per_imp / 1000
        min_total_budget = min_budget_tv + min_budget_dig

        if budget < min_total_budget:
            st.warning(f"❌ Поточний бюджет ({int(budget)}) замалий для ефективного спліту. "
                       f"Рекомендований мінімальний бюджет: {int(min_total_budget)}")

        # --- Генерація варіантів ---
        results = []
        for split in np.linspace(0.1, 0.9, n_options):
            tv_budget = budget * split
            dig_budget = budget * (1 - split)

            tv_trp = tv_budget / tv_cost_per_trp
            dig_imp = dig_budget / dig_cost_per_imp * 1000  # у одиницях тисяч

            # Охоплення через сплайн
            tv_reach = float(np.clip(tv_spline(tv_trp), 0, 1))
            dig_reach = float(np.clip(dig_spline(dig_imp), 0, 1))

            # Кросмедійне охоплення
            cross_reach = tv_reach + dig_reach - tv_reach * dig_reach

            # Тиск
            tv_weekly = tv_trp / flight_weeks
            dig_weekly = dig_imp / flight_weeks / 1000  # у тисячах

            # Перевірка конкурентів
            tv_ok = tv_weekly >= tv_weekly_clutter
            dig_ok = dig_weekly >= dig_weekly_clutter
            overall_ok = tv_ok and dig_ok

            results.append({
                "Спліт ТБ": f"{split*100:.0f}%",
                "Бюджет ТБ": int(tv_budget),
                "Бюджет Digital": int(dig_budget),
                "TRP_TV": round(tv_trp,1),
                "Imp_Digital": int(dig_imp),
                "Reach_TV %": round(tv_reach*100,1),
                "Reach_Digital %": round(dig_reach*100,1),
                "Cross_Reach %": round(cross_reach*100,1),
                "Тиск ТБ/тижд": round(tv_weekly,1),
                "Тиск Digital/тижд": round(dig_weekly,1),
                "Ефективний": overall_ok
            })

        df = pd.DataFrame(results)

        # --- Підсвітка ---
        def highlight(row):
            color = "background-color: lightgreen" if row["Ефективний"] else "background-color: lightcoral"
            return [color]*len(row)

        st.subheader("📑 Результати")
        st.dataframe(df.style.apply(highlight, axis=1))

        # --- Графік ---
        st.subheader("📈 Кросмедійне охоплення")
        fig, ax = plt.subplots()
        cross_values = df["Cross_Reach %"]
        colors = ["green" if x else "red" for x in df["Ефективний"]]
        ax.scatter(df["Спліт ТБ"], cross_values, c=colors, s=100)
        ax.set_ylabel("Кросмедійне охоплення %")
        ax.set_xlabel("Спліт ТБ")
        ax.set_title("Кросмедійне охоплення залежно від спліта")
        plt.xticks(rotation=45)
        st.pyplot(fig)

        # --- Експорт Excel ---
        st.subheader("⬇️ Завантаження Excel")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Splits")
        output.seek(0)
        st.download_button(
            label="Скачати Excel",
            data=output,
            file_name="media_split.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("Файл повинен містити колонки: TRP_TV, Reach_TV, Imp_Digital, Reach_Digital")
else:
    st.info("Завантажте файл з точками охоплення, щоб почати")

