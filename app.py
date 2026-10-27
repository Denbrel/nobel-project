import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import pydeck as pdk

# --- Настройка премиального дизайна ---
st.set_page_config(page_title="Интеллектуальная Миграция", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    /* Немного CSS для красоты заголовков */
    h1 { color: #F2C94C; font-weight: 300; }
    .subtitle { font-size: 1.2em; color: #E0E0E0; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🏛️ Центры Знаний: Интеллектуальная Миграция")
st.markdown('<p class="subtitle">Анализ географии и перемещений выдающихся деятелей науки и культуры.</p>', unsafe_allow_html=True)

@st.cache_data
def load_data():
    conn = sqlite3.connect('nobel_database.sqlite')
    query = '''
        SELECT l.id, l.name, l.gender, l.birth_year, l.birth_city, l.birth_country, l.lat, l.lon, 
               p.award_year, p.category, p.motivation, p.work_lat, p.work_lon, p.work_city
        FROM laureates l
        JOIN prizes p ON l.id = p.laureate_id
        WHERE l.lat IS NOT NULL AND l.lon IS NOT NULL
    '''
    df = pd.read_sql_query(query, conn)
    df['award_age'] = df['award_year'] - df['birth_year']
    
    # Для дуг нам нужны только те, кто мигрировал (есть место работы)
    df['has_moved'] = df['work_lat'].notnull()
    return df

df = load_data()

# --- ФИЛЬТРЫ ---
st.sidebar.header("Параметры фильтрации")
selected_category = st.sidebar.multiselect("Категория (Премия)", df['category'].unique(), default=df['category'].unique())
min_year, max_year = st.sidebar.slider("Год вручения", int(df['award_year'].min()), int(df['award_year'].max()), (1901, 2024))

filtered_df = df[
    (df['category'].isin(selected_category)) &
    (df['award_year'] >= min_year) &
    (df['award_year'] <= max_year)
]

# --- ВИЗУАЛИЗАЦИЯ 1: FLOW MAP (PYDECK) ---
st.subheader("🌐 Карта интеллектуальной миграции (Birth ➔ Work)")
st.markdown("*Градиентные дуги показывают путь от места рождения (красная точка) к месту совершения открытия/работы (золотая точка).*")

# Готовим данные только для тех, у кого есть место работы
map_data = filtered_df[filtered_df['has_moved']].copy()
# Приводим координаты к числовому типу (обязательно для pydeck)
map_data['lat'] = map_data['lat'].astype(float)
map_data['lon'] = map_data['lon'].astype(float)
map_data['work_lat'] = map_data['work_lat'].astype(float)
map_data['work_lon'] = map_data['work_lon'].astype(float)

# Слой 1: Дуги миграции (Полупрозрачные, градиентные)
arc_layer = pdk.Layer(
    "ArcLayer",
    data=map_data,
    get_source_position=["lon", "lat"],
    get_target_position=["work_lon", "work_lat"],
    get_source_color=[255, 75, 75, 120],   # Розово-красный (Рождение)
    get_target_color=[242, 201, 76, 200],  # Золотой (Открытие)
    get_width=2,
    pickable=True
)

# Слой 2: Точки рождения (Небольшие)
birth_layer = pdk.Layer(
    "ScatterplotLayer",
    data=map_data,
    get_position=["lon", "lat"],
    get_color=[255, 75, 75, 180],
    get_radius=30000,
    pickable=False
)

# Слой 3: Точки открытия (Крупные, золотые - имитируем "звездочку")
work_layer = pdk.Layer(
    "ScatterplotLayer",
    data=map_data,
    get_position=["work_lon", "work_lat"],
    get_color=[242, 201, 76, 255],
    get_radius=50000,
    pickable=False
)

# Настройка красивого всплывающего окна (Tooltips) для PyDeck
tooltip = {
    "html": """
    <div style='font-family: sans-serif;'>
        <b style='color: #F2C94C; font-size: 16px;'>{name}</b><br/>
        <b>Категория:</b> {category} ({award_year})<br/>
        <hr style='margin: 5px 0;'/>
        🛫 <b>Родился:</b> {birth_city}, {birth_country}<br/>
        🛬 <b>Работал:</b> {work_city}<br/>
    </div>
    """,
    "style": {"backgroundColor": "#1E1E1E", "color": "white", "border": "1px solid #333", "borderRadius": "8px"}
}

# Отрисовка карты
deck = pdk.Deck(
    layers=[arc_layer, birth_layer, work_layer],
    initial_view_state=pdk.ViewState(latitude=40, longitude=0, zoom=1.5, pitch=45), # Pitch дает 3D-наклон!
    map_style="mapbox://styles/mapbox/dark-v11",
    tooltip=tooltip
)
st.pydeck_chart(deck)

st.write("---")

# --- ВИЗУАЛИЗАЦИЯ 2 и 3: Обычные графики с КРАСИВЫМИ карточками ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("🌍 Статическая карта всех лауреатов")
    fig_map = px.scatter_geo(
        filtered_df, lat='lat', lon='lon', color='category',
        hover_name='name', size_max=10, opacity=0.8, projection="natural earth"
    )
    # КРАСИВАЯ КАРТОЧКА (Hover Template)
    fig_map.update_traces(
        hovertemplate="<b style='font-size:14px'>%{hovertext}</b><br><br>" +
                      "🏅 <b>Категория:</b> %{customdata[0]}<br>" +
                      "🌍 <b>Страна рождения:</b> %{customdata[1]}<br>" +
                      "📅 <b>Год:</b> %{customdata[2]}<br>" +
                      "<extra></extra>", # extra убирает лишний мусор из тултипа
        customdata=filtered_df[['category', 'birth_country', 'award_year']]
    )
    fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor="rgba(0,0,0,0)", geo=dict(bgcolor='rgba(0,0,0,0)'))
    st.plotly_chart(fig_map, use_container_width=True)

with col2:
    st.subheader("📊 Возраст на момент получения")
    fig_age = px.histogram(
        filtered_df, x="award_age", nbins=25, color="category",
        labels={'award_age': 'Возраст', 'count': 'Количество'}
    )
    fig_age.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_age, use_container_width=True)
