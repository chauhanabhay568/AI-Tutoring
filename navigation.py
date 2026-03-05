import streamlit as st
from time import sleep


def make_sidebar():
    with st.sidebar:
        if st.session_state.get("logged_in", False):

            st.title("Pre Feedback")
            st.page_link("pages/pre_survey.py", label="Traditional Teaching Survey")
            st.markdown("<hr>", unsafe_allow_html=True)

            st.title("Service Menu")
            st.page_link("pages/topic_help.py", label="Topic Help",  icon="🔒")
            st.page_link("pages/quiz_help.py",  label="Quiz Help",   icon="🕵️")
            st.markdown("<hr>", unsafe_allow_html=True)

            st.title("Post Feedback")
            st.page_link("pages/post_survey.py", label="AI Teaching Survey")
            st.markdown("<hr>", unsafe_allow_html=True)

            st.page_link("pages/my_account.py", label="My Account", icon="📊")
            st.write("")

            if st.button("Log out"):
                _logout()

        elif not st.session_state.get("on_main_page", False):
            st.switch_page("main.py")


def _logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
