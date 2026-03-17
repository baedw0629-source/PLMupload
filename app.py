import streamlit as st
import pandas as pd
from itertools import product
import io

# --- 공통 설정 및 데이터 ---
COMPANY_CODE_MAP = {"시디즈": "T01P", "일룸": "T01I", "퍼시스": "T01F", "바로스": "T01B", "FURSYS VN": "T01N"}

st.set_page_config(page_title="PLM/ERP 일괄 등록 시스템", layout="wide")

# 사이드바 메뉴 구성
st.sidebar.title("🗂️ 메인 메뉴")
menu = st.sidebar.radio(
    "원하는 작업을 선택하세요:",
    ["1. PLM 일괄 부품 생성", "2. ERP BOM 일괄 등록"]
)

# 세션 상태 초기화 (메뉴가 바뀌면 초기화될 수 있도록)
if 'matrix_df' not in st.session_state: st.session_state.matrix_df = None
if 'file_id' not in st.session_state: st.session_state.file_id = None

# --- [공통 함수: 양식 생성 및 업로드] ---
def upload_section(title):
    st.subheader(f"1. {title} 양식 업로드")
    col1, col2 = st.columns([3, 1])
    with col2:
        template_data = pd.DataFrame(columns=['시리즈명', '단품명', '단품세부구성', '색상', '회사'])
        template_buf = io.BytesIO()
        with pd.ExcelWriter(template_buf, engine='openpyxl') as writer:
            template_data.to_excel(writer, index=False)
        st.write(" ")
        st.download_button(label="📥 기본 양식 다운로드", data=template_buf.getvalue(), file_name="입력_양식.xlsx")
    with col1:
        return st.file_uploader("양식 파일을 업로드하세요", type="xlsx", label_visibility="collapsed")

# --- 1번 메뉴: PLM 일괄 부품 생성 ---
if menu == "1. PLM 일괄 부품 생성":
    st.title("🧱 PLM 일괄 부품 생성")
    uploaded_file = upload_section("PLM 부품 생성")

    if uploaded_file:
        df_in = pd.read_excel(uploaded_file)
        all_units = df_in['단품명'].dropna().unique().tolist()
        all_details = df_in['단품세부구성'].dropna().unique().tolist()
        
        if st.session_state.matrix_df is None:
            rows = [{"단품명": u, "단품세부구성": d, "마감": True, "미싱": True, "재단": True, "벨텍스 재단": False} 
                    for u, d in product(all_units, all_details)]
            st.session_state.matrix_df = pd.DataFrame(rows)

        st.divider()
        st.subheader("2. 단품별 세부구성 출력항목 설정")
        calc_height = (len(st.session_state.matrix_df) + 1) * 35 + 5
        config_editor = st.data_editor(st.session_state.matrix_df, hide_index=True, use_container_width=True, height=calc_height, key="plm_editor")
        st.session_state.matrix_df = config_editor

        if st.button("🚀 PLM 업로드 데이터 생성", use_container_width=True):
            series_names = df_in['시리즈명'].dropna().unique().tolist()
            all_colors = df_in['색상'].dropna().unique().tolist()
            raw_comp = str(df_in['회사'].iloc[0])
            mapped_comp = next((code for key, code in COMPANY_CODE_MAP.items() if key in raw_comp), "UNKNOWN")
            choice_map = st.session_state.matrix_df.set_index(['단품명', '단품세부구성']).to_dict('index')
            
            final_list = []
            for s, u, d in product(series_names, all_units, all_details):
                opt = choice_map.get((u, d))
                if not opt: continue
                for c in all_colors:
                    c_str = str(c); suffix = c_str[:3] if c_str.startswith('L') else c_str[:2]
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
                    final_list.append({"부품명": f"{s} {u} {d} 벨텍스 재단", "부품유형": "MAT", "단위": "ea", "회사": mapped_comp, "개발구분": "R", "카테고리_대": "FB", "카테고리_중": "FP", "카테고리_소": "FJ", "색상코드": "XX"})
            
            st.divider()
            df_final = pd.DataFrame(final_list)
            g_keys = ['부품명', '부품유형', '단위', '회사', '개발구분', '카테고리_대', '카테고리_중', '카테고리_소']
            df_out = df_final.groupby(g_keys, sort=False)['색상코드'].apply(lambda x: ', '.join(x.unique())).reset_index()
            st.data_editor(df_out, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_out.to_excel(writer, index=False)
            st.download_button("✅ PLM 부품 리스트 다운로드", data=buf.getvalue(), file_name="PLM_부품리스트.xlsx")

# --- 2번 메뉴: ERP BOM 일괄 등록 ---
elif menu == "2. ERP BOM 일괄 등록":
    st.title("🌲 ERP BOM 일괄 등록 데이터 생성")
    uploaded_file = upload_section("ERP BOM 등록")

    if uploaded_file:
        df_in = pd.read_excel(uploaded_file)
        all_units = df_in['단품명'].dropna().unique().tolist()
        all_details = df_in['단품세부구성'].dropna().unique().tolist()
        
        if st.session_state.matrix_df is None:
            rows = [{"단품명": u, "단품세부구성": d, "마감": True, "미싱": True, "재단": True, "벨텍스 재단": False} 
                    for u, d in product(all_units, all_details)]
            st.session_state.matrix_df = pd.DataFrame(rows)

        st.divider()
        st.subheader("2. 단품별 세부구성 구조 설정 (BOM 연결 대상 선택)")
        calc_height = (len(st.session_state.matrix_df) + 1) * 35 + 5
        config_editor = st.data_editor(st.session_state.matrix_df, hide_index=True, use_container_width=True, height=calc_height, key="bom_editor")
        st.session_state.matrix_df = config_editor

        if st.button("🚀 BOM 구조 데이터 생성", use_container_width=True):
            series_names = df_in['시리즈명'].dropna().unique().tolist()
            all_colors = df_in['색상'].dropna().unique().tolist()
            choice_map = st.session_state.matrix_df.set_index(['단품명', '단품세부구성']).to_dict('index')
            
            struct_list = []
            for s, u, d in product(series_names, all_units, all_details):
                opt = choice_map.get((u, d))
                if not opt: continue
                for c in all_colors:
                    c_str = str(c); suffix = c_str[:3] if c_str.startswith('L') else c_str[:2]
                    mat = "가죽" if c_str.startswith('L') else "패브릭"
                    
                    ma = f"{s} {u} {d} 마감_{suffix}"
                    mi = f"{s} {u} {d} 미싱_{suffix}"
                    ja = f"{s} {u} {d} {mat} 재단_{suffix}"
                    vt = f"{s} {u} {d} 벨텍스 재단"

                    if opt["마감"] and opt["미싱"]: struct_list.append({"상위부품": ma, "하위부품": mi})
                    if opt["미싱"] and opt["재단"]: struct_list.append({"상위부품": mi, "하위부품": ja})
                    if opt["미싱"] and opt["벨텍스 재단"]: struct_list.append({"상위부품": mi, "하위부품": vt})

            st.divider()
            df_struct = pd.DataFrame(struct_list).drop_duplicates()
            st.data_editor(df_struct, use_container_width=True)
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_struct.to_excel(writer, index=False)
            st.download_button("✅ ERP BOM 구조 다운로드", data=buf.getvalue(), file_name="ERP_BOM_구조.xlsx")
