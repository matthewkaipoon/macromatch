"""Shared Manrope and graphite/blue styling for the MacroMatch interface."""

import streamlit as st


def inject_theme() -> None:
    st.markdown("""
    <style>
      @font-face {
        font-family: 'Manrope';
        src: url('/app/static/Manrope-Variable.ttf') format('truetype');
        font-weight: 200 800;
        font-style: normal;
        font-display: swap;
      }
      html, body, .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3,
      .stApp h4, .stApp label, .stApp input, .stApp button,
      .stApp [data-testid="stMarkdownContainer"],
      .stApp [data-testid="stCaptionContainer"] {
        font-family: 'Manrope', 'Segoe UI Variable', 'Aptos', sans-serif !important;
      }
      .stApp { background: #111419; color: #F0F3F7; }
      .block-container { padding-top: 1.65rem !important; padding-bottom: 3rem; max-width: 1200px; }
      h1 { color: #88B4FF !important; letter-spacing: -.04em; font-weight: 800 !important; padding-top: 0 !important; }
      h2, h3, h4 { color: #F2F4F6 !important; letter-spacing: -.025em; }
      [data-testid="stSidebar"] { width: 14rem !important; min-width: 14rem !important; background: #181C22 !important; border-right: 1px solid #30363F; }
      [data-testid="stSidebar"] [data-testid="stSidebarContent"] { width: 14rem !important; }
      [data-testid="stSidebarNav"] a { border-radius: .65rem; margin-bottom: .2rem; }
      [data-testid="stSidebarNav"] a:hover { background: #303741; }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size: .8rem; }
      [data-testid="stAppViewContainer"] [data-testid="stButton"] button[kind="primary"] {
        background: #4E82DB; border-color: #6196F2; color: #fff;
      }
      [data-testid="stButton"] button { border-radius: .65rem; min-height: 2.65rem; }
      [data-testid="stVerticalBlockBorderWrapper"] { border-color: #373E47 !important; border-radius: .95rem !important; }
      [data-testid="stMetric"] { background: #242930; padding: .65rem; border-radius: .75rem; }
      .mm-lead { color: #BAC0C8; font-size: 1.04rem; line-height: 1.65; max-width: 760px; }
      .mm-eyebrow { font-size: .7rem; font-weight: 800; letter-spacing: .12em; color: #DBB374; margin: .6rem 0; }
      .mm-tile-index { font-size: 2.4rem; font-weight: 800; line-height: 1.3; margin: .15rem 0 .8rem; color: #A7C8FF; letter-spacing: -.07em; }
      .mm-tile-title { font-size: 1.2rem; font-weight: 800; color: #F4F4F5; }
      .mm-tile-desc { color: #AEB5BF; font-size: .85rem; line-height: 1.5; min-height: 3.8rem; margin: .5rem 0 .9rem; }
      [class*="st-key-mm_home_"] [data-testid="stVerticalBlockBorderWrapper"] { background: #242931; min-height: 17rem; }
      [class*="st-key-mm_home_"] [data-testid="stPageLink"] a { width: 100%; justify-content: center; border: 1px solid #637FB1; border-radius: .65rem; background: #34455E; padding: .65rem; }
      .mm-compact-stat { background: #20252B; border: 1px solid #363D46; border-radius: .75rem; padding: .7rem .85rem; min-height: 5rem; }
      .mm-compact-stat span { display: block; color: #A7AFBB; font-size: .73rem; line-height: 1.35; }
      .mm-compact-stat strong { display: block; font-size: 1.25rem; font-weight: 750; color: #E9EEF4; margin-top: .25rem; }
      .mm-badge { display: inline-block; padding: .27rem .62rem; font-size: .78rem; background: #243D37; color: #A2E4D1; border-radius: 999px; margin-bottom: .5rem; }
      [data-testid="stSegmentedControl"] [role="radiogroup"] { display: flex; width: 100%; max-width: 720px; }
      [data-testid="stSegmentedControl"] [role="radiogroup"] label,
      [data-testid="stSegmentedControl"] [role="radiogroup"] button { flex: 1; justify-content: center; text-align: center; }
      [class*="st-key-mm_goal_"] button { min-height: 3.5rem; font-size: .94rem; }

      /* Every table cell is a borderless action. The unified row provides the hover target. */
      [class*="st-key-mm_table_header_"] { padding: .3rem .7rem 0; }
      [class*="st-key-mm_table_header_"] [data-testid="stCaptionContainer"] { color: #9CA6B3; font-size: .7rem; font-weight: 800; letter-spacing: .07em; }
      [class*="st-key-mm_table_row_"] { background: #22272E; border: 1px solid #373E47; border-radius: .58rem; padding: .1rem .42rem; margin-bottom: .1rem; transition: background .15s, border-color .15s; }
      [class*="st-key-mm_table_row_"]:nth-of-type(even) { background: #262B32; }
      [class*="st-key-mm_table_row_"]:hover { background: #303740; border-color: #68798F; }
      [class*="st-key-mm_table_row_"][class*="_active"] { background: #303D51; border-color: #7AA9FA; }
      [class*="st-key-mm_table_row_"] [data-testid="stButton"] button {
        background: transparent !important; border: 0 !important; box-shadow: none !important;
        color: #E7EBF0 !important; border-radius: 0 !important; text-align: left;
        justify-content: flex-start; min-height: 1.85rem; padding: .28rem .18rem;
        font-size: .78rem; font-weight: 550;
      }
      [class*="st-key-mm_table_row_"] [data-testid="stButton"] button:hover { color: #A7C8FF !important; }
      [class*="st-key-mm_table_row_"] [data-testid="stButton"] button:focus-visible { outline: 2px solid #8FB8FF !important; outline-offset: -2px; }
      [class*="st-key-mm_discover_detail"], [class*="st-key-mm_primary_detail"],
      [class*="st-key-mm_incomplete_detail"] { scroll-margin-top: 5rem; }

      /* Text-like pagination, compact and centred below the rows. */
      [class*="st-key-mm_discover_pagination_"] button {
        background: transparent !important; border: none !important; box-shadow: none !important;
        color: #C8D0DB !important; border-radius: .2rem !important;
        font-size: .83rem !important; min-height: 1.4rem !important;
        padding: .12rem .38rem !important; line-height: 1.2;
      }
      [class*="st-key-mm_discover_pagination_"] button:hover { text-decoration: underline; color: #8FB8FF !important; }
      [class*="st-key-mm_discover_pagination_"] button:disabled { opacity: 1 !important; font-weight: 800; color: #8FB8FF !important; text-decoration: underline; }

      /* Lift the focused compare card above its neighbors while the menu is open. */
      [class*="st-key-mm_compare_card_"]:focus-within { position: relative; z-index: 10; }
      [class*="st-key-mm_compare_card_"] [data-testid="stVerticalBlockBorderWrapper"] { background: #20252B; }
      .mm-readonly-table-wrap { overflow-x: auto; border: 1px solid #3A4149; border-radius: .75rem; margin: .7rem 0 1rem; }
      .mm-readonly-table { border-collapse: collapse; width: 100%; font-size: .84rem; min-width: 500px; }
      .mm-readonly-table th { text-align: left; background: #30353D; color: #D8E5F8; font-weight: 800; font-size: .76rem; padding: .78rem .85rem; white-space: normal; min-width: 145px; line-height: 1.4; }
      .mm-readonly-table th:first-child { min-width: 160px; }
      .mm-readonly-table td { padding: .7rem .85rem; border-top: 1px solid #363C44; color: #DCE1E8; }
      .mm-readonly-table tr:nth-child(even) { background: #252A30; }
      .mm-readonly-table tr:nth-child(odd) { background: #1E2329; }
      .mm-readonly-table tr:hover { background: #333B44; }

      @media (max-width: 800px) {
        .block-container { padding-top: 1.1rem !important; }
        .mm-compact-stat { padding: .5rem; }
        .mm-compact-stat strong { font-size: 1.07rem; }
        [data-testid="stSidebar"] { width: 13rem !important; min-width: 13rem !important; }
        [class*="st-key-mm_table_row_"] [data-testid="stButton"] button { font-size: .71rem; }
      }
    </style>
    """, unsafe_allow_html=True)
