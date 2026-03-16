import streamlit as st
import pandas as pd
import numpy as np
from textblob import TextBlob
from datetime import datetime
import sqlite3
import json
import plotly.express as px
import bcrypt

# --- DATABASE SETUP ---
def init_database():
    conn = sqlite3.connect('humanity_platform.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT NOT NULL,
            sentiment_score REAL,
            mood_score INTEGER,
            stress_level INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    return conn

# --- AUTH SYSTEM ---
class AuthSystem:
    def __init__(self, conn):
        self.conn = conn

    def hash_password(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    def verify_password(self, password, hashed):
        return bcrypt.checkpw(password.encode('utf-8'), hashed)

    def register_user(self, username, email, password):
        cursor = self.conn.cursor()
        password_hash = self.hash_password(password)
        try:
            cursor.execute('''
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
            ''', (username, email, password_hash))
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def login_user(self, username, password):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        if result and self.verify_password(password, result[1]):
            return {'id': result[0], 'username': username}
        return None

# --- AI ANALYSIS ---
class AIAnalyzer:
    def analyze_sentiment(self, text):
        blob = TextBlob(text)
        return blob.sentiment.polarity

    def assess_risk(self, mood, stress):
        if mood <= 3 or stress >= 8:
            return 'high'
        elif mood <= 5 or stress >= 6:
            return 'moderate'
        else:
            return 'low'

# --- STREAMLIT APP ---
st.set_page_config(page_title="Humanity Platform", layout="wide")

# Initialize systems
if 'db_conn' not in st.session_state:
    st.session_state.db_conn = init_database()
if 'auth_system' not in st.session_state:
    st.session_state.auth_system = AuthSystem(st.session_state.db_conn)
if 'ai_analyzer' not in st.session_state:
    st.session_state.ai_analyzer = AIAnalyzer()

# --- AUTH PAGE ---
def show_auth_page():
    st.title("🌐 Humanity Platform - Login/Register")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            user = st.session_state.auth_system.login_user(username, password)
            if user:
                st.session_state.user = user
                st.success("Logged in successfully!")
            else:
                st.error("Invalid credentials")

    with tab2:
        new_username = st.text_input("Choose Username", key="reg_user")
        new_email = st.text_input("Email", key="reg_email")
        new_password = st.text_input("Choose Password", type="password", key="reg_pass")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_pass_confirm")
        if st.button("Register"):
            if new_password != confirm_password:
                st.error("Passwords don't match")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters")
            else:
                user_id = st.session_state.auth_system.register_user(new_username, new_email, new_password)
                if user_id:
                    st.success("Account created! Please log in.")
                else:
                    st.error("Username or email already exists")

# --- MAIN APP PAGE ---
def show_main_app():
    st.sidebar.write(f"Welcome, {st.session_state.user['username']}!")
    if st.sidebar.button("Logout"):
        st.session_state.pop('user')
        st.experimental_rerun()

    tab1, tab2 = st.tabs(["🧠 Wellbeing", "📊 Mood Analytics"])

    # --- Wellbeing Check-In ---
    with tab1:
        st.header("Daily Mental Health Check-In")
        mood = st.slider("Mood (1-10)", 1, 10, 5)
        stress = st.slider("Stress Level (1-10)", 1, 10, 5)
        journal = st.text_area("Journal Entry", height=150)
        if st.button("Submit Check-In"):
            sentiment = st.session_state.ai_analyzer.analyze_sentiment(journal)
            risk = st.session_state.ai_analyzer.assess_risk(mood, stress)
            cursor = st.session_state.db_conn.cursor()
            cursor.execute('''
                INSERT INTO journal_entries (user_id, content, sentiment_score, mood_score, stress_level)
                VALUES (?, ?, ?, ?, ?)
            ''', (st.session_state.user['id'], journal, sentiment, mood, stress))
            st.session_state.db_conn.commit()
            st.success(f"Check-in saved! Risk level: {risk.upper()}")

    # --- Mood Analytics ---
    with tab2:
        st.header("Recent Mood Trend")
        cursor = st.session_state.db_conn.cursor()
        cursor.execute('''
            SELECT mood_score, created_at FROM journal_entries
            WHERE user_id = ? ORDER BY created_at DESC LIMIT 14
        ''', (st.session_state.user['id'],))
        data = cursor.fetchall()
        if data:
            df = pd.DataFrame(data, columns=['mood', 'date'])
            df['date'] = pd.to_datetime(df['date'])
            fig = px.line(df, x='date', y='mood', title="Last 14 Days Mood", range_y=[1, 10])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No entries yet. Submit check-ins to see trends!")

# --- APP ROUTE ---
if 'user' not in st.session_state:
    show_auth_page()
else:
    show_main_app()