import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Mi Dashboard Fácil y Online")

data = pd.DataFrame({
    'Categoría': ['A', 'B', 'C'],
    'Valor': [10, 23, 17]
})

st.subheader("Gráfico de barras de prueba")
fig, ax = plt.subplots()
ax.bar(data['Categoría'], data['Valor'], color='skyblue')
st.pyplot(fig)

st.success("¡Funciona online! 🚀")import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Mi Dashboard Fácil y Online")

data = pd.DataFrame({
    'Categoría': ['A', 'B', 'C'],
    'Valor': [10, 23, 17]
})

st.subheader("Gráfico de barras de prueba")
fig, ax = plt.subplots()
ax.bar(data['Categoría'], data['Valor'], color='skyblue')
st.pyplot(fig)

st.success("¡Funciona online! 🚀")