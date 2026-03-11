import streamlit as st


def load_css(file_name):
    """Load a local CSS file into the Streamlit app."""
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def load_bootstrap():
    """Inject Bootstrap 5 CDN into the Streamlit app."""
    st.markdown(
        """
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background-color: #f8f9fa; }
            .card-header { background-color: #007bff; color: white; }
        </style>
        """,
        unsafe_allow_html=True,
    )
