import streamlit as st
import pandas as pd
from itertools import product
import io
import re

# --- [공통 데이터 및 설정] ---
COMPANY_CODE_MAP = {
    "시디즈": "T01P", "일룸": "T01I", "퍼시스": "T01F", 
    "바로스": "T01B", "FURSYS VN": "T01N", "퍼시스베트남": "T01N"
}

st.set_page_config(page_title="PLM/ERP 일괄 등록 시스템", layout="wide")

# CSS: UI 디자인 최적화
st.markdown("""
    <style>
    .stVerticalBlock { gap: 0.8rem; }
    .stButton>button { width: 100%; font-weight: bold; }
    /* 이미지 캡션 스타일 */
    .stImage > div > p { font-size: 13px !important; color: #666; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# GitHub 마스터 파일 로드 (2번 메뉴용)
@st.cache_data
def load_color_master():
    try:
        # GITHUB 저장소에 color_material_master.xlsx 가 있어야 함
        return pd.read_excel("color_material_master.xlsx")
    except:
        return None

color_master_df = load_color_master()

# 사이드바 메뉴 구성
st.sidebar.title("🗂️ 메인 메뉴")
menu = st.sidebar.radio(
    "원하는 작업을 선택하세요:",
    ["1. PLM 일괄 자재 등록", "2. ERP BOM 일괄 등록"]
)

# 세션 상태 초기화
if 'file_id' not in st.session_state: st.session_state.file_id = None
if 'matrix_df' not in st.session_state: st.session_state.matrix_df = None

# ----------------------------------------------------------------
# 메뉴 1. PLM 일괄 자재 등록
# ----------------------------------------------------------------
if menu == "1. PLM 일괄 자재 등록":
    st.title("🧱 PLM 일괄 자재 등록")
    
    st.subheader("1. 입력 양식 업로드")
    
    # [이미지 가이드 표시] 접지 않고 바로 노출
    st.image("plm_upload_example.png", caption="▲ PLM 입력 양식 작성 예시", use_container_width=True)

    col1, col2 = st.columns([3, 1])
    with col2:
        template_data = pd.DataFrame(columns=['시리즈명', '단품명', '단품세부구성', '색상', '회사'])
        template_buf = io.BytesIO()
        with pd.ExcelWriter(template_buf, engine='openpyxl') as writer:
            template_data.to_excel(writer, index=False)
        st.write(" ")
        st.download_button("📥 PLM 양식 다운로드", data=template_buf.getvalue(), file_name="PLM_입력양식.xlsx")
    
    with col1:
        uploaded_file = st.file_uploader("PLM 양식 파일을 업로드하세요", type="xlsx", key="plm_up", label_visibility="collapsed")

    if uploaded_file:
        if st.session_state.file_id != uploaded_file.name:
            st.session_state.file_id = uploaded_file.name
            st.session_state.matrix_df = None

        df_in = pd.read_excel(uploaded_file)
        all_units = df_in['단품명'].dropna().unique().tolist()
        all_details = df_in['단품세부구성'].dropna().unique().tolist()
        
        if st.session_state.matrix_df is None:
            rows = [{"단품명": u, "단품세부구성": d, "마감": True, "미싱": True, "재단": True, "벨텍스 재단": False} 
                    for u, d in product(all_units, all_details)]
            st.session_state.matrix_df = pd.DataFrame(rows)

        st.divider()
        st.subheader("2. 단품별 세부 항목 설정")
        calc_height = (len(st.session_state.matrix_df) + 1) * 35 + 5
        config_editor = st.data_editor(
            st.session_state.matrix_df, hide_index=True, use_container_width=True, 
            height=calc_height, key="plm_matrix",
            column_config={
                "단품명": st.column_config.TextColumn("단품명", disabled=True),
                "단품세부구성": st.column_config.TextColumn("단품세부구성", disabled=True),
            }
        )
        st.session_state.matrix_df = config_editor

        if st.button("🚀 PLM 업로드용 데이터 생성", use_container_width=True):
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
            st.download_button("✅ PLM 업로드용 데이터 다운로드", data=buf.getvalue(), file_name="PLM_UPLOAD_RESULT.xlsx")

# ----------------------------------------------------------------
# 메뉴 2. ERP BOM 일괄 등록
# ----------------------------------------------------------------
elif menu == "2. ERP BOM 일괄 등록":
    st.title("🌲 ERP BOM 일괄 등록")
    st.subheader("1. 입력 양식 업로드")
    
    # [이미지 가이드 표시] 접지 않고 바로 노출
    st.image("bom_upload_example.png", caption="▲ ERP BOM 입력 양식 예시", use_container_width=True)

    col1, col2 = st.columns([3, 1])
    with col2:
        buf = io.BytesIO()
        pd.DataFrame(columns=['자재코드', '자재명', '색상코드']).to_excel(buf, index=False)
        st.write(" ")
        st.download_button("📥 BOM 양식 다운로드", data=buf.getvalue(), file_name="BOM_입력양식.xlsx")
    
    with col1:
        uploaded_file = st.file_uploader("BOM 양식 파일을 업로드하세요", type="xlsx", key="bom_up", label_visibility="collapsed")

    if uploaded_file:
        df_input = pd.read_excel(uploaded_file)
        if not all(col in df_input.columns for col in ['자재코드', '자재명', '색상코드']):
            st.error("❗ 필수 컬럼이 누락되었습니다.")
        else:
            st.divider()
            st.subheader("2. 4단계 계층 구조 분석 결과")
            
            bom_pairs = []
            item_list = df_input[~df_input['자재명'].str.contains("마감|미싱|재단")].copy()
            ma_list = df_input[df_input['자재명'].str.contains("마감")].copy()
            mi_list = df_input[df_input['자재명'].str.contains("미싱")].copy()
            ja_list = df_input[df_input['자재명'].str.contains("재단")].copy()

            def get_clean(name): return re.sub(r'_[^_]+$', '', name).strip()

            # 1단계: 단품 -> 마감
            for _, i in item_list.iterrows():
                base = get_clean(i['자재명'])
                match = ma_list[(ma_list['자재명'].str.contains(base, regex=False)) & (ma_list['색상코드'] == i['색상코드'])]
                for _, m in match.iterrows():
                    bom_pairs.append({"상위자재코드": i['자재코드'], "상위자재명": i['자재명'], "상위색상": i['색상코드'], "하위자재코드": m['자재코드'], "하위자재명": m['자재명'], "하위색상": m['색상코드'], "정량": "1", "실량": "1", "공정": "소파마감", "공정코드": "TSE051"})

            # 2단계: 마감 -> 미싱
            for _, m in ma_list.iterrows():
                base = m['자재명'].replace("마감", "").strip()
                match = mi_list[mi_list['자재명'].apply(lambda x: x.replace("미싱", "").strip()) == base]
                for _, mi in match.iterrows():
                    bom_pairs.append({"상위자재코드": m['자재코드'], "상위자재명": m['자재명'], "상위색상": m['색상코드'], "하위자재코드": mi['자재코드'], "하위자재명": mi['자재명'], "하위색상": mi['색상코드'], "정량": "1", "실량": "1", "공정": "소파마감", "공정코드": "TSE051"})

            # 3단계: 미싱 -> 재단 -> 원자재
            for _, mi in mi_list.iterrows():
                base = mi['자재명'].replace("미싱", "").strip()
                for _, ja in ja_list.iterrows():
                    t = ""
                    if "패브릭 재단" in ja['자재명']: t = "패브릭 재단"
                    elif "가죽 재단" in ja['자재명']: t = "가죽 재단"
                    elif "벨텍스 재단" in ja['자재명']: t = "벨텍스 재단"
                    
                    if t:
                        j_base = ja['자재명'].replace(t, "").strip()
                        p_name = "가죽재단" if t == "가죽 재단" else "패브릭 재단"
                        p_code = "PAN208" if t == "가죽 재단" else "TSE057"

                        if j_base == base or (t == "벨텍스 재단" and j_base == get_clean(base)):
                            bom_pairs.append({"상위자재코드": mi['자재코드'], "상위자재명": mi['자재명'], "상위색상": mi['색상코드'], "하위자재코드": ja['자재코드'], "하위자재명": ja['자재명'], "하위색상": ja['색상코드'], "정량": "1", "실량": "1", "공정": "재봉", "공정코드": "TSE030"})
                            
                            # 최종: 원자재 연결
                            if t == "벨텍스 재단":
                                bom_pairs.append({"상위자재코드": ja['자재코드'], "상위자재명": ja['자재명'], "상위색상": ja['색상코드'], "하위자재코드": "FBRF001187-R000", "하위자재명": "벨텍스(중국)", "하위색상": "XX", "정량": "실소요량 입력", "실량": "실소요량 입력", "공정": p_name, "공정코드": p_code})
                            elif color_master_df is not None:
                                raw_m = color_master_df[color_master_df['색상'].astype(str) == str(ja['색상코드'])]
                                if not raw_m.empty:
                                    bom_pairs.append({"상위자재코드": ja['자재코드'], "상위자재명": ja['자재명'], "상위색상": ja['색상코드'], "하위자재코드": raw_m.iloc[0]['자재코드'], "하위자재명": raw_m.iloc[0]['자재명'], "하위색상": raw_m.iloc[0]['색상'], "정량": "실소요량 입력", "실량": "실소요량 입력", "공정": p_name, "공정코드": p_code})

            if bom_pairs:
                df_bom = pd.DataFrame(bom_pairs).drop_duplicates()
                st.data_editor(df_bom[['상위자재코드', '상위자재명', '상위색상', '하위자재코드', '하위자재명', '하위색상', '정량', '실량', '공정']], use_container_width=True)
                buf = io.BytesIO()
                df_bom[['상위자재코드', '상위자재명', '상위색상', '하위자재코드', '하위자재명', '하위색상', '정량', '실량', '공정코드']].to_excel(buf, index=False)
                st.download_button("✅ BOM 업로드용 데이터 다운로드", data=buf.getvalue(), file_name="BOM_UPLOAD_FINAL.xlsx")
