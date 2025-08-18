# ui.py
import streamlit as st

def inject_css():
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    .stApp {background: linear-gradient(180deg, #fff 0%, #fafbfd 100%);}

    h1, .stMarkdown h1 {font-size: 1.9rem; margin-bottom: .3rem;}
    h2, .stMarkdown h2 {font-size: 1.3rem; margin-top: 0.8rem; margin-bottom: .2rem;}
    h3, .stMarkdown h3 {font-size: 1.05rem;}

    .card {
        border-radius: 16px;
        border: 1px solid #E5E7EB;
        background: #FFFFFF;
        box-shadow: 0 4px 16px rgba(15,23,42,0.04);
        padding: 16px 18px;
        height: 100%;
    }
    .card h3 { margin: 0 0 6px 0; font-size: 1.05rem;}
    .muted { color: #6B7280; font-size: 0.92rem; }

    section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
    .side-section-title {
        font-weight: 700; font-size: .9rem; letter-spacing:.02em; margin: 6px 0 2px 0;
        text-transform: uppercase; color: #0F172A; opacity: .7;
    }

    .js-plotly-plot {margin-bottom: 26px;}
    </style>
    """, unsafe_allow_html=True)

def card(title: str, body_md: str, button_label: str | None = None, page_path: str | None = None, icon: str = "➡️"):
    st.markdown(f"""
    <div class="card">
      <h3>{title}</h3>
      <div class="muted">{body_md}</div>
    </div>
    """, unsafe_allow_html=True)
    if button_label and page_path:
        st.page_link(page_path, label=button_label, icon=icon)

def kpi(label: str, value: str, help: str | None = None):
    st.markdown(f"""
    <div class="card" style="padding:12px">
      <div class="muted">{label}</div>
      <div style="font-size:1.35rem; font-weight:700; margin-top:2px">{value}</div>
    </div>
    """, unsafe_allow_html=True)
    if help: st.caption(help)
