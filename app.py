import streamlit as st
import pandas as pd
from itertools import product
import io

# --- 회사 코드 매핑 데이터 ---
COMPANY_CODE_MAP = {"시디즈": "T01P", "일룸": "T01I", "퍼시스": "T01F", "바로스": "T01B", "FURSYS VN": "T01N"}

st.set_page_config(page_title="PLM 부품 생성 시스템", layout="wide")

st.markdown("""
    <style>
    .stVerticalBlock { gap: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🧱 PLM 일괄 부품 생성 데이터 변환 시스템")

# 파일이 바뀌면 세션 상태를 초기화하기 위한 로직
if 'file_id' not in st.session_state:
    st.session_state.file_id = None
if 'matrix_df' not in st.session_state:
    st.session_state.matrix_df = None
if 'convert_done' not in st.session_state:
    st.session_state.convert_done = False

# --- 1. PLM 입력 양식 업로드 및 다운로드 ---
st.subheader("1. 입력 양식 업로드")
col_up1, col_up2 = st.columns([3, 1])

with col_up2:
    template_data = pd.DataFrame(columns=['시리즈명', '단품명', '단품세부구성', '색상', '회사'])
    template_buf = io.BytesIO()
    with pd.ExcelWriter(template_buf, engine='openpyxl') as writer:
        template_data.to_excel(writer, index=False)
    st.write(" ") 
    st.download_button(
        label="📥 기본 양식 다운로드",
        data=template_buf.getvalue(),
        file_name="기본 입력 양식.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with col_up1:
    uploaded_file = st.file_uploader("기본 입력 양식 파일을 업로드하세요", type="xlsx", label_visibility="collapsed")

if uploaded_file:
    # 새로운 파일이 업로드되면 세션 초기화
    if st.session_state.file_id != uploaded_file.name:
        st.session_state.file_id = uploaded_file.name
        st.session_state.matrix_df = None
        st.session_state.convert_done = False

    df_in = pd.read_excel(uploaded_file)
    
    # [핵심 수정] sorted() 제거: 엑셀에 등장하는 순서 그대로 추출
    all_units = df_in['단품명'].dropna().unique().tolist()
    all_details = df_in['단품세부구성'].dropna().unique().tolist()
    
    # 매트릭스 데이터 초기화 (엑셀 입력 순서 그대로 조합)
    if st.session_state.matrix_df is None:
        rows = [{"단품명": u, "단품세부구성": d, "마감": True, "미싱": True, "재단": True, "벨텍스 재단": False} 
                for u, d in product(all_units, all_details)]
        st.session_state.matrix_df = pd.DataFrame(rows)

    st.divider()
    st.subheader("2. 단품별 세부구성 출력항목 설정")
    st.caption("※ 각 세부 구성별로 생성할 부품 종류를 선택하세요.")

    df_len = len(st.session_state.matrix_df)
    calc_height = (df_len + 1) * 35 + 5

    config_editor = st.data_editor(
        st.session_state.matrix_df,
        hide_index=True,
        use_container_width=True,
        height=calc_height,
        column_config={
            "단품명": st.column_config.TextColumn("단품명", disabled=True),
            "단품세부구성": st.column_config.TextColumn("단품세부구성", disabled=True),
            "마감": st.column_config.CheckboxColumn("마감"),
            "미싱": st.column_config.CheckboxColumn("미싱"),
            "재단": st.column_config.CheckboxColumn("재단"),
            "벨텍스 재단": st.column_config.CheckboxColumn("벨텍스 재단"),
        },
        key="plm_config_matrix"
    )
    st.session_state.matrix_df = config_editor

    # --- 데이터 변환 실행 ---
    if st.button("🚀 PLM 업로드용 데이터 생성 시작", use_container_width=True):
        series_names = df_in['시리즈명'].dropna().unique().tolist()
        all_colors = df_in['색상'].dropna().unique().tolist()
        
        raw_comp = str(df_in['회사'].iloc[0])
        mapped_comp = "UNKNOWN"
        for key, code in COMPANY_CODE_MAP.items():
            if key in raw_comp: mapped_comp = code; break
        
        choice_map = st.session_state.matrix_df.set_index(['단품명', '단품세부구성']).to_dict('index')
        
        final_list = []
        # 엑셀 원본 순서대로 루프 (정렬 절대 금지)
        for s in series_names:
            for u in all_units:
                for d in all_details:
                    opt = choice_map.get((u, d))
                    if not opt: continue
                    
                    for c in all_colors:
                        c_str = str(c)
                        suffix = c_str[:3] if c_str.startswith('L') else c_str[:2]
                        mat = "가죽" if c_str.startswith('L') else "패브릭"
                        
                        base = {"부품유형": "MAT", "단위": "ea", "회사": mapped_comp, "개발구분": "R", "색상코드": c_str}

                        if opt["마감"]:
                            r = base.copy(); r.update({"부품명": f"{s} {u} {d} 마감_{suffix}", "카테고리_대": "WD", "카테고리_중": "WW", "카테고리_소": "WW"})
                            final_list.append(r)
                        if opt["미싱"]:
                            r = base.copy(); r.update({"부품명": f"{s} {u} {d} 미싱_{suffix}", "카테고리_대": "FB", "카테고리_중": "FP", "카테고리_소": "FJ"})
                            final_list.append(r)
                        if opt["재단"]:
                            r = base.copy(); r.update({"부품명": f"{s} {u} {d} {mat} 재단_{suffix}", "카테고리_대": "FB", "카테고리_중": "FP", "카테고리_소": "FJ"})
                            final_list.append(r)
                    
                    if opt["벨텍스 재단"]:
                        final_list.append({
                            "부품명": f"{s} {u} {d} 벨텍스 재단", "부품유형": "MAT", "단위": "ea", "회사": mapped_comp, "개발구분": "R",
                            "카테고리_대": "FB", "카테고리_중": "FP", "카테고리_소": "FJ", "색상코드": "XX"
                        })
        
        st.session_state.final_rows = final_list
        st.session_state.convert_done = True

    # --- 3. 결과 확인 및 다운로드 ---
    if st.session_state.convert_done:
        st.divider()
        st.subheader("3. 결과 확인 및 다운로드")
        df_final = pd.DataFrame(st.session_state.final_rows)
        
        # 그룹화 시에도 sort=False를 사용하여 데이터가 쌓인 순서(원본 순서) 그대로 유지
        g_keys = ['부품명', '부품유형', '단위', '회사', '개발구분', '카테고리_대', '카테고리_중', '카테고리_소']
        df_out = df_final.groupby(g_keys, sort=False)['색상코드'].apply(lambda x: ', '.join(x.unique())).reset_index()
        
        final_view = st.data_editor(df_out[['부품명', '부품유형', '단위', '회사', '개발구분', '카테고리_대', '카테고리_중', '카테고리_소', '색상코드']], use_container_width=True)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            final_view.to_excel(writer, index=False, sheet_name='PLM_UPLOAD')
        st.download_button("✅ PLM 부품 일괄 생성 데이터 다운로드", data=buf.getvalue(), file_name="PLM_PART_DATA_FINAL.xlsx")