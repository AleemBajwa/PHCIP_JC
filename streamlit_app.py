import streamlit as st
import sys
import traceback

def main():
    try:
        from dashboard import main as dashboard_main
        dashboard_main()
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error("Full traceback:")
        st.code(traceback.format_exc())
        
        # List available files
        st.write("Available files in the current directory:")
        import os
        st.write(os.listdir("."))

if __name__ == "__main__":
    main() 