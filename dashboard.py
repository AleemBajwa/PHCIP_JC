import streamlit as st
import pandas as pd
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import io
import requests
import json
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import geopandas as gpd
import traceback

# Set page configuration
st.set_page_config(
    page_title="PHCIP_JC Daily Reporting",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Always define this
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Determine if we're running in Streamlit Cloud
is_streamlit_cloud = os.environ.get('STREAMLIT_SERVER_RUNNING', 'false').lower() == 'true'

# Use only the filename, since the file is in the same directory as your script
DAILY_REPORT_PATH = "30April439PMwithdrawal_reporting.xlsx"
# LEGACY_RECON_PATH = "30April440PM_Consolidated_BOP_Balances.xlsx"  # Commented out legacy file

# Cache the data loading to improve performance
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    try:
        # Check if daily report file exists
        if not os.path.exists(DAILY_REPORT_PATH):
            st.error(f"Daily report file not found at: {DAILY_REPORT_PATH}")
            st.write("Available files:", os.listdir("."))
            return None

        # Load daily reporting data
        daily_df = pd.read_excel(DAILY_REPORT_PATH)
        
        # Basic data validation
        if 'CNIC' not in daily_df.columns:
            raise ValueError("CNIC column not found in dataset")
        
        # Clean CNIC data
        daily_df['CNIC'] = daily_df['CNIC'].astype(str).str.strip()
        
        return daily_df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.error("Full traceback:")
        st.code(traceback.format_exc())
        return None

def process_data(daily_df):
    try:
        # Convert Transaction Time to datetime with correct format
        daily_df['Transaction Time'] = pd.to_datetime(
            daily_df['Transaction Time'], 
            format='%d-%m-%Y %H:%M:%S', 
            errors='coerce'
        )

        # Get maximum transaction time (dropna in case of conversion errors)
        max_transaction_time = daily_df['Transaction Time'].dropna().max()
        if pd.isnull(max_transaction_time):
            max_transaction_time_str = "Unknown"
        else:
            max_transaction_time_str = max_transaction_time.strftime('%Y-%m-%d')
        
        return daily_df, max_transaction_time_str
    except Exception as e:
        st.error(f"Error processing data: {str(e)}")
        return None, None

def create_visualizations(df):
    # Create visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Transaction distribution by date
        daily_transactions = df.groupby(df['Transaction Time'].dt.date).size().reset_index(name='count')
        fig_transactions = px.line(
            daily_transactions,
            x='Transaction Time',
            y='count',
            title='Daily Transaction Distribution',
            labels={'count': 'Number of Transactions', 'Transaction Time': 'Date'}
        )
        st.plotly_chart(fig_transactions, use_container_width=True)
    
    with col2:
        # Withdrawal amount distribution
        fig_withdrawal = px.histogram(
            df,
            x='Withdrawal Amount',
            title='Withdrawal Amount Distribution',
            labels={'Withdrawal Amount': 'Amount', 'count': 'Frequency'}
        )
        st.plotly_chart(fig_withdrawal, use_container_width=True)

def main():
    # Load data
    daily_df = load_data()
    
    if daily_df is not None:
        # Process data
        processed_df, max_transaction_time_str = process_data(daily_df)
        
        if processed_df is not None:
            # --- SIDEBAR FILTERS (flat, clean, professional) ---
            st.sidebar.markdown("""
                <div style='padding:0 0 10px 0;margin-bottom:8px;'>
                    <span style='font-size:1.1em;font-weight:700;color:#24527a;letter-spacing:0.01em;'>PHCIP_JC Filters</span>
                </div>
            """, unsafe_allow_html=True)

            # Date Range (separate From and To pickers)
            st.sidebar.markdown("""
                <div style='font-size:0.97em;font-weight:600;color:#24527a;margin-bottom:2px;'>📅 Date Range</div>
            """, unsafe_allow_html=True)
            min_date = processed_df['Transaction Time'].min()
            max_date = processed_df['Transaction Time'].max()
            if 'from_date' not in st.session_state:
                st.session_state['from_date'] = min_date
            if 'to_date' not in st.session_state:
                st.session_state['to_date'] = max_date
            from_date = st.sidebar.date_input(
                "From",
                value=st.session_state['from_date'],
                min_value=min_date,
                max_value=max_date,
                key="from_date_input"
            )
            to_date = st.sidebar.date_input(
                "To",
                value=st.session_state['to_date'],
                min_value=min_date,
                max_value=max_date,
                key="to_date_input"
            )
            # Clear Date Filter button
            if st.sidebar.button('Clear Date Filter'):
                st.session_state['from_date'] = min_date
                st.session_state['to_date'] = max_date
                st.rerun()
            else:
                st.session_state['from_date'] = from_date
                st.session_state['to_date'] = to_date
            if from_date > to_date:
                st.sidebar.error("From date must be before To date.")
            st.sidebar.markdown("<hr style='margin:0.5em 0 0.5em 0;border:0;border-top:1px solid #e1e4e8;'>", unsafe_allow_html=True)

            # District
            st.sidebar.markdown("<div style='font-size:0.97em;font-weight:600;color:#24527a;margin-bottom:2px;margin-top:0.5em;'>📍 District</div>", unsafe_allow_html=True)
            district_list = processed_df['District Name'].fillna('Blank').unique().tolist()
            district_options = ['All'] + district_list
            district_filter = st.sidebar.selectbox("   ", district_options, key="district_filter")

            st.sidebar.markdown("<hr style='margin:0.7em 0 0.7em 0;border:0;border-top:1px solid #e1e4e8;'>", unsafe_allow_html=True)

            # Search
            st.sidebar.markdown("<div style='font-size:0.97em;font-weight:600;color:#24527a;margin-bottom:2px;'>🔍 Search by CNIC</div>", unsafe_allow_html=True)
            search_term = st.sidebar.text_input(" ", key="search_term")

            # --- APPLY FILTERS ---
            display_df = processed_df.copy()
            # Date filter (using from_date and to_date)
            display_df = display_df[
                (display_df['Transaction Time'].dt.date >= from_date) &
                (display_df['Transaction Time'].dt.date <= to_date)
            ]
            # District filter
            if district_filter != 'All':
                if district_filter == 'Blank':
                    display_df = display_df[display_df['District Name'].isna()]
                else:
                    display_df = display_df[display_df['District Name'] == district_filter]
            # Search filter
            if search_term:
                display_df = display_df[
                    display_df.astype(str).apply(
                        lambda x: x.str.contains(search_term, case=False, na=False)
                    ).any(axis=1)
                ]

            # --- DASHBOARD TITLE ---
            max_transaction_time = processed_df['Transaction Time'].max()
            max_transaction_time_str = max_transaction_time.strftime('%Y-%m-%d %H:%M:%S') if pd.notnull(max_transaction_time) else "Unknown"
            st.markdown(f"""
                <h1 style='color:#2c3e50; background-color:#eaf6fb; padding: 20px 0 20px 0; border-radius: 10px; text-align:center;'>
                    PHCIP_Saphhire <span style='font-size:0.7em;'>(as of {max_transaction_time_str})</span>
                </h1>
            """, unsafe_allow_html=True)

            # --- SUMMARY STATISTICS (Two Rows) ---
            st.subheader("Summary Statistics")
            color_total = "#3498db"
            icon_total = "📋"

            # First row
            col1, col2, col3 = st.columns(3)
            total_records = len(display_df)
            total_withdrawal = display_df['Withdrawal Amount'].sum()
            unique_records = display_df['CNIC'].nunique()
            
            with col1:
                st.markdown(f"""
                    <div style='background:{color_total};padding:18px 0 10px 0;border-radius:10px;text-align:center;color:white;'>
                        <span style='font-size:2em;'>{icon_total}</span><br>
                        <b>Total Records</b><br>
                        <span style='font-size:2em;font-weight:bold;'>{total_records:,}</span>
                    </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                    <div style='background:{color_total};padding:18px 0 10px 0;border-radius:10px;text-align:center;color:white;'>
                        <span style='font-size:2em;'>{icon_total}</span><br>
                        <b>Total Withdrawal</b><br>
                        <span style='font-size:2em;font-weight:bold;'>{total_withdrawal:,.0f}</span>
                    </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                    <div style='background:{color_total};padding:18px 0 10px 0;border-radius:10px;text-align:center;color:white;'>
                        <span style='font-size:2em;'>{icon_total}</span><br>
                        <b>Unique Records</b><br>
                        <span style='font-size:2em;font-weight:bold;'>{unique_records:,}</span>
                    </div>
                """, unsafe_allow_html=True)

            # --- RED FLAG SECTION ---
            # Count blank districts
            blank_districts_count = display_df['District Name'].isna().sum() if 'District Name' in display_df.columns else 0
            blank_districts_unique = display_df[display_df['District Name'].isna()]['CNIC'].nunique() if 'District Name' in display_df.columns and 'CNIC' in display_df.columns else 0
            # Count missing coordinates
            missing_coords_mask = display_df['Device Latitude'].isna() | display_df['Device Longitude'].isna() if 'Device Latitude' in display_df.columns and 'Device Longitude' in display_df.columns else None
            missing_coords_count = missing_coords_mask.sum() if missing_coords_mask is not None else 0
            missing_coords_unique = display_df[missing_coords_mask]['CNIC'].nunique() if missing_coords_mask is not None and 'CNIC' in display_df.columns else 0
            # Count missing CNICs
            missing_cnic_count = display_df['CNIC'].isna().sum() if 'CNIC' in display_df.columns else 0
            
            red_flag_msgs = []
            if blank_districts_count > 0:
                red_flag_msgs.append(f"<b>{blank_districts_count}</b> record(s) have <b>Blank District</b> (affecting <b>{blank_districts_unique}</b> unique CNICs).")
            if missing_coords_count > 0:
                red_flag_msgs.append(f"<b>{missing_coords_count}</b> record(s) have <b>missing coordinates</b> (affecting <b>{missing_coords_unique}</b> unique CNICs).")
            if missing_cnic_count > 0:
                red_flag_msgs.append(f"<b>{missing_cnic_count}</b> record(s) have <b>missing CNIC</b>.")
            if not red_flag_msgs:
                red_flag_msgs.append("<b>No major data issues detected.</b>")

            st.markdown("""
                <div style='background:#ffebee;border-left:6px solid #c0392b;padding:18px 18px 10px 18px;border-radius:8px;margin:18px 0 18px 0;'>
                    <span style='font-size:1.2em;font-weight:700;color:#c0392b;'>🚩 Red Flag</span><br>
                    <ul style='margin:0.5em 0 0 1.2em;color:#b71c1c;font-size:1.05em;'>
                        <li>""" + "</li><li>".join(red_flag_msgs) + "</li>" + "</ul>"
                + "</div>"
            , unsafe_allow_html=True)

            # --- DAILY WITHDRAWAL TRENDS TABLE ---
            st.markdown("""
                <div style='background: #ffe600; color: #222; font-weight: bold; font-size: 1.3em; text-align: center; border-radius: 4px; padding: 6px 0 2px 0; margin-bottom: 0;'>
                    DAILY WITHDRAWAL TRENDS
                </div>
            """, unsafe_allow_html=True)
            trends_df = processed_df.copy()
            trends_df['Date'] = trends_df['Transaction Time'].dt.strftime('%d-%b')
            daily = trends_df.groupby('Date').agg(
                **{'# of PLWs': ('CNIC', 'nunique'),
                   'Withdrawal Amount': ('Withdrawal Amount', 'sum')}
            ).reset_index()
            daily = daily.sort_values('Date', key=lambda x: pd.to_datetime(x, format='%d-%b'))
            daily['% of Increase'] = daily['Withdrawal Amount'].pct_change().fillna(0).apply(lambda x: f"{x*100:.0f}%" if x != 0 else '-')
            daily['Avg. Wtdr/PLW'] = (daily['Withdrawal Amount'] / daily['# of PLWs']).round(0).astype(int)
            # Format numbers
            daily['Withdrawal Amount'] = daily['Withdrawal Amount'].apply(lambda x: f"{x:,.0f}")
            daily['Avg. Wtdr/PLW'] = daily['Avg. Wtdr/PLW'].apply(lambda x: f"{x:,}")
            # Grand Total row
            grand_total = pd.DataFrame({
                'Date': ['Grand Total'],
                '# of PLWs': [daily['# of PLWs'].astype(int).sum()],
                'Withdrawal Amount': [f"{processed_df['Withdrawal Amount'].sum():,}"],
                '% of Increase': ['-'],
                'Avg. Wtdr/PLW': [f"{int(processed_df['Withdrawal Amount'].sum()/daily['# of PLWs'].astype(int).sum()):,}"]
            })
            daily = pd.concat([daily, grand_total], ignore_index=True)
            # Style table
            def highlight_header(s):
                return ['background-color: #ffe600; color: #222; font-weight: bold; text-align: center;' for _ in s]
            def highlight_grand_total(row):
                if row['Date'] == 'Grand Total':
                    return ['background-color: #b3d7f7; font-weight: bold; color: #222;' for _ in row]
                else:
                    return ['background-color: #ffe600;' for _ in row]
            styled = daily.style.apply(highlight_header, axis=0).apply(highlight_grand_total, axis=1)
            st.markdown(f"<div style='width:100%;'>" + styled.to_html(index=False, escape=False) + "</div>", unsafe_allow_html=True)

            # --- SUMMARY STATS BELOW TABLE ---
            daily_for_avg = daily[~daily['Date'].isin(['18-Apr', 'Grand Total'])].copy()
            highest_plws = daily_for_avg['# of PLWs'].astype(int).max()
            highest_withdrawal = daily_for_avg['Withdrawal Amount'].apply(lambda x: int(x.replace(',', ''))).max()
            avg_plws = int(daily_for_avg['# of PLWs'].astype(int).mean())
            avg_withdrawal = int(daily_for_avg['Withdrawal Amount'].apply(lambda x: int(x.replace(',', ''))).mean())
            st.markdown(f"""
                <div style='font-size:1.1em; margin-top: 0.5em;'>
                <b>*Highest number of PLWs performing withdrawals in a day</b>&nbsp;&nbsp;&nbsp;{highest_plws}<br>
                <b>*Highest withdrawal amount in a single day</b>&nbsp;&nbsp;&nbsp;{highest_withdrawal:,}<br>
                <b>*Average number of PLWs per day coming for withdrawals</b>&nbsp;&nbsp;&nbsp;{avg_plws}<br>
                <b>*Average amount withdrawn per day</b>&nbsp;&nbsp;&nbsp;{avg_withdrawal:,}<br>
                </div>
            """, unsafe_allow_html=True)
            st.markdown("""
                <div style='font-size:1em; margin-top: 0.5em;'><b>Note:</b> April 18 was the pilot test day; therefore, it has not been included in the average calculations. April 21 was the Go Live day.</div>
            """, unsafe_allow_html=True)

            # --- Export Options ---
            st.subheader("Export Options")
            col1, col2 = st.columns(2)
            with col1:
                csv = display_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv,
                    file_name=f"phcip_jc_processed_data_{max_transaction_time_str}.csv",
                    mime="text/csv"
                )
            with col2:
                excel_buffer = io.BytesIO()
                display_df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                st.download_button(
                    label="📥 Download as Excel",
                    data=excel_buffer,
                    file_name=f"phcip_jc_processed_data_{max_transaction_time_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # --- MAP (Pakistan only, focus on Punjab, restrict bounds) ---
            st.subheader("Device Location")
            map_df = display_df.dropna(subset=['Device Latitude', 'Device Longitude'])
            map_df = map_df.copy()
            map_df['Device Latitude'] = map_df['Device Latitude'].astype(float)
            map_df['Device Longitude'] = map_df['Device Longitude'].astype(float)
            if 'District Name' in map_df.columns:
                map_df = map_df.sort_values('District Name')
            # Custom color palette for districts
            district_colors = [
                ('Bright Blue', '#007bff'),
                ('Bright Green', '#28a745'),
                ('Bright Yellow', '#ffc107'),
                ('Bright Purple', '#6610f2'),
                ('Cyan / Aqua', '#17a2b8'),
                ('Lime Green', '#01ff70'),
                ('Sky Blue', '#00c0ff'),
                ('Bright Mint', '#00ffa2'),
                ('Deep Blue', '#0056b3'),
                ('Gold', '#ffd700'),
                ('Violet', '#8a2be2'),
                ('Light Turquoise', '#40e0d0'),
            ]
            # Get unique districts in display order (excluding nulls)
            unique_districts = [d for d in map_df['District Name'].unique() if pd.notnull(d)]
            # Assign colors in order, cycling if more districts than colors
            color_map = {}
            for i, district in enumerate(unique_districts):
                color_map[district] = district_colors[i % len(district_colors)][1]
            fig = px.scatter_mapbox(
                map_df,
                lat='Device Latitude',
                lon='Device Longitude',
                color='District Name' if 'District Name' in map_df.columns else None,
                hover_name='District Name' if 'District Name' in map_df.columns else None,
                hover_data={
                    'CNIC': True,
                    'Device Accuracy': True,
                    'District Name': True if 'District Name' in map_df.columns else False,
                },
                zoom=st.session_state['map_zoom'],
                center=st.session_state['map_center'],
                height=600,
                mapbox_style="carto-positron",
                color_discrete_map=color_map
            )
            # Restrict map bounds (Pakistan only)
            fig.update_layout(
                mapbox_bounds={
                    "west": pakistan_bounds["west"],
                    "east": pakistan_bounds["east"],
                    "south": pakistan_bounds["south"],
                    "north": pakistan_bounds["north"]
                }
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("Failed to load data. Please check the file paths and try again.")

# Add a more textured workspace background to the page (target .stApp and body)
st.markdown(
    '''
    <style>
    .stApp, body {
        background-image: url("https://www.toptal.com/designers/subtlepatterns/patterns/paper_fibers.png"), linear-gradient(135deg, #f5f5dc 0%, #e0cda9 100%);
        background-repeat: repeat;
        background-size: auto;
        background-color: #f5f5dc;
    }
    </style>
    ''',
    unsafe_allow_html=True
)

if __name__ == "__main__":
    # Center and bounds for Punjab, Pakistan
    punjab_center = {"lat": 31.1471, "lon": 75.3412}
    pakistan_bounds = {
        "west": 60.5,   # min longitude (Pakistan's west)
        "east": 77.0,   # max longitude (Pakistan's east)
        "south": 23.5,  # min latitude (Pakistan's south)
        "north": 37.2   # max latitude (Pakistan's north)
    }
    # Ensure map_zoom and map_center are initialized in session state
    if 'map_zoom' not in st.session_state:
        st.session_state['map_zoom'] = 6
    if 'map_center' not in st.session_state:
        st.session_state['map_center'] = {"lat": 31.1471, "lon": 75.3412}
    main() 