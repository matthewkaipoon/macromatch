"""Shared premium-fitness / modern-wellness presentation for MacroMatch."""

import streamlit as st


def inject_theme() -> None:
    """Apply one visual system to all four pages without changing their data logic."""
    st.markdown(
        """
    <style>
      @font-face {
        font-family: 'Manrope';
        src: url('/app/static/Manrope-Variable.ttf') format('truetype');
        font-weight: 200 800;
        font-display: swap;
      }
      :root {
        --mm-canvas: #2B3034;
        --mm-panel: #363D41;
        --mm-raised: #41494D;
        --mm-hover: #495357;
        --mm-border: #586368;
        --mm-text: #F3F6F3;
        --mm-muted: #C1CDCB;
        --mm-blue: #93BEF0;
        --mm-sage: #B5D7C0;
      }
      html, body, .stApp, .stApp p, .stApp h1, .stApp h2,
      .stApp h3, .stApp h4, .stApp label, .stApp input,
      .stApp button, .stApp [data-testid="stMarkdownContainer"],
      .stApp [data-testid="stCaptionContainer"] {
        font-family: 'Manrope', 'Segoe UI Variable', 'Aptos', sans-serif !important;
      }
      .stApp {
        background: var(--mm-canvas);
        color: var(--mm-text);
      }
      .block-container {
        max-width: 1200px;
        padding-top: 1.05rem !important;
        padding-bottom: 3.5rem !important;
      }
      .stApp h1 {
        color: var(--mm-text) !important;
        font-size: clamp(2.1rem, 4vw, 2.9rem) !important;
        letter-spacing: -.055em;
        font-weight: 790 !important;
        padding-top: 0 !important;
        line-height: 1.13;
      }
      .stApp h2, .stApp h3, .stApp h4 {
        color: var(--mm-text) !important;
        letter-spacing: -.035em;
        font-weight: 740;
      }
      .stApp h2 { font-size: 1.5rem; }
      .stApp h3 { font-size: 1.18rem; }
      [data-testid="stCaptionContainer"], .stApp small,
      .stApp [data-testid="stWidgetLabel"] {
        color: var(--mm-muted);
      }
      a { color: var(--mm-blue); }
      a:hover { color: #C2DAF7; }
      hr { border-color: var(--mm-border) !important; opacity: .6; }

      /* Restrained navigation: a single sage indicator, generous touch targets. */
      [data-testid="stSidebar"] {
        width: 13.5rem !important;
        min-width: 13.5rem !important;
        background: #343B3F !important;
        border-right: 1px solid #566166;
      }
      [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        width: 13.5rem !important;
      }
      [data-testid="stSidebarNav"] a {
        border-radius: .42rem;
        margin-bottom: .2rem;
        padding: .68rem .75rem;
        border-left: 3px solid transparent;
      }
      [data-testid="stSidebarNav"] a:hover { background: #444D50; }
      [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: #45564D;
        border-left-color: var(--mm-sage);
      }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: .78rem;
        line-height: 1.5;
        color: var(--mm-muted);
      }

      /* Streamlit's native controls follow the same modest radius and contrast. */
      [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid var(--mm-border) !important;
        border-radius: .58rem !important;
      }
      [data-testid="stButton"] button,
      [data-testid="stPageLink"] a {
        border-radius: .42rem;
        min-height: 2.65rem;
        font-weight: 700;
        transition: background .14s ease, border-color .14s ease;
      }
      [data-testid="stButton"] button[kind="primary"],
      [data-testid="stAppViewContainer"] [data-testid="stButton"] button[kind="primary"] {
        background: #7BADE5;
        color: #202E3B;
        border: 1px solid #A7CDF3;
        box-shadow: none;
      }
      [data-testid="stButton"] button[kind="primary"]:hover {
        background: #ACD2F6;
        border-color: #C4E0FC;
        color: #202E3B;
      }
      [data-testid="stButton"] button[kind="secondary"] {
        background: #434D50;
        color: var(--mm-text);
        border-color: #626F71;
      }
      [data-testid="stButton"] button[kind="secondary"]:hover {
        background: #4D595B;
        border-color: var(--mm-sage);
        color: white;
      }
      [data-testid="stTextInput"] input,
      [data-testid="stNumberInput"] input,
      [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background: #41494D !important;
        border-color: #6D797A !important;
        border-radius: .46rem !important;
        color: var(--mm-text) !important;
      }
      [data-testid="stTextInput"] input:focus,
      [data-testid="stNumberInput"] input:focus {
        border-color: #A8D0F4 !important;
      }
      [data-testid="stPopover"] button {
        border-radius: .42rem;
      }
      [data-testid="stMetric"] {
        background: var(--mm-panel);
        border: 1px solid #536065;
        padding: .65rem .85rem;
        border-radius: .5rem;
      }

      /* Home: generous hierarchy, compact metadata, flat numbered action cards. */
      .mm-lead {
        color: #D4DEDA;
        font-size: 1.03rem;
        line-height: 1.75;
        max-width: 730px;
        margin: .22rem 0 1.55rem;
      }
      .mm-eyebrow {
        font-size: .68rem;
        font-weight: 800;
        letter-spacing: .12em;
        color: var(--mm-sage);
        margin: .5rem 0 .7rem;
      }
      [class*="st-key-mm_home_"] [data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 18.25rem;
        background: #374044;
        border-color: #637074 !important;
        border-top: 2px solid var(--mm-blue) !important;
        padding: .18rem;
      }
      [class*="st-key-mm_home_recommend"] [data-testid="stVerticalBlockBorderWrapper"] {
        border-top-color: var(--mm-sage) !important;
      }
      [class*="st-key-mm_home_compare"] [data-testid="stVerticalBlockBorderWrapper"] {
        border-top-color: #C7D6CE !important;
      }
      .mm-tile-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: .5rem;
        margin: .15rem 0 .95rem;
      }
      .mm-tile-index {
        color: var(--mm-blue);
        font-size: 2.5rem;
        line-height: 1.1;
        font-weight: 760;
        letter-spacing: -.085em;
      }
      [class*="st-key-mm_home_recommend"] .mm-tile-index { color: var(--mm-sage); }
      [class*="st-key-mm_home_compare"] .mm-tile-index { color: #D0E0D6; }
      .mm-tile-kicker {
        color: #B8C7C4;
        font-size: .6rem;
        font-weight: 750;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .mm-tile-title {
        color: var(--mm-text);
        font-size: 1.19rem;
        font-weight: 770;
        letter-spacing: -.035em;
      }
      .mm-tile-desc {
        color: #CBD5D2;
        font-size: .84rem;
        line-height: 1.65;
        min-height: 3.8rem;
        margin: .45rem 0 1.0rem;
      }
      [class*="st-key-mm_home_"] [data-testid="stPageLink"] a {
        width: 100%;
        justify-content: space-between;
        padding: .56rem .75rem;
        background: #45524E;
        border: 1px solid #718B7B;
        color: #F3F9F4;
      }
      [class*="st-key-mm_home_"] [data-testid="stPageLink"] a:hover {
        background: #52695B;
        border-color: #A9D1B8;
      }
      .mm-compact-stat {
        background: #384145;
        border: 1px solid #566369;
        border-radius: .42rem;
        padding: .65rem .82rem;
        min-height: 4.6rem;
      }
      .mm-compact-stat span {
        display: block;
        color: #BAC7C7;
        font-size: .72rem;
        line-height: 1.4;
      }
      .mm-compact-stat strong {
        display: block;
        font-size: 1.23rem;
        color: #EDF4EE;
        font-weight: 790;
        margin-top: .24rem;
      }
      .mm-badge {
        display: inline-block;
        padding: .27rem .62rem;
        font-size: .77rem;
        background: #4A6657;
        color: #E1F1E5;
        border: 1px solid #719A7D;
        border-radius: .32rem;
        margin-bottom: .5rem;
      }

      /* Large selectable goals, clearly distinct active/quiet states. */
      [data-testid="stSegmentedControl"] [role="radiogroup"] {
        display: flex; width: 100%; max-width: 720px;
        background: #40494B;
        border: 1px solid #657274;
        border-radius: .5rem;
        padding: .22rem;
      }
      [data-testid="stSegmentedControl"] [role="radiogroup"] label,
      [data-testid="stSegmentedControl"] [role="radiogroup"] button {
        flex: 1;
        justify-content: center;
        text-align: center;
      }
      [class*="st-key-mm_goal_"] button {
        min-height: 3.45rem;
        font-size: .91rem;
        border-radius: .45rem;
      }
      [class*="st-key-mm_goal_"] button[kind="primary"] {
        background: #557765 !important;
        border-color: #B6DDC2 !important;
        color: #F7FFF8 !important;
      }
      [class*="st-key-mm_goal_"] button[kind="secondary"] {
        background: #414B4E !important;
      }

      /* Each food row has multiple full-size click targets, never a checkbox. */
      [class*="st-key-mm_table_header_"] { padding: .28rem .62rem 0; }
      [class*="st-key-mm_table_header_"] [data-testid="stCaptionContainer"] {
        color: #B5C9C4;
        font-size: .69rem;
        font-weight: 800;
        letter-spacing: .07em;
      }
      [class*="st-key-mm_table_row_"] {
        background: #384145;
        border: 1px solid #516064;
        border-radius: .38rem;
        padding: .12rem .42rem;
        margin-bottom: .14rem;
        transition: background .15s, border-color .15s;
      }
      [class*="st-key-mm_table_row_"]:nth-of-type(even) { background: #3C4549; }
      [class*="st-key-mm_table_row_"]:hover {
        background: #4A5855;
        border-color: #A6CCB3;
      }
      [class*="st-key-mm_table_row_"][class*="_active"] {
        background: #506B5C;
        border-color: #B7E0C4;
      }
      [class*="st-key-mm_table_row_"] [data-testid="stButton"] button {
        background: transparent !important;
        border: 0 !important;
        box-shadow: none !important;
        color: #EEF3F0 !important;
        border-radius: 0 !important;
        text-align: left;
        justify-content: flex-start;
        min-height: 1.95rem;
        padding: .28rem .18rem;
        font-size: .79rem;
        font-weight: 570;
      }
      [class*="st-key-mm_table_row_"] [data-testid="stButton"] button:hover {
        color: #C5E7CD !important;
      }
      [class*="st-key-mm_table_row_"] [data-testid="stButton"] button:focus-visible {
        outline: 2px solid #B5D7C0 !important;
        outline-offset: -2px;
      }
      [class*="st-key-mm_discover_detail"],
      [class*="st-key-mm_primary_detail"],
      [class*="st-key-mm_incomplete_detail"] {
        scroll-margin-top: 5rem;
      }
      [class*="st-key-mm_discover_pagination_"] button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #D1DAD7 !important;
        border-radius: .18rem !important;
        font-size: .81rem !important;
        min-height: 1.4rem !important;
        padding: .12rem .34rem !important;
        line-height: 1.2;
      }
      [class*="st-key-mm_discover_pagination_"] button:hover {
        text-decoration: underline;
        color: #C3E0CB !important;
      }
      [class*="st-key-mm_discover_pagination_"] button:disabled {
        opacity: 1 !important;
        font-weight: 800;
        color: #C3E0CB !important;
        text-decoration: underline;
      }

      /* Comparison cards rise only while the live search menu is in focus. */
      [class*="st-key-mm_compare_card_"]:focus-within {
        position: relative;
        z-index: 10;
      }
      [class*="st-key-mm_compare_card_"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: #394246;
      }
      .mm-readonly-table-wrap {
        overflow-x: auto;
        border: 1px solid #637174;
        border-radius: .47rem;
        margin: .7rem 0 1rem;
      }
      .mm-readonly-table {
        border-collapse: collapse;
        width: 100%;
        font-size: .84rem;
        min-width: 500px;
      }
      .mm-readonly-table th {
        text-align: left;
        background: #485852;
        color: #F0F8F1;
        font-weight: 780;
        font-size: .76rem;
        padding: .82rem .87rem;
        white-space: normal;
        min-width: 145px;
        line-height: 1.4;
        border-bottom: 2px solid #92BA9E;
      }
      .mm-readonly-table th:first-child { min-width: 160px; }
      .mm-readonly-table td {
        padding: .76rem .87rem;
        border-top: 1px solid #526064;
        color: #E7EEEA;
      }
      .mm-readonly-table tr:nth-child(even) { background: #3B4549; }
      .mm-readonly-table tr:nth-child(odd) { background: #363F43; }
      .mm-readonly-table tr:hover { background: #4B5953; }

      @media (max-width: 800px) {
        .block-container { padding-top: .75rem !important; }
        .mm-compact-stat { padding: .5rem; }
        .mm-compact-stat strong { font-size: 1.08rem; }
        [data-testid="stSidebar"] {
          width: 13rem !important;
          min-width: 13rem !important;
        }
        [class*="st-key-mm_table_row_"] [data-testid="stButton"] button {
          font-size: .71rem;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { transition-duration: .01ms !important; }
      }
    </style>
        """,
        unsafe_allow_html=True,
    )
