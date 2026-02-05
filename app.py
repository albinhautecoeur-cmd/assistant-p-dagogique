# ======================
# LOGIN (1 clic)
# ======================
if not st.session_state.connected:
    st.title("🔐 Connexion élève")

    with st.form("login_form"):
        username = st.text_input("Identifiant")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Connexion")
        if submitted:
            active_users = clean_expired_sessions()
            if username in USERS and USERS[username] == password:
                if username in active_users:
                    st.error("❌ Ce compte est déjà connecté sur un autre appareil.")
                else:
                    active_users[username] = time.time()
                    save_active_users(active_users)
                    st.session_state.connected = True
                    st.session_state.username = username
                    st.success("Connexion réussie")
            else:
                st.error("Identifiant ou mot de passe incorrect")
    st.stop()


# ======================
# DECONNEXION (1 clic)
# ======================
if st.button("🚪 Déconnexion"):
    active_users = load_active_users()
    if st.session_state.username in active_users:
        del active_users[st.session_state.username]
        save_active_users(active_users)
    st.session_state.connected = False
    st.session_state.username = None
    st.session_state.document_content = ""
    st.session_state.document_images = []
    st.session_state.chat_history = []
    st.experimental_rerun()  # remplace st.stop() pour un seul clic
