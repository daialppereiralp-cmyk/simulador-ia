import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from supabase import create_client, Client
import json
import pandas as pd
import plotly.express as px

try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except:
    GEMINI_API_KEY = "SUA_CHAVE_AQUI"
    SUPABASE_URL = "SUA_URL_AQUI"
    SUPABASE_KEY = "SUA_CHAVE_AQUI"


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def gerar_questoes_ia(tema, qtd):
    """Solicita questões à IA Gemini"""
    prompt = f"""
    Gere {qtd} questões de múltipla escolha sobre '{tema}' para concurso público.
    Retorne APENAS um JSON puro (sem markdown) no formato:
    [
      {{"pergunta": "texto", "opcoes": ["A) ", "B) ", "C) ", "D) "], "resposta": "letra_maiuscula"}}
    ]
    """
    response = model.generate_content(prompt)
    texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
    return json.loads(texto_limpo)

def gerar_pdf(questoes, tema):
    """Cria o arquivo PDF para download"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Simulado: {tema}", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    
    for i, q in enumerate(questoes):
        pdf.ln(10)
        pdf.multi_cell(0, 10, txt=f"{i+1}. {q['pergunta']}")
        for opt in q['opcoes']:
            pdf.cell(0, 8, txt=opt, ln=True)
    return pdf.output(dest='S').encode('latin-1')


st.set_page_config(page_title="AprovaIA - Simulados", layout="wide")

if 'user' not in st.session_state:
    st.title("?? AprovaIA: Simulados com Inteligência")
    tab_log, tab_reg = st.tabs(["Login", "Criar Conta"])
    
    with tab_log:
        e = st.text_input("Email")
        p = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            try:
                res = supabase.auth.sign_in_with_password({"email": e, "password": p})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Login inválido.")

    with tab_reg:
        ne = st.text_input("Novo Email")
        np = st.text_input("Nova Senha", type="password")
        if st.button("Cadastrar"):
            try:
                supabase.auth.sign_up({"email": ne, "password": np})
                st.info("Sucesso! Verifique seu email para confirmar.")
            except: st.error("Erro ao cadastrar.")
    st.stop()

st.sidebar.title(f"?? {st.session_state.user.email}")
menu = st.sidebar.radio("Navegação", ["Criar Simulado", "Meu Progresso", "Sair"])

if menu == "Sair":
    supabase.auth.sign_out()
    del st.session_state.user
    st.rerun()

elif menu == "Criar Simulado":
    st.header("?? Gerador de Provas")
    tema = st.text_input("Qual o assunto da prova?", placeholder="Ex: Direito Constitucional")
    qtd = st.select_slider("Número de questões", options=[5, 10, 15, 20])

    if st.button("Gerar Simulado com IA"):
        with st.spinner("A IA está criando as questões..."):
            try:
                st.session_state.questoes = gerar_questoes_ia(tema, qtd)
                st.session_state.tema_atual = tema
            except Exception as e:
                st.error("Erro ao gerar questões. Tente novamente.")

    if 'questoes' in st.session_state:
        st.divider()
        respostas_usuario = []
        for i, q in enumerate(st.session_state.questoes):
            st.subheader(f"Questão {i+1}")
            st.write(q['pergunta'])
            resp = st.radio("Selecione uma opção:", q['opcoes'], key=f"q_{i}", index=None)
            respostas_usuario.append(resp)
        
        if st.button("Finalizar e Corrigir"):
            acertos = 0
            for i, q in enumerate(st.session_state.questoes):
                if respostas_usuario[i] and respostas_usuario[i][0] == q['resposta']:
                    acertos += 1
                    st.success(f"Q{i+1}: Correta!")
                else:
                    st.error(f"Q{i+1}: Errada. A correta era {q['resposta']}")
            
            nota = (acertos / len(st.session_state.questoes)) * 100
            st.metric("Resultado Final", f"{nota}%", f"{acertos} acertos")
            
            supabase.table("simulados").insert({
                "user_id": st.session_state.user.id,
                "tema": st.session_state.tema_atual,
                "nota": nota,
                "questoes": st.session_state.questoes
            }).execute()

        pdf_data = gerar_pdf(st.session_state.questoes, st.session_state.tema_atual)
        st.download_button("?? Baixar Prova (PDF)", pdf_data, "prova.pdf", "application/pdf")

elif menu == "Meu Progresso":
    st.header("?? Evolução nos Estudos")
    res = supabase.table("simulados").select("*").eq("user_id", st.session_state.user.id).execute()
    
    if res.data:
        df = pd.DataFrame(res.data)
        df['criado_em'] = pd.to_datetime(df['criado_em']).dt.strftime('%d/%m/%Y')
        
        fig = px.line(df, x='criado_em', y='nota', title='Desempenho por Simulado', markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.table(df[['tema', 'nota', 'criado_em']])
    else:

        st.info("Você ainda não fez nenhum simulado.")
