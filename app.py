"""The Comeback Equation — NCAA Women's Basketball visualization dashboard.
Run from the BasketballComebackAnalysis project directory:
    python -m streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path(__file__).resolve().parent

st.set_page_config(page_title="The Comeback Equation", page_icon="🏀", layout="wide")


def elapsed_minutes(period, clock, regulation_periods):
    """Minutes elapsed from tip-off, including 5-minute overtime periods."""
    try:
        period = int(period)
        regulation_periods = int(regulation_periods)
        minutes, seconds = str(clock).split(":")
        clock_seconds = int(minutes) * 60 + float(seconds)
        if regulation_periods not in (2, 4) or period < 1:
            return None
        period_length = 1200 if regulation_periods == 2 else 600
        if period <= regulation_periods:
            if not 0 <= clock_seconds <= period_length:
                return None
            return ((period - 1) * period_length + period_length - clock_seconds) / 60
        if not 0 <= clock_seconds <= 300:
            return None
        return (2400 + (period - regulation_periods - 1) * 300 + 300 - clock_seconds) / 60
    except (TypeError, ValueError):
        return None


@st.cache_data
def load_data():
    stats = pd.read_csv(BASE / "visualizations/time_aware_comeback_statistics.csv")
    trends = pd.read_csv(BASE / "visualizations/season_comeback_statistics.csv")
    events = pd.read_csv(
        BASE / "data/processed/top50_comeback_events.csv", dtype={"game_id": str}
    )
    games = pd.read_csv(
        BASE / "data/game_metadata.csv",
        usecols=[
            "game_id", "home_display_name", "away_display_name", "game_date",
            "format_regulation_periods",
        ],
        dtype={"game_id": str},
        low_memory=False,
    ).drop_duplicates("game_id")
    events = events.merge(games, on="game_id", how="left", validate="many_to_one")
    events["sequence_number"] = pd.to_numeric(events["sequence_number"], errors="coerce")
    events["home_score"] = pd.to_numeric(events["home_score"], errors="coerce")
    events["away_score"] = pd.to_numeric(events["away_score"], errors="coerce")
    events = events.dropna(subset=["sequence_number", "home_score", "away_score"])
    return stats, trends, events


st.title("🏀 The Comeback Equation")
st.markdown("### When does a basketball game become almost impossible to win?")
st.write(
    "Explore more than two decades of NCAA Women's Basketball play-by-play data "
    "to discover how scoring deficits and time remaining relate to comeback outcomes."
)
st.markdown(
    "**Start with Comeback Odds** to explore the statistics, then visit "
    "**Game Explorer** to follow extraordinary comebacks as they unfold."
)
st.caption("Historical observations from games passing preliminary data-quality checks, 2006–2026.")

headline1, headline2, headline3 = st.columns(3)
headline1.metric("Games Analyzed", "51,814")
headline2.metric("10+ Point Comebacks", "5,401")
headline3.metric("Win Rate After 20+ Point Deficit", "0.48%")
st.caption(
    "The first two headline figures count games; the last is the observed percentage "
    "of teams that ever faced a 20+ point deficit and subsequently won."
)

try:
    stats, trends, events = load_data()
except (FileNotFoundError, ValueError, KeyError) as exc:
    st.error(f"Could not load project data: {exc}")
    st.info("Check that data/game_metadata.csv, the processed event CSV, and both visualization CSVs exist.")
    st.stop()

odds_tab, games_tab, trends_tab, method_tab = st.tabs([
    "📊 Comeback Odds", "🏀 Game Explorer", "📈 Historical Trends", "🔬 Methodology"
])

# ---------- Comeback Odds ----------
with odds_tab:
    st.header("When Does a Deficit Become Too Large?")
    st.write(
        "These are observed win percentages for teams that first reached a given "
        "deficit within each time window. Each cell shows a rate, not a live prediction."
    )
    order = ["30–40", "20–30", "10–20", "0–10"]
    thresholds = [10, 15, 20]
    rates = stats.pivot(index="threshold", columns="time_window", values="win_percentage")
    rates = rates.reindex(index=thresholds, columns=order)
    counts = stats.pivot(index="threshold", columns="time_window", values="total_teams")
    counts = counts.reindex(index=thresholds, columns=order)
    wins = stats.pivot(index="threshold", columns="time_window", values="successful_comebacks")
    wins = wins.reindex(index=thresholds, columns=order)
    fig = go.Figure(go.Heatmap(
        z=rates.to_numpy(), x=order, y=[f"{n} pts" for n in thresholds],
        customdata=[[[int(wins.iloc[i, j]), int(counts.iloc[i, j])]
                     for j in range(len(order))] for i in range(len(thresholds))],
        colorscale="Blues", colorbar=dict(title="Win rate (%)"),
        text=[[f"{rates.iloc[i,j]:.2f}%" for j in range(len(order))]
              for i in range(len(thresholds))],
        texttemplate="%{text}",
        hovertemplate=("Deficit: %{y}<br>Time remaining: %{x} minutes<br>"
                       "Won: %{customdata[0]:,} / %{customdata[1]:,}<br>"
                       "Win rate: %{z:.2f}%<extra></extra>"),
    ))
    fig.update_layout(
        title="Observed Win Rate After Falling Behind", height=440,
        xaxis_title="Minutes remaining in regulation", yaxis_title="Deficit threshold",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.info("Historical associations, not causal effects or predictions for specific games.")
    with st.expander("View underlying observations"):
        st.dataframe(stats, hide_index=True, use_container_width=True)

# ---------- Game Explorer ----------
with games_tab:
    st.header("Explore a Comeback")
    st.write("Follow the eventual winner's scoring margin, biggest deficit, and first lead after that deficit.")

    # Only games whose winning team trailed by at least ten points.
    ordered = events.sort_values(["game_id", "sequence_number"])
    summary = ordered.groupby("game_id").agg(
        final_home=("home_score", "last"),
        final_away=("away_score", "last"),
    )
    ordered = ordered.assign(margin=ordered["home_score"] - ordered["away_score"])
    margin_summary = ordered.groupby("game_id")["margin"].agg(["min", "max"])
    summary["largest_deficit"] = [
        max(0, -margin_summary.loc[gid, "min"])
        if row.final_home > row.final_away else max(0, margin_summary.loc[gid, "max"])
        for gid, row in summary.iterrows()
    ]
    comeback_ids = summary.index[summary["largest_deficit"] >= 10]
    eligible_events = ordered[ordered["game_id"].isin(comeback_ids)].copy()

    info = eligible_events.groupby("game_id", as_index=False).agg(
        home_team=("home_display_name", "first"),
        away_team=("away_display_name", "first"),
        date=("game_date", "first"),
        season=("season", "first"),
    )
    info["display"] = (
        info["away_team"].fillna("Away Team") + " vs. "
        + info["home_team"].fillna("Home Team") + " ("
        + info["date"].astype(str) + ")"
    )
    info = info.merge(summary[["largest_deficit"]], left_on="game_id", right_index=True)

    filter1, filter2, filter3 = st.columns(3)
    with filter1:
        years = sorted(pd.to_numeric(info["season"], errors="coerce").dropna().astype(int).unique(), reverse=True)
        selected_year = st.selectbox("Season", ["All seasons"] + list(years))
    with filter2:
        team_search = st.text_input("Search for a team", placeholder="e.g. Iowa, Purdue, UConn")
    with filter3:
        minimum_deficit = st.selectbox("Minimum comeback size", [10, 15, 20, 25, 30], index=0)

    if selected_year != "All seasons":
        info = info[pd.to_numeric(info["season"], errors="coerce") == selected_year]
    if team_search.strip():
        info = info[
            info["home_team"].fillna("").str.contains(team_search, case=False, regex=False)
            | info["away_team"].fillna("").str.contains(team_search, case=False, regex=False)
        ]
    info = info[info["largest_deficit"] >= minimum_deficit]
    info = info.sort_values(["largest_deficit", "game_id"], ascending=[False, True])

    if info.empty:
        st.info("No featured games match those filters. Try a different season, team, or minimum deficit.")
    else:
        selected_id = st.selectbox(
            "Choose a game", info["game_id"].tolist(),
            format_func=lambda gid: info.set_index("game_id").loc[gid, "display"],
        )
        game = eligible_events[eligible_events["game_id"] == selected_id].copy()
        game = game.sort_values("sequence_number").reset_index(drop=True)
        home_name = str(game.iloc[0]["home_display_name"])
        away_name = str(game.iloc[0]["away_display_name"])
        final_home = int(game.iloc[-1]["home_score"])
        final_away = int(game.iloc[-1]["away_score"])
        home_won = final_home > final_away
        winner_name = home_name if home_won else away_name
        loser_name = away_name if home_won else home_name
        season = int(game.iloc[0]["season"])
        fmt = pd.to_numeric(game.iloc[0]["format_regulation_periods"], errors="coerce")
        regulation_periods = int(fmt) if pd.notna(fmt) and int(fmt) in (2, 4) else (2 if season <= 2015 else 4)

        game["elapsed_minutes"] = game.apply(
            lambda r: elapsed_minutes(r["period_number"], r["clock_display_value"], regulation_periods), axis=1
        )
        game = game.dropna(subset=["elapsed_minutes"]).copy()
        game = game.sort_values(["elapsed_minutes", "sequence_number"]).reset_index(drop=True)
        if game.empty:
            st.warning("No valid game-clock records are available for this matchup.")
        else:
            game["winner_margin"] = (
                game["home_score"] - game["away_score"] if home_won
                else game["away_score"] - game["home_score"]
            )
            largest_deficit = int(max(0, -game["winner_margin"].min()))
            low_idx = int(game["winner_margin"].idxmin())
            lowest = game.loc[low_idx]
            deficit_time = float(lowest["elapsed_minutes"])
            remaining = max(0, 40 - deficit_time)
            post_low = game.loc[low_idx:]
            lead_rows = post_low[post_low["winner_margin"] > 0]
            lead_event = lead_rows.iloc[0] if not lead_rows.empty else None

            st.subheader(f"{away_name} vs. {home_name}")
            m1, m2, m3 = st.columns(3)
            m1.metric(home_name, final_home)
            m2.metric(away_name, final_away)
            m3.metric("Largest deficit overcome", f"{largest_deficit} pts")

            st.markdown("### 📖 The Comeback Story")
            if largest_deficit:
                time_phrase = (
                    f"with approximately **{remaining:.1f} minutes left in regulation**"
                    if deficit_time <= 40 else "during overtime"
                )
                story = f"**{winner_name}** trailed **{loser_name}** by **{largest_deficit} points** {time_phrase}. "
                if lead_event is not None:
                    story += (f"They first moved ahead after that deficit at approximately "
                              f"**{lead_event['elapsed_minutes']:.1f} minutes elapsed**. ")
                story += f"They won **{max(final_home, final_away)}–{min(final_home, final_away)}**."
            else:
                story = f"**{winner_name}** did not trail in the recorded timeline."
            st.markdown(story)

            k1, k2, k3 = st.columns(3)
            k1.metric("Biggest deficit", f"{largest_deficit} pts")
            k2.metric("Time of biggest deficit", f"{deficit_time:.1f} min elapsed")
            k3.metric("First lead after deficit",
                      f"{float(lead_event['elapsed_minutes']):.1f} min" if lead_event is not None else "N/A")

            plot = go.Figure()
            plot.add_trace(go.Scatter(
                x=game["elapsed_minutes"], y=game["winner_margin"], mode="lines",
                line=dict(color="#2563eb", width=3), name="Eventual winner's lead",
                customdata=game[["period_number", "clock_display_value", "text"]].fillna("").to_numpy(),
                hovertemplate=("Time elapsed: %{x:.1f} min<br>Winner's margin: %{y} pts<br>"
                               "Period: %{customdata[0]} · Clock: %{customdata[1]}<br>"
                               "%{customdata[2]}<extra></extra>"),
            ))
            plot.add_hline(y=0, line_dash="dash", line_color="gray")
            if largest_deficit:
                plot.add_trace(go.Scatter(
                    x=[deficit_time], y=[float(lowest["winner_margin"])],
                    mode="markers+text", marker=dict(color="#dc2626", size=13),
                    text=[f"−{largest_deficit} pts"], textposition="bottom center",
                    name="Largest deficit", hovertemplate="Largest deficit: %{y} pts<extra></extra>",
                ))
                if lead_event is not None:
                    plot.add_trace(go.Scatter(
                        x=[float(lead_event["elapsed_minutes"])],
                        y=[float(lead_event["winner_margin"])],
                        mode="markers+text", marker=dict(color="#15803d", size=13),
                        text=["Takes the lead"], textposition="top center", name="First lead after deficit",
                    ))
            plot.update_layout(
                title=f"{winner_name}: The Comeback Timeline",
                xaxis_title="Minutes elapsed", yaxis_title=f"{winner_name}'s lead (points)",
                height=540, hovermode="closest",
                xaxis=dict(range=[0, max(40, float(game["elapsed_minutes"].max()))], dtick=5),
            )
            st.plotly_chart(plot, use_container_width=True)
            st.caption("Negative values mean the eventual winner was behind. Hover to see the recorded plays.")
            st.caption("Featured games passed automated consistency checks; these checks do not independently verify every recorded event.")

# ---------- Historical Trends ----------
with trends_tab:
    st.header("How Have Comebacks Changed Over Time?")
    st.write("Share of games where the eventual winner overcame a deficit of at least 10 points.")
    trend_fig = px.line(
        trends, x="season", y="comeback_rate", markers=True,
        custom_data=["total_games", "comebacks"],
        labels={"season": "Season", "comeback_rate": "Games with 10+ point comebacks (%)"},
        title="10+ Point Comebacks Across Seasons",
    )
    trend_fig.update_traces(hovertemplate=(
        "Season: %{x}<br>Comeback rate: %{y:.2f}%<br>"
        "Games analyzed: %{customdata[0]:,}<br>Comebacks: %{customdata[1]:,}<extra></extra>"
    ))
    trend_fig.update_layout(height=480, xaxis=dict(dtick=1), yaxis=dict(ticksuffix="%"))
    st.plotly_chart(trend_fig, use_container_width=True)
    st.write("In games passing preliminary checks, 10+ point comebacks generally account for about 8–12% of games in each season.")
    st.warning("Coverage differs substantially by season, especially in earlier years. Do not infer changes in the sport from these rates alone.")
    with st.expander("View season-by-season statistics"):
        st.dataframe(trends, hide_index=True, use_container_width=True)

# ---------- Methodology ----------
with method_tab:
    st.header("Methodology & Data Validation")
    st.write("NCAA Women's Basketball play-by-play data (2006–2026), from the provided ESPN-derived dataset.")
    x1, x2, x3 = st.columns(3)
    x1.metric("Games processed", "54,925")
    x2.metric("Games passing checks", "51,814")
    x3.metric("10+ point comebacks", "5,401")
    st.subheader("Data processing")
    st.markdown("""
1. **Extract:** Processed approximately 19.2 million events using memory-safe partitions.
2. **Validate:** Compared each recorded final score with the corresponding game record.
3. **Correct:** Fixed isolated rows where the home and away scores appeared reversed.
4. **Screen:** Excluded games with mismatching final scores or unexplained large margin jumps.
5. **Classify:** Determined the eventual winner's largest recorded deficit.
6. **Analyze timing:** Located the first recorded crossing of each threshold (5, 10, 15, 20, 25 points), including regulation timing and eventual outcome.
7. **Featured games:** Audited 38 selected games for score continuity, final-score agreement, event sequence uniqueness, and clock-field availability.
""")
    st.subheader("How win rates are calculated")
    st.latex(r"P(\mathrm{Win}\mid\mathrm{Deficit\ reached}) = \frac{\mathrm{Teams\ that\ eventually\ won}}{\mathrm{Teams\ that\ reached\ the\ deficit}}")
    st.write(
        "A team is counted once per deficit threshold at its first recorded crossing. "
        "Time-window rates exclude overtime crossings. Threshold groups overlap: a team reaching 20 points behind also reached 10 and 15."
    )
    st.subheader("Limitations")
    st.markdown("""
- **Coverage:** Fewer historical games are represented in some seasons, especially early years.
- **Incomplete play-by-play:** Matching final scores does not guarantee all intermediate events are complete.
- **Selection effects:** Excluding games with unusual records may affect the reported rates.
- **Scoring corrections:** Some excluded changes could reflect legitimate score corrections.
- **Observational estimates:** These rates are descriptive, not causal or calibrated live win-probability forecasts.
- **Timing:** The displayed first crossing is the first *recorded* threshold event, which may differ from the true first crossing if events are missing.
""")
    st.info("These findings reflect games passing preliminary data-quality checks, not a complete independently verified NCAA game census.")
