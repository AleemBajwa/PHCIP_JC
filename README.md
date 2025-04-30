# PHCIP_JC Daily Reporting Dashboard

This is a Streamlit dashboard for PHCIP_JC Daily Reporting.

## Deployment Instructions

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app locally:
```bash
streamlit run streamlit_app.py
```

3. To deploy to Streamlit Cloud:
   - Create a Streamlit account at https://streamlit.io/
   - Connect your GitHub repository
   - Deploy the app through the Streamlit Cloud interface

## File Structure
- `dashboard.py`: Main dashboard code
- `streamlit_app.py`: Streamlit entry point
- `requirements.txt`: Python dependencies
- `.streamlit/config.toml`: Streamlit configuration

## Data Files
- `Saphhire Reporting.xlsx`: Daily reporting data
- `BOP Balances (Eligible to be Shifted to ERP).xlsx`: Legacy data
- `districts.geojson`: Geographic data for mapping 