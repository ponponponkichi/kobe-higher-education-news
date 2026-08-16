"""高等教育ニュースのStreamlit閲覧画面。"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from news_app.presentation import is_new_article
from news_app.public_feed import read_public_feed
from news_app.taxonomy import SUBJECT_TABS, THEME_ALL, THEME_TABS


st.set_page_config(
    page_title="高等教育ニュースポータル",
    page_icon="📰",
    layout="wide",
)

PAYWALL_LABELS = {
    "free": "無料と推定",
    "likely_paid": "有料の可能性",
    "unknown": "無料・有料不明",
}

TAB_PRESENTATION = [
    ("🔴", "#d50000", "#ffffff", SUBJECT_TABS[0]),
    ("🟠", "#ef6c00", "#ffffff", SUBJECT_TABS[1]),
    ("🟡", "#ffd600", "#202020", SUBJECT_TABS[2]),
    ("🔵", "#0066cc", "#ffffff", SUBJECT_TABS[3]),
]
SUBJECT_SUMMARY_ROWS = [
    ("#d50000", "#ffffff", SUBJECT_TABS[0], SUBJECT_TABS[0]),
    ("#ef6c00", "#ffffff", SUBJECT_TABS[1], SUBJECT_TABS[1]),
    ("#ffd600", "#202020", SUBJECT_TABS[2], SUBJECT_TABS[2]),
    ("#0066cc", "#ffffff", SUBJECT_TABS[3], SUBJECT_TABS[3]),
    ("#7b1fa2", "#ffffff", "すべて", None),
]
DEFAULT_SUBJECT_FILTER = SUBJECT_TABS[0]
SITE_URL = os.getenv("NEWS_SITE_URL", "https://kobe-higher-education-news.streamlit.app")

SUBJECT_SUMMARY_STYLE = """
<style>
h1 {
    text-align: center;
}
.portal-update-caption {
    text-align: center;
    font-size: 1rem;
    opacity: 0.75;
    margin-top: -0.6rem;
    margin-bottom: 1rem;
}
.subject-summary-number {
    text-align: center;
    font-size: 1.08rem;
    font-weight: 750;
    padding-top: 0.45rem;
}
.subject-summary-number small {
    font-size: 0.78rem;
    font-weight: 550;
    margin-left: 0.18rem;
}
div[data-testid="stExpander"] details summary p {
    color: #ff2b2b !important;
    font-weight: 750;
}
[class*="st-key-subject_filter_"] button {
    min-height: 2.7rem;
    border: 2px solid rgba(0, 0, 0, 0.28);
    border-radius: 0.55rem;
    font-weight: 750;
    color: #ffffff !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
}
[class*="st-key-subject_filter_"] button p { color: inherit !important; }
.st-key-subject_filter_0_idle button, .st-key-subject_filter_0_selected button { background: #d50000; }
.st-key-subject_filter_1_idle button, .st-key-subject_filter_1_selected button { background: #ef6c00; }
.st-key-subject_filter_2_idle button, .st-key-subject_filter_2_selected button { background: #ffd600; color: #202020 !important; }
.st-key-subject_filter_3_idle button, .st-key-subject_filter_3_selected button { background: #0066cc; }
.st-key-subject_filter_4_idle button, .st-key-subject_filter_4_selected button { background: #7b1fa2; }
[class*="st-key-subject_filter_"][class*="_idle"] button {
    opacity: 0.52;
    filter: saturate(0.72);
}
[class*="st-key-subject_filter_"][class*="_selected"] button {
    opacity: 1;
    filter: none;
    box-shadow:
        0 0 0 3px #ffffff,
        0 0 0 6px #242424,
        0 4px 0.7rem rgba(0, 0, 0, 0.28);
}
</style>
"""
st.markdown(SUBJECT_SUMMARY_STYLE, unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_articles() -> tuple[pd.DataFrame, str]:
    """収集処理を行わず、公表用JSONだけを読み込む。"""
    payload = read_public_feed()
    frame = pd.DataFrame(payload.get("articles", []))
    if not frame.empty:
        frame["display_date"] = pd.to_datetime(
            frame["published_at"].fillna(frame["first_seen_at"]),
            errors="coerce",
            utc=True,
        ).dt.tz_convert("Asia/Tokyo")
        frame["theme_list"] = frame["themes"].apply(
            lambda value: value.split("｜") if value else []
        )
    return frame, payload.get("generated_at", "")


def format_date(value) -> str:
    if pd.isna(value):
        return "日付不明"
    return value.strftime("%Y年%m月%d日 %H:%M")


def current_new_articles(frame: pd.DataFrame) -> pd.DataFrame:
    """無料・関連ありの記事から、現在NEW表示中の記事を返す。"""
    if frame.empty:
        return frame.copy()
    base = frame[(frame["paywall_status"] == "free") & (frame["is_relevant"] == 1)].copy()
    return base[base["display_date"].apply(is_new_article)].sort_values(
        ["subject_category", "display_date"], ascending=[True, False]
    )


def build_digest_text(digest: pd.DataFrame) -> str:
    """メール下書きにも利用できる、分野別NEW概要のテキストを作る。"""
    lines = [
        f"高等教育ニュース NEW概要（{pd.Timestamp.now(tz='Asia/Tokyo'):%Y年%m月%d日}）",
        "",
    ]
    for subject in SUBJECT_TABS:
        group = digest[digest["subject_category"] == subject]
        lines.append(f"【{subject}】{len(group)}件")
        if group.empty:
            lines.append("・該当なし")
        else:
            for row in group.itertuples():
                lines.extend((f"・{row.title}", f"  {row.url}"))
        lines.append("")
    lines.extend(("ニュースサイト", SITE_URL))
    return "\n".join(lines)


def render_new_digest(frame: pd.DataFrame) -> None:
    """4つの主語別にNEWタイトルを折りたたみ表示する。"""
    digest = current_new_articles(frame)

    with st.expander(f"公開3日以内のNEWタイトル一覧を開く（{len(digest)}件）"):
        for icon, _, _, subject in TAB_PRESENTATION:
            group = digest[digest["subject_category"] == subject]
            st.markdown(f"#### {icon} {subject}（{len(group)}件）")
            if group.empty:
                st.caption("該当するNEW記事はありません。")
            else:
                for row in group.itertuples():
                    safe_title = row.title.replace("[", "\\[").replace("]", "\\]")
                    st.markdown(f"- [{safe_title}]({row.url})")

        st.divider()
        st.markdown(f"**ニュースサイトURL：** {SITE_URL}")
        st.download_button(
            "NEW概要をテキストで保存",
            data=build_digest_text(digest),
            file_name=f"higher_education_news_{pd.Timestamp.now():%Y%m%d}.txt",
            mime="text/plain",
        )
        st.caption(
            "画面では公開3日以内の記事を表示します。日次メールでは重複を避けるため、"
            "前回配信後に初めて収集した記事だけを使う予定です。"
        )


def render_subject_summary(frame: pd.DataFrame) -> str | None:
    """主語別の件数を一覧表示し、選択された主語を返す。"""
    valid_labels = {label for _, _, label, _ in SUBJECT_SUMMARY_ROWS}
    selected_label = st.session_state.get("selected_subject_filter", DEFAULT_SUBJECT_FILTER)
    if selected_label not in valid_labels:
        selected_label = DEFAULT_SUBJECT_FILTER
        st.session_state["selected_subject_filter"] = selected_label

    st.markdown("### ②ニュースの主語を選択")
    header = st.columns([4.2, 1.2, 1.9, 1.2])
    header[0].markdown("**主語（クリックして絞り込み）**")
    header[1].markdown("**記事**")
    header[2].markdown("**うち、公開3日以内**")
    header[3].markdown("**媒体数**")

    selected_subject = None
    for index, (_, _, label, subject) in enumerate(SUBJECT_SUMMARY_ROWS):
        view = frame if subject is None else frame[frame["subject_category"] == subject]
        new_count = int(view["display_date"].apply(is_new_article).sum()) if not view.empty else 0
        source_count = int(view["source_name"].nunique()) if not view.empty else 0
        is_selected = label == selected_label

        with st.container(key=f"subject_summary_row_{index}", border=True):
            columns = st.columns([4.2, 1.2, 1.9, 1.2], vertical_alignment="center")
            button_key = f"subject_filter_{index}_{'selected' if is_selected else 'idle'}"
            if columns[0].button(
                f"{'✓ ' if is_selected else ''}{label}",
                key=button_key,
                use_container_width=True,
            ):
                st.session_state["selected_subject_filter"] = label
                st.rerun()
            columns[1].markdown(
                f'<div class="subject-summary-number">{len(view):,}<small>件</small></div>',
                unsafe_allow_html=True,
            )
            columns[2].markdown(
                f'<div class="subject-summary-number">{new_count:,}<small>件</small></div>',
                unsafe_allow_html=True,
            )
            columns[3].markdown(
                f'<div class="subject-summary-number">{source_count:,}<small>媒体</small></div>',
                unsafe_allow_html=True,
            )

        if is_selected:
            selected_subject = subject

    return selected_subject


def render_article_list(view: pd.DataFrame) -> None:
    """選択中の主語に該当する記事カードを表示する。"""
    st.divider()
    if view.empty:
        st.info("条件に該当する記事がありません。期間・テーマ・検索条件を緩めてください。")
        return

    for row in view.head(300).itertuples():
        with st.container(border=True):
            title_col, link_col = st.columns([8, 1.3])
            with title_col:
                title = f"{'⭐ ' if row.kobe_related else ''}{row.title}"
                if is_new_article(row.display_date):
                    badge_col, text_col = st.columns([0.8, 9.2])
                    with badge_col:
                        st.badge("NEW!", color="red")
                    with text_col:
                        st.markdown(f"### {title}")
                else:
                    st.markdown(f"### {title}")
            with link_col:
                st.link_button("元記事を開く", row.url, use_container_width=True)

            paywall_label = PAYWALL_LABELS.get(row.paywall_status, row.paywall_status)
            theme_text = row.themes.replace("｜", "・") if row.themes else "該当テーマなし"
            st.caption(
                f"{format_date(row.display_date)} ｜ {row.source_name} ｜ "
                f"主語：{row.subject_category} ｜ テーマ：{theme_text} ｜ "
                f"{paywall_label} ｜ 関連度 {row.relevance_score}"
            )
            if row.summary:
                st.write(row.summary)


frame, generated_at = load_articles()

st.title("高等教育ニュースポータル")
if generated_at:
    updated = pd.to_datetime(generated_at, utc=True).tz_convert("Asia/Tokyo")
    update_caption = f"毎朝8時頃に更新します。（最終データ更新：{updated:%Y年%m月%d日 %H:%M}）"
else:
    update_caption = "毎朝8時頃に更新します。"
st.markdown(
    f'<div class="portal-update-caption">{update_caption}</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("補助条件")
    if frame.empty:
        st.info("公表用ニュースデータがまだ生成されていません。")
        st.stop()

    search_text = st.text_input("キーワード検索")
    sources = sorted(frame["source_name"].dropna().unique())
    selected_sources = st.multiselect("媒体", sources)
    days = st.selectbox("期間", [1, 3, 7, 14, 30, 90, 365, "全期間"], index=4)
    st.caption("条件：関連度あり・新着順・無料と推定した記事")

render_new_digest(frame)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("### ①ニューステーマを選択")
selected_theme = st.selectbox(
    "①ニューステーマを選択",
    [THEME_ALL, *THEME_TABS],
    help="「すべて」はテーマで絞り込まない状態です。",
    key="main_theme_filter",
    label_visibility="collapsed",
)


filtered = frame.copy()
if days != "全期間":
    cutoff = pd.Timestamp.now(tz="Asia/Tokyo") - pd.Timedelta(days=days)
    oldest = pd.Timestamp.min.tz_localize("UTC").tz_convert("Asia/Tokyo")
    filtered = filtered[filtered["display_date"].fillna(oldest) >= cutoff]
filtered = filtered[filtered["paywall_status"] == "free"]
filtered = filtered[filtered["is_relevant"] == 1]
if selected_sources:
    filtered = filtered[filtered["source_name"].isin(selected_sources)]
if selected_theme != THEME_ALL:
    filtered = filtered[
        filtered["theme_list"].apply(lambda themes: selected_theme in themes)
    ]
if search_text:
    needle = search_text.casefold()
    matches = (
        filtered["title"].fillna("").str.casefold().str.contains(needle, regex=False)
        | filtered["summary"].fillna("").str.casefold().str.contains(needle, regex=False)
    )
    filtered = filtered[matches]

filtered = filtered.sort_values("display_date", ascending=False)

selected_subject = render_subject_summary(filtered)
selected_label = selected_subject or "すべて"
st.markdown(f"### 選択中：{selected_label}")
view = (
    filtered
    if selected_subject is None
    else filtered[filtered["subject_category"] == selected_subject]
)
render_article_list(view)

st.caption(
    "本サイトは、公開情報を自動収集・分類した個人運営の情報整理サイトです。"
    "詳細・正確な内容はリンク先をご確認ください。分類は自動処理による推定です。"
)