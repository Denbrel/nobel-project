import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- Настройка страницы ---
st.set_page_config(page_title="Нобелевская аналитика", layout="wide")
st.title("🏆 Аналитика Нобелевских Лауреатов (Digital Humanities)")
st.markdown("Проект по исследованию интеллектуальной миграции и центров знаний.")

# --- 1. Извлечение данных из БД ---
# Обязательное требование: Декоратор (кэширует данные, чтобы база не дергалась при каждом клике)
@st.cache_data
def load_data():
    conn = sqlite3.connect('nobel_database.sqlite')
    # SQL-запрос, объединяющий лауреатов и их премии (JOIN)
    query = '''
        SELECT l.id, l.name, l.gender, l.birth_year, l.birth_country, l.lat, l.lon, 
               p.award_year, p.category, p.prize_amount
        FROM laureates l
        JOIN prizes p ON l.id = p.laureate_id
        WHERE l.lat IS NOT NULL AND l.lon IS NOT NULL
    '''
    df = pd.read_sql_query(query, conn)
    # Вычисляем возраст лауреата на момент получения премии
    df['award_age'] = df['award_year'] - df['birth_year']
    return df

df = load_data()

# --- 2. Фильтры (Сайдбар) - Требование "менять параметры" ---
st.sidebar.header("Параметры фильтрации")
selected_gender = st.sidebar.multiselect("Пол", df['gender'].dropna().unique(), default=df['gender'].dropna().unique())
selected_category = st.sidebar.multiselect("Категория", df['category'].unique(), default=df['category'].unique())
min_year, max_year = st.sidebar.slider("Год получения премии", int(df['award_year'].min()), int(df['award_year'].max()), (1901, 2024))

# Применяем фильтры к датафрейму
filtered_df = df[
    (df['gender'].isin(selected_gender)) &
    (df['category'].isin(selected_category)) &
    (df['award_year'] >= min_year) &
    (df['award_year'] <= max_year)
]

st.write(f"Найдено премий по вашим фильтрам: **{len(filtered_df)}**")

# --- 3. Визуализация 1: Интерактивная Карта ---
st.subheader("🌍 География рождения лауреатов")
# Plotly Scatter Geo сам рисует карту мира и наносит координаты
fig_map = px.scatter_geo(
    filtered_df,
    lat='lat',
    lon='lon',
    hover_name='name',
    hover_data=['birth_country', 'category', 'award_year'],
    color='category',
    projection="natural earth",
    opacity=0.7,
    size_max=10
)
fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig_map, use_container_width=True)

col1, col2 = st.columns(2)

# --- 4. Визуализация 2: Гистограмма возраста ---
with col1:
    st.subheader("📊 Возраст получения премии")
    fig_age = px.histogram(
        filtered_df, 
        x="award_age", 
        nbins=25, 
        color="category",
        labels={'award_age': 'Возраст', 'count': 'Количество'}
    )
    st.plotly_chart(fig_age, use_container_width=True)

# --- 5. Визуализация 3: Динамика по годам ---
with col2:
    st.subheader("📈 Количество премий по десятилетиям")
    # Группируем по годам и категориям
    df_grouped = filtered_df.groupby(['award_year', 'category']).size().reset_index(name='count')
    fig_trend = px.area(
        df_grouped, 
        x='award_year', 
        y='count', 
        color='category',
        labels={'award_year': 'Год', 'count': 'Количество премий'}
    )
    st.plotly_chart(fig_trend, use_container_width=True)
