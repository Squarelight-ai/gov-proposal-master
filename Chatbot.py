from openai import OpenAI
import streamlit as st
import anthropic
import PyPDF2
import io
from pathlib import Path
import os
from dotenv import load_dotenv
import re

# .env 파일 로드
load_dotenv()

st.set_page_config(layout="wide")

def read_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.getvalue()))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def split_by_headers(text):
    # 마크다운 헤더를 기준으로 텍스트 분할
    sections = []
    current_section = ""
    next_section = ""
    
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('#'):
            # 현재 섹션이 있고, 내용이 있는 경우에만 추가
            if current_section and len(current_section.strip().split('\n')) > 1:
                sections.append(current_section.strip())
            elif current_section: # 제목만 있는 경우
                next_section = current_section
            current_section = next_section + line + '\n'
            next_section = ""
        else:
            current_section += line + '\n'
            
    if current_section:
        sections.append(current_section.strip())
        
    # 섹션이 없는 경우 일반 청크로 분할
    if not sections:
        return split_into_chunks(text)
        
    return sections

def split_into_chunks(text, chunk_size=2000):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

with st.sidebar:
    api_provider = st.selectbox("API 제공자", ["Claude", "OpenAI"])
    
    if api_provider == "OpenAI":
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            openai_api_key = st.text_input("OpenAI API 키", key="openai_api_key", type="password")
        else:
            with st.expander("OpenAI API 키", expanded=False):
                st.text_input("사전 정의된 API Key값 입력완료", value=openai_api_key, type="password", disabled=True)
        "[OpenAI API 키 발급받기](https://platform.openai.com/account/api-keys)"
        if openai_api_key:
            try:
                client = OpenAI(api_key=openai_api_key)
                models = client.models.list()
                model_names = [model.id for model in models.data if "gpt" in model.id]
                selected_model = st.selectbox("모델 선택", model_names)
            except:
                st.error("유효하지 않은 OpenAI API 키입니다")
                selected_model = None
    else:
        claude_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not claude_api_key:
            claude_api_key = st.text_input("Claude API 키", key="claude_api_key", type="password")
        else:
            with st.expander("Claude API 키", expanded=False):
                st.text_input("사전 정의된 API Key값 입력완료", value=claude_api_key, type="password", disabled=True)
        "[Claude API 키 발급받기](https://console.anthropic.com/)"
        if claude_api_key:
            try:
                claude = anthropic.Anthropic(api_key=claude_api_key)
                models = claude.models.list()
                model_names = [model.id for model in models.data]
                selected_model = st.selectbox("모델 선택", model_names)
            except:
                st.error("유효하지 않은 Claude API 키입니다")
                selected_model = None

st.title("💼 정부지원사업 사업계획서 마스터")
st.caption("🚀 생성AI 기반 사업계획서 자동 작성 시스템")

# 프롬프트 설정 (기본값 접힌 상태)
with st.expander("프롬프트 설정", expanded=False):
    default_prompt = "당신은 정부지원 사업 사업계획서를 작성하는 숙련된 전문가입니다. 공고와 회사 소개를 통해 적절한 사업 계획서를 충실히 작성해주세요. 마크다운 형식으로 '#', '##', '###' 헤더를 사용하여 구조화된 문서를 작성해주세요."
    custom_prompt = st.text_area("프롬프트 수정", value=default_prompt, height=100)

# PDF 업로드
uploaded_file = st.file_uploader("공고 PDF 파일을 업로드해주세요", type="pdf")

# 회사 정보 입력
company_info = st.text_area("회사 정보를 입력해주세요", height=200)

if "proposal_chunks" not in st.session_state:
    st.session_state.proposal_chunks = []

if uploaded_file and company_info:
    if st.button("사업계획서 생성"):
        with st.spinner("PDF 분석 중..."):
            pdf_text = read_pdf(uploaded_file)
            
        with st.spinner("사업계획서 작성 중..."):
            placeholder = st.empty()
            generated_text = ""
            
            if api_provider == "OpenAI":
                stream = client.chat.completions.create(
                    model=selected_model,
                    messages=[
                        {"role": "system", "content": custom_prompt},
                        {"role": "user", "content": f"공고내용: {pdf_text}\n\n회사정보: {company_info}"}
                    ],
                    stream=True
                )
                
                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        generated_text += chunk.choices[0].delta.content
                        placeholder.markdown(generated_text + "▌")
                
                proposal = generated_text
                
            else:
                message = claude.messages.create(
                    model=selected_model,
                    max_tokens=4000,
                    messages=[
                        {
                            "role": "user",
                            "content": f"{custom_prompt}\n\n공고내용: {pdf_text}\n\n회사정보: {company_info}"
                        }
                    ]
                )
                generated_text = message.content[0].text
                placeholder.markdown(generated_text)
                proposal = generated_text
                
            placeholder.markdown(generated_text)
            st.session_state.proposal_chunks = split_by_headers(proposal)

# 청크별 표시 및 피드백
if st.session_state.proposal_chunks:
    for i, chunk in enumerate(st.session_state.proposal_chunks):
        with st.expander(f"파트 {i+1}", expanded=True):
            st.markdown(chunk)
            feedback = st.text_area(f"파트 {i+1}에 대한 피드백", key=f"feedback_{i}")
            
            if st.button(f"파트 {i+1} 수정", key=f"revise_{i}"):
                with st.spinner("수정 중..."):
                    placeholder = st.empty()
                    generated_text = ""
                    
                    if api_provider == "OpenAI":
                        stream = client.chat.completions.create(
                            model=selected_model,
                            messages=[
                                {"role": "system", "content": custom_prompt},
                                {"role": "user", "content": f"원본 내용:\n{chunk}\n\n피드백:\n{feedback}\n\n이 피드백을 반영하여 내용을 수정해주세요."}
                            ],
                            stream=True
                        )
                        
                        for chunk in stream:
                            if chunk.choices[0].delta.content is not None:
                                generated_text += chunk.choices[0].delta.content
                                placeholder.markdown(generated_text + "▌")
                                
                        revised_chunk = generated_text
                        
                    else:
                        message = claude.messages.create(
                            model=selected_model,
                            max_tokens=4000,
                            messages=[
                                {
                                    "role": "user",
                                    "content": f"{custom_prompt}\n\n원본 내용:\n{chunk}\n\n피드백:\n{feedback}\n\n이 피드백을 반영하여 내용을 수정해주세요."
                                }
                            ]
                        )
                        generated_text = message.content[0].text
                        placeholder.markdown(generated_text)
                        revised_chunk = generated_text
                    
                    placeholder.markdown(generated_text)
                    st.session_state.proposal_chunks[i] = revised_chunk
                    st.rerun()

if st.session_state.proposal_chunks:
    # 전체 다운로드 버튼
    full_proposal = "\n\n".join(st.session_state.proposal_chunks)
    st.download_button(
        "전체 사업계획서 다운로드",
        full_proposal,
        "proposal.md",
        "text/markdown"
    )
