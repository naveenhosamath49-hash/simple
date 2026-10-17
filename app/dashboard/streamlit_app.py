from __future__ import annotations

import datetime
import os
import sys
from typing import Dict, Any, List, Optional
import requests
import streamlit as st
import pandas as pd

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.config import settings
from app.database.database import SessionLocal, init_db
from app.database.repository import NewsRepository
from app.services.ingestion import IngestionService
from app.services.search import SearchService
from app.intelligence.llm_provider import get_llm_provider
from app.intelligence.summarizer import ArticleSummarizer
from app.intelligence.claim_comparator import ClaimComparator
from app.intelligence.qa import QuestionAnsweringEngine

st.set_page_config(
    page_title="AI News Intelligence Agent",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for polished visual hierarchy
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 4px solid #1E88E5;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .article-box {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 16px;
        transition: transform 0.1s ease-in-out;
    }
    .article-box:hover {
        border-color: #1E88E5;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .ai-badge {
        background-color: #E3F2FD;
        color: #0D47A1;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 12px;
        border: 1px solid #90CAF9;
    }
    .publisher-badge {
        background-color: #ECEFF1;
        color: #37474F;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 12px;
    }
    .category-badge {
        background-color: #E8F5E9;
        color: #1B5E20;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 12px;
    }
    .importance-badge {
        background-color: #FFF3E0;
        color: #E65100;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 12px;
    }
    .ai-summary-box {
        background-color: #F8F9FA;
        border-left: 4px solid #43A047;
        padding: 12px 16px;
        margin: 12px 0;
        border-radius: 4px;
        font-size: 0.92rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# Helper Functions (API / Local Fallback)
# ---------------------------------------------------------

@st.cache_resource
def get_db_session():
    init_db()
    return SessionLocal()


def fetch_system_summary():
    """Fetch health and metrics from backend API or local DB."""
    try:
        resp = requests.get(f"{settings.BACKEND_API_URL}/api/sources/status", timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    
    # Direct DB fallback
    db = get_db_session()
    repo = NewsRepository(db)
    summary = repo.get_system_summary()
    logs = repo.get_recent_logs(limit=10)
    llm = get_llm_provider()
    return {
        "connectors": {
            "NewsAPI": {
                "configured": bool(settings.NEWS_API_KEY and settings.NEWS_API_KEY != "your_news_api_key_here"),
                "status": "ONLINE" if settings.NEWS_API_KEY else "KEY_NOT_CONFIGURED",
            },
            "RSSConnector": {"configured": True, "status": "ONLINE"},
            "NvidiaLLM": {
                "configured": bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY != "your_nvidia_api_key_here"),
                "model": llm.model_name,
                "status": "ONLINE" if llm.is_available() else "FALLBACK_MOCK_ACTIVE",
            },
        },
        "stats": summary,
        "recent_logs": [log.to_dict() for log in logs],
    }


def trigger_ingestion_api(query: Optional[str] = None):
    """Trigger ingestion pipeline via API or direct service."""
    try:
        resp = requests.post(
            f"{settings.BACKEND_API_URL}/api/ingestion/run",
            json={"include_news_api": True, "include_rss": True, "query": query},
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json().get("details", {})
    except Exception:
        pass

    # Direct DB fallback
    db = get_db_session()
    service = IngestionService(db=db, enable_ai=True)
    return service.run_pipeline(include_news_api=True, include_rss=True, query=query)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

system_info = fetch_system_summary()
stats = system_info.get("stats", {})
connectors = system_info.get("connectors", {})

st.sidebar.title("🌐 News Intelligence")
st.sidebar.caption(f"v{settings.VERSION} | {settings.ENVIRONMENT.title()} Mode")

# Navigation Menu
nav_selection = st.sidebar.radio(
    "Navigation",
    [
        "📰 Live Feed & Search",
        "🧠 Deep AI Analysis",
        "📈 Trend & Emerging Topics",
        "💬 Grounded AI Q&A",
        "⚖️ Cross-Source Claim Comparison",
        "⚙️ Connectors & Health Logs",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.subheader("📡 Connector Status")

# News API indicator
n_status = connectors.get("NewsAPI", {}).get("status", "UNKNOWN")
if n_status == "ONLINE":
    st.sidebar.success("🟢 News API: Connected")
else:
    st.sidebar.warning(f"🟡 News API: {n_status}")

# RSS indicator
st.sidebar.success("🟢 RSS Feeds: Active (5 feeds)")

# LLM indicator
llm_info = connectors.get("NvidiaLLM", {})
if llm_info.get("status") == "ONLINE":
    st.sidebar.success(f"🟢 NVIDIA NIM: {llm_info.get('model', 'Online')}")
else:
    st.sidebar.info("🔵 Intelligence: Heuristic/Mock Active")

st.sidebar.markdown("---")
last_time = stats.get("last_collection_time")
if last_time:
    st.sidebar.caption(f"Last Collection: {str(last_time)[:19]}")

if st.sidebar.button("🔄 Trigger News Ingestion", use_container_width=True):
    with st.spinner("Ingesting, deduplicating, and analyzing news..."):
        ingest_res = trigger_ingestion_api()
        st.sidebar.success(f"Ingested {ingest_res.get('inserted', 0)} new articles!")
        st.rerun()


# ---------------------------------------------------------
# View 1: Live Feed & Search
# ---------------------------------------------------------
if nav_selection == "📰 Live Feed & Search":
    st.title("📰 Live Intelligence Feed")
    st.markdown("Aggregated, normalized, and AI-enriched intelligence from verified global sources.")

    # Top Metric Tiles
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Ingested Articles", stats.get("total_articles", 0))
    with m2:
        st.metric("Published in Last 24h", stats.get("recent_articles_24h", 0))
    with m3:
        st.metric("Canonical Articles", stats.get("canonical_articles", 0))
    with m4:
        st.metric("Near-Duplicates Filtered", stats.get("duplicate_articles", 0))

    st.markdown("---")

    # Search & Filter Controls
    c_search, c_cat, c_imp = st.columns([3, 2, 1.5])
    with c_search:
        search_query = st.text_input("🔍 Keyword Search", placeholder="e.g. artificial intelligence, semiconductors, treaty...")
    with c_cat:
        available_categories = ["All"] + settings.DEFAULT_CATEGORIES
        selected_category = st.selectbox("Category Filter", available_categories)
    with c_imp:
        min_importance = st.slider("Min Importance Score", 0.0, 10.0, 0.0, step=0.5)

    # Fetch articles
    db = get_db_session()
    repo = NewsRepository(db)
    articles, total_matches = repo.search_articles(
        query=search_query if search_query else None,
        category=selected_category if selected_category != "All" else None,
        min_importance=min_importance if min_importance > 0 else None,
        limit=40,
    )

    st.caption(f"Displaying {len(articles)} of {total_matches} matching articles.")

    if not articles:
        st.info("No articles match the current filter criteria. Use the sidebar to trigger a collection run.")
    else:
        for art in articles:
            analysis = art.ai_analysis
            imp_score = analysis.importance_score if analysis else 5.0
            category = art.category or "General"
            pub_date = str(art.published_at)[:16]

            with st.container():
                st.markdown(f"""
                <div class="article-box">
                    <div style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center;">
                        <span class="category-badge">{category}</span>
                        <span class="publisher-badge">{art.publisher_name}</span>
                        <span class="importance-badge">Importance: {imp_score}/10</span>
                        <span style="color: #757575; font-size: 0.8rem; margin-left: auto;">{pub_date}</span>
                    </div>
                    <h3 style="margin-top: 4px; margin-bottom: 8px;">
                        <a href="{art.url}" target="_blank" style="text-decoration: none; color: #1565C0;">{art.title}</a>
                    </h3>
                    <p style="color: #424242; font-size: 0.95rem; margin-bottom: 8px;">
                        <strong>Original Publisher Excerpt:</strong> {art.description or art.content or "No original description available."}
                    </p>
                """, unsafe_allow_html=True)

                if analysis:
                    st.markdown(f"""
                    <div class="ai-summary-box">
                        <span class="ai-badge">AI Intelligence Summary ({analysis.model_used})</span>
                        <p style="margin-top: 6px; margin-bottom: 0;">{analysis.summary}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Entities
                    entities = analysis.entities or {}
                    ent_pills = []
                    for p in entities.get("people", [])[:3]:
                        ent_pills.append(f"👤 {p}")
                    for o in entities.get("organizations", [])[:3]:
                        ent_pills.append(f"🏛️ {o}")
                    for c in entities.get("companies", [])[:3]:
                        ent_pills.append(f"🏢 {c}")
                    for l in entities.get("locations", [])[:3]:
                        ent_pills.append(f"📍 {l}")

                    if ent_pills:
                        st.markdown(f"<div style='font-size: 0.82rem; color: #555;'>{' &nbsp;|&nbsp; '.join(ent_pills)}</div>", unsafe_allow_html=True)

                st.markdown(f"""
                    <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <a href="{art.url}" target="_blank" style="font-size: 0.85rem; color: #1E88E5; font-weight: 600;">🔗 Read Original Article on {art.publisher_name} &rarr;</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ---------------------------------------------------------
# View 2: Deep AI Analysis
# ---------------------------------------------------------
elif nav_selection == "🧠 Deep AI Analysis":
    st.title("🧠 Deep AI Intelligence Analysis")
    st.markdown("Detailed intelligence breakdown, entity relationship mapping, and transparent importance scoring.")

    db = get_db_session()
    repo = NewsRepository(db)
    articles, _ = repo.search_articles(limit=50)

    if not articles:
        st.warning("No articles available in database. Please run ingestion from the sidebar first.")
    else:
        article_options = {f"[{a.id}] {a.title[:80]}... ({a.publisher_name})": a for a in articles}
        selected_key = st.selectbox("Select Article to Analyze", list(article_options.keys()))
        selected_article = article_options[selected_key]
        analysis = selected_article.ai_analysis

        c1, c2 = st.columns([1, 1])

        with c1:
            st.subheader("📄 Verified Publisher Content")
            st.markdown(f"**Headline:** {selected_article.title}")
            st.markdown(f"**Publisher:** {selected_article.publisher_name} ({selected_article.publisher_domain or 'N/A'})")
            st.markdown(f"**Publication Timestamp:** `{selected_article.published_at}`")
            st.markdown(f"**Canonical Link:** [{selected_article.canonical_url}]({selected_article.url})")
            st.markdown("---")
            st.markdown("**Original Description / Content:**")
            st.write(selected_article.content or selected_article.description or "No full text available.")

        with c2:
            st.subheader("🤖 AI Intelligence Synthesis")
            if not analysis:
                st.info("This article has not been processed through the AI pipeline yet.")
                if st.button("Generate AI Intelligence Now"):
                    with st.spinner("Processing article with LLM..."):
                        service = IngestionService(db=db, enable_ai=True)
                        service._process_article_ai(selected_article)
                        st.success("Analysis generated!")
                        st.rerun()
            else:
                st.caption(f"Synthesized by model: `{analysis.model_used}` | Analyzed at: `{analysis.created_at}`")
                st.markdown("### Executive Summary")
                st.info(analysis.summary)

                st.markdown("### Transparent Importance Criteria")
                breakdown = analysis.importance_breakdown or {}
                col_i1, col_i2, col_i3, col_i4 = st.columns(4)
                col_i1.metric("Recency", f"{breakdown.get('recency', 5.0)}/10")
                col_i2.metric("Source Diversity", f"{breakdown.get('source_diversity', 5.0)}/10")
                col_i3.metric("Source Quality", f"{breakdown.get('source_quality', 5.0)}/10")
                col_i4.metric("Public Impact", f"{breakdown.get('public_impact', 5.0)}/10")

                st.markdown("### Extracted Entities")
                entities = analysis.entities or {}
                t_p, t_o, t_c, t_l = st.tabs(["People", "Organizations", "Companies", "Locations"])
                with t_p:
                    people = entities.get("people", [])
                    st.write(", ".join(people) if people else "No individuals extracted.")
                with t_o:
                    orgs = entities.get("organizations", [])
                    st.write(", ".join(orgs) if orgs else "No organizations extracted.")
                with t_c:
                    comps = entities.get("companies", [])
                    st.write(", ".join(comps) if comps else "No corporate entities extracted.")
                with t_l:
                    locs = entities.get("locations", [])
                    st.write(", ".join(locs) if locs else "No locations extracted.")


# ---------------------------------------------------------
# View 3: Trend & Emerging Topics
# ---------------------------------------------------------
elif nav_selection == "📈 Trend & Emerging Topics":
    st.title("📈 Topic Radar & Emerging Trends")
    st.markdown("""
    Tracks topic velocity and publisher diversity over a defined observation window.
    **Objectivity Rule:** A topic is only marked as trending if corroborated by **>= 2 independent reporting sources**.
    """)

    db = get_db_session()
    repo = NewsRepository(db)
    topics = repo.get_trending_topics(limit=25)

    if not topics:
        st.info("No topics tracked yet. Ingestion will automatically calculate trend metrics across articles.")
    else:
        # Check for emerging topics
        emerging = [t for t in topics if t.is_emerging]
        if emerging:
            st.warning(f"🚨 **Recently Emerging Topics Detected ({len(emerging)}):** " + ", ".join([t.name for t in emerging]))

        topic_data = []
        for t in topics:
            metrics = t.trend_metrics or {}
            topic_data.append({
                "Topic Name": t.name,
                "Article Count": t.article_count,
                "Trend Score": t.trend_score,
                "Velocity (Arts/Hr)": metrics.get("velocity", 0.0),
                "Multi-Source Confirmed": "✅ Yes" if metrics.get("is_trending") else "⚠️ Single Source",
                "Emerging": "🔥 Emerging" if t.is_emerging else "Normal",
                "Last Active": str(t.last_observed_at)[:16],
            })

        df_topics = pd.DataFrame(topic_data)
        st.dataframe(df_topics, use_container_width=True)

        st.markdown("---")
        st.subheader("📊 Category Distribution")
        summary = repo.get_system_summary()
        cat_counts = summary.get("categories", {})
        if cat_counts:
            df_cat = pd.DataFrame(list(cat_counts.items()), columns=["Category", "Count"]).sort_values("Count", ascending=False)
            st.bar_chart(df_cat.set_index("Category"))


# ---------------------------------------------------------
# View 4: Grounded AI Q&A
# ---------------------------------------------------------
elif nav_selection == "💬 Grounded AI Q&A":
    st.title("💬 Grounded AI Question Answering")
    st.markdown("""
    Ask questions about current global news. Answers are **strictly grounded** in collected article documents.
    If the intelligence database lacks evidence, the system will explicitly report that limitation.
    """)

    # Quick question suggestions
    st.markdown("**Sample inquiries:**")
    q_col1, q_col2, q_col3 = st.columns(3)
    sample_q = ""
    if q_col1.button("Technology Developments"):
        sample_q = "What are today's major technology stories?"
    if q_col2.button("Artificial Intelligence"):
        sample_q = "Summarize the latest developments in artificial intelligence."
    if q_col3.button("International Affairs"):
        sample_q = "What are the key international news stories reported this week?"

    user_query = st.text_input("Enter your intelligence inquiry:", value=sample_q, placeholder="e.g. What are the key business stories in the technology sector?")

    if st.button("Generate Grounded Answer", type="primary"):
        if not user_query.strip():
            st.warning("Please type a question or select a sample inquiry.")
        else:
            with st.spinner("Retrieving evidence and synthesizing grounded response..."):
                try:
                    resp = requests.post(
                        f"{settings.BACKEND_API_URL}/api/ai/ask",
                        json={"question": user_query, "days_back": 14, "limit": 8},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        qa_result = resp.json()
                    else:
                        raise Exception(resp.text)
                except Exception:
                    # Fallback direct call
                    db = get_db_session()
                    repo = NewsRepository(db)
                    llm = get_llm_provider()
                    qa_engine = QuestionAnsweringEngine(llm)
                    arts, _ = repo.search_articles(query=user_query, limit=8)
                    qa_result = qa_engine.answer_question(user_query, [a.to_dict() for a in arts])

                st.markdown("### Answer")
                status = qa_result.get("evidence_status", "PARTIAL")
                if status == "SUFFICIENT":
                    st.success(f"Evidence Level: **SUFFICIENT** (Verified across {len(qa_result.get('citations', []))} sources)")
                elif status == "PARTIAL":
                    st.info("Evidence Level: **PARTIAL** (Limited supporting articles found in database)")
                else:
                    st.warning("Evidence Level: **INSUFFICIENT** (Database does not contain sufficient coverage)")

                st.write(qa_result.get("answer"))

                citations = qa_result.get("citations", [])
                if citations:
                    st.markdown("---")
                    st.markdown("#### 📚 Supporting Article Citations")
                    for cit in citations:
                        st.markdown(f"- **{cit.get('doc_ref', '[Doc]')}**: [{cit.get('title')}]({cit.get('url')}) — *{cit.get('publisher')}* ({cit.get('published_at')})")


# ---------------------------------------------------------
# View 5: Cross-Source Claim Comparison
# ---------------------------------------------------------
elif nav_selection == "⚖️ Cross-Source Claim Comparison":
    st.title("⚖️ Cross-Source Claim Comparison Engine")
    st.markdown("""
    Cross-examine reporting across multiple publishers to detect consensus, single-source disclosures, conflicting facts, and unverified statements.
    """)

    db = get_db_session()
    repo = NewsRepository(db)
    articles, _ = repo.search_articles(limit=40)

    if len(articles) < 2:
        st.info("At least 2 articles are required to perform cross-source claim comparison. Ingest news first.")
    else:
        article_map = {f"[{a.id}] {a.title} ({a.publisher_name})": a.id for a in articles}
        selected_options = st.multiselect(
            "Select 2 to 5 articles to compare:",
            options=list(article_map.keys()),
            default=list(article_map.keys())[:2] if len(article_map) >= 2 else [],
        )

        topic_label = st.text_input("Topic / Event Label (optional):", placeholder="e.g. AI Model Release, Geopolitical Summit")

        if st.button("Compare Claims Across Sources", type="primary"):
            if len(selected_options) < 2:
                st.warning("Please select at least 2 articles.")
            else:
                chosen_ids = [article_map[k] for k in selected_options]
                with st.spinner("Cross-referencing claims with AI analysis..."):
                    llm = get_llm_provider()
                    comparator = ClaimComparator(llm)
                    art_dicts = [repo.get_article(aid).to_dict() for aid in chosen_ids]
                    comparison = comparator.compare_articles(art_dicts, topic_hint=topic_label)

                    st.markdown(f"### Consensus Summary")
                    st.success(comparison.get("summary_of_consensus", "N/A"))

                    c_left, c_right = st.columns(2)

                    with c_left:
                        st.markdown("#### ✅ Corroborated by Multiple Sources")
                        multi_claims = comparison.get("supported_by_multiple_sources", [])
                        if multi_claims:
                            for item in multi_claims:
                                if isinstance(item, dict):
                                    st.markdown(f"- **{item.get('claim')}** *(Sources: {', '.join(item.get('sources', []))})*")
                                else:
                                    st.markdown(f"- {item}")
                        else:
                            st.write("No multi-source claims identified.")

                        st.markdown("#### ⚡ Conflicting Reports")
                        conflicts = comparison.get("conflicting_claims", [])
                        if conflicts:
                            for c in conflicts:
                                if isinstance(c, dict):
                                    st.markdown(f"- **{c.get('aspect')}**: {c.get('source_a')} *vs* {c.get('source_b')}")
                                else:
                                    st.markdown(f"- {c}")
                        else:
                            st.write("No factual contradictions observed among selected articles.")

                    with c_right:
                        st.markdown("#### 🔍 Single-Source Disclosures")
                        single_claims = comparison.get("single_source_claims", [])
                        if single_claims:
                            for s in single_claims:
                                if isinstance(s, dict):
                                    st.markdown(f"- {s.get('claim')} — *({s.get('source')})*")
                                else:
                                    st.markdown(f"- {s}")
                        else:
                            st.write("No exclusive single-source claims detected.")

                        st.markdown("#### ❓ Unverified / Developing Claims")
                        st.caption("Note: Unverified claims are not declared false; they require additional confirmation.")
                        unverified = comparison.get("unverified_claims", [])
                        if unverified:
                            for u in unverified:
                                if isinstance(u, dict):
                                    st.markdown(f"- {u.get('claim')} *(Context: {u.get('context', 'Pending')})*")
                                else:
                                    st.markdown(f"- {u}")
                        else:
                            st.write("No unverified claims flagged.")


# ---------------------------------------------------------
# View 6: Connectors & Health Logs
# ---------------------------------------------------------
elif nav_selection == "⚙️ Connectors & Health Logs":
    st.title("⚙️ System Observability & Connector Logs")
    st.markdown("Audit logs, API quota awareness, and connector telemetry.")

    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("🔌 Configured Connectors")
        st.markdown(f"- **News API**: `{'Configured' if connectors.get('NewsAPI', {}).get('configured') else 'Missing API Key'}`")
        st.markdown(f"- **RSS Syndication**: `Configured ({len(settings.DEFAULT_RSS_FEEDS)} feeds)`")
        st.markdown(f"- **NVIDIA NIM LLM**: `{'Configured' if connectors.get('NvidiaLLM', {}).get('configured') else 'Using Fallback Intelligence'}`")
        st.markdown(f"- **Database URL**: `{settings.DATABASE_URL}`")

    with c_right:
        st.subheader("🛡️ Security Controls Active")
        st.markdown("- **SSRF Protection**: Private IP ranges (RFC 1918, loopbacks, link-local metadata) blocked.")
        st.markdown("- **Prompt Injection Sanitization**: Article text XML-encapsulated & defanged.")
        st.markdown("- **Deterministic Deduplication**: SHA-256 fingerprinting + token shingling.")

    st.markdown("---")
    st.subheader("📋 Recent Operation Audit Logs")
    recent_logs = system_info.get("recent_logs", [])
    if recent_logs:
        df_logs = pd.DataFrame(recent_logs)[["connector_name", "operation", "status", "articles_fetched", "articles_inserted", "timestamp"]]
        st.dataframe(df_logs, use_container_width=True)
    else:
        st.info("No system logs recorded yet.")
