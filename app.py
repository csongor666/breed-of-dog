import base64
import json
import random
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Kutyafajta-felismerő", page_icon="🐕", layout="wide")
BASE = Path(__file__).parent
DATA = json.loads((BASE / "breeds.json").read_text(encoding="utf-8"))
GROUP_ORDER = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
BREEDS = [d["breed"] for d in DATA]
COATS = sorted({d["coat"] for d in DATA})
CARES = sorted({d["care"] for d in DATA})
GROUPS = [g for g in GROUP_ORDER if any(d["group"] == g for d in DATA)]

st.markdown("""<style>
.block-container{max-width:1120px;padding-top:1.35rem}.hero{padding:1.1rem 1.35rem;border-radius:18px;background:linear-gradient(120deg,#17324d,#2d6a78);color:white;margin-bottom:1rem}.hero h1{margin:0;font-size:2.05rem}.hero p{margin:.35rem 0 0;opacity:.88}.stButton button{border-radius:10px;font-weight:650}.result{padding:.8rem 1rem;border-radius:12px;background:#eef8f2;border-left:5px solid #2e8b57}.wrong{background:#fff3f1;border-left-color:#c94c4c}.smallmuted{color:#65717c;font-size:.9rem}.modebox{padding:.7rem 1rem;border-radius:12px;background:#f4f7fa;margin-bottom:.8rem}.answerline{margin:.1rem 0}</style>""", unsafe_allow_html=True)



def github_config():
    """Return GitHub settings from Streamlit secrets, or None when not configured."""
    try:
        cfg = st.secrets["github"]
        return {
            "token": str(cfg["token"]),
            "owner": str(cfg["owner"]),
            "repo": str(cfg["repo"]),
            "branch": str(cfg.get("branch", "main")),
            "log_path": str(cfg.get("log_path", "data/quiz_logs.json")),
        }
    except (KeyError, FileNotFoundError):
        return None


def github_request(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "streamlit-dog-quiz",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            details = json.loads(body)
        except json.JSONDecodeError:
            details = {"message": body}
        return exc.code, details


def load_github_logs():
    cfg = github_config()
    if not cfg:
        return [], "A GitHub naplózás nincs beállítva."
    path = urllib.parse.quote(cfg["log_path"], safe="/")
    url = f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}/contents/{path}?ref={urllib.parse.quote(cfg['branch'])}"
    status, result = github_request("GET", url, cfg["token"])
    if status == 404:
        return [], None
    if status != 200:
        return [], f"GitHub olvasási hiba ({status}): {result.get('message', 'ismeretlen hiba')}"
    try:
        raw = base64.b64decode(result["content"].replace("\n", "")).decode("utf-8")
        logs = json.loads(raw)
        return logs if isinstance(logs, list) else [], None
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        return [], f"A GitHub napló nem olvasható: {exc}"


def append_github_log(entry, retries=3):
    """Append one result with optimistic retry if another user updated the file."""
    cfg = github_config()
    if not cfg:
        return False, "A GitHub naplózás nincs beállítva a Streamlit Secrets-ben."
    path = urllib.parse.quote(cfg["log_path"], safe="/")
    base_url = f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}/contents/{path}"
    for attempt in range(retries):
        get_url = f"{base_url}?ref={urllib.parse.quote(cfg['branch'])}&t={time.time_ns()}"
        status, current = github_request("GET", get_url, cfg["token"])
        if status == 404:
            logs, sha = [], None
        elif status == 200:
            try:
                logs = json.loads(base64.b64decode(current["content"].replace("\n", "")).decode("utf-8"))
                if not isinstance(logs, list):
                    logs = []
                sha = current["sha"]
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                return False, f"A meglévő napló hibás: {exc}"
        else:
            return False, f"GitHub olvasási hiba ({status}): {current.get('message', 'ismeretlen hiba')}"
        logs.append(entry)
        payload = {
            "message": f"Quiz log: {entry['timestamp']}",
            "content": base64.b64encode(json.dumps(logs, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
            "branch": cfg["branch"],
        }
        if sha:
            payload["sha"] = sha
        put_status, result = github_request("PUT", base_url, cfg["token"], payload)
        if put_status in (200, 201):
            return True, None
        if put_status in (409, 422) and attempt < retries - 1:
            time.sleep(0.35 * (attempt + 1))
            continue
        return False, f"GitHub írási hiba ({put_status}): {result.get('message', 'ismeretlen hiba')}"
    return False, "A napló mentése ütközések miatt nem sikerült."


def build_log_entry(score, maximum, answers, difficulty):
    wrong = []
    for row in answers:
        if row["Pont"] < 4:
            wrong.append({"breed": row["Helyes fajta"], "points": int(row["Pont"]), "maximum": 4})
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "difficulty": difficulty,
        "score": int(score),
        "maximum_score": int(maximum),
        "percent": round(100 * score / maximum, 1) if maximum else 0.0,
        "wrong_breeds": wrong,
    }


def show_statistics():
    st.divider()
    st.subheader("📊 Összesített statisztika")
    logs, error = load_github_logs()
    if error:
        st.caption(error)
        return
    if not logs:
        st.info("Még nincs eltárolt kitöltés.")
        return
    valid = [x for x in logs if isinstance(x, dict)]
    percentages = [float(x.get("percent", 0)) for x in valid]
    failures = {}
    for entry in valid:
        for item in entry.get("wrong_breeds", []):
            breed = item.get("breed") if isinstance(item, dict) else str(item)
            if breed:
                failures[breed] = failures.get(breed, 0) + 1
    c1, c2, c3 = st.columns(3)
    c1.metric("Összes kitöltés", len(valid))
    c2.metric("Átlagpontszám", f"{sum(percentages) / len(percentages):.1f}%" if percentages else "0.0%")
    hardest = sorted(failures.items(), key=lambda x: (-x[1], x[0]))[:5]
    c3.metric("Hibás fajták száma", len(failures))
    if hardest:
        st.markdown("**Legnehezebb fajták, hibák száma alapján:**")
        st.dataframe(pd.DataFrame(hardest, columns=["Fajta", "Hibás kitöltések"]), hide_index=True, use_container_width=True)
    raw = json.dumps(valid, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("GitHub-log letöltése", raw, "quiz_logs.json", "application/json", use_container_width=True)

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def group_is_correct(answer, correct):
    aliases = {g: {normalize(g), str(i + 1), f"{i + 1} fajtacsoport", f"{normalize(g)} fajtacsoport"}
               for i, g in enumerate(GROUP_ORDER)}
    return normalize(answer) in aliases.get(correct, {normalize(correct)})


def text_is_correct(answer, correct):
    return normalize(answer) == normalize(correct)


def random_options(correct, pool, amount, rng):
    others = [x for x in pool if x != correct]
    selected = rng.sample(others, min(amount - 1, len(others)))
    result = selected + [correct]
    rng.shuffle(result)
    return result


def similar_breed_options(item, amount, rng):
    # First prefer dogs from the same FCI group and with the same coat or care.
    tiers = [
        [d["breed"] for d in DATA if d["breed"] != item["breed"] and d["group"] == item["group"] and (d["coat"] == item["coat"] or d["care"] == item["care"])],
        [d["breed"] for d in DATA if d["breed"] != item["breed"] and d["group"] == item["group"]],
        [d["breed"] for d in DATA if d["breed"] != item["breed"] and d["coat"] == item["coat"]],
        [b for b in BREEDS if b != item["breed"]],
    ]
    chosen = []
    for tier in tiers:
        candidates = [x for x in tier if x not in chosen]
        rng.shuffle(candidates)
        chosen.extend(candidates[: max(0, amount - 1 - len(chosen))])
        if len(chosen) >= amount - 1:
            break
    result = chosen[:amount - 1] + [item["breed"]]
    rng.shuffle(result)
    return result


def new_quiz(count, selected_groups, difficulty, indices=None):
    rng = random.Random()
    if indices is None:
        available = [i for i, d in enumerate(DATA) if d["group"] in selected_groups]
        rng.shuffle(available)
        quiz = available[:min(count, len(available))]
    else:
        quiz = list(indices)
        rng.shuffle(quiz)
    st.session_state.quiz = quiz
    st.session_state.pos = 0
    st.session_state.score = 0
    st.session_state.answers = []
    st.session_state.checked = False
    st.session_state.seed = rng.randrange(1_000_000_000)
    st.session_state.difficulty_active = difficulty
    st.session_state.result_logged = False


def init():
    defaults = {"quiz": [], "pos": 0, "score": 0, "answers": [], "checked": False,
                "seed": 0, "difficulty_active": "Könnyű", "result_logged": False}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init()
st.markdown('<div class="hero"><h1>🐕 Kutyafajta-felismerő</h1><p>Fajta, szőrtípus, ápolási mód és fajtacsoport felismerése képről</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Gyakorlás beállításai")
    selected_groups = st.multiselect("Fajtacsoportok", GROUPS, default=GROUPS,
                                     format_func=lambda x: f"{x}. fajtacsoport")
    max_count = max(1, sum(d["group"] in selected_groups for d in DATA))
    count = st.slider("Kérdések száma", 1, max_count, min(10, max_count))
    difficulty = st.radio("Nehézségi szint", ["Könnyű", "Közepes", "Mester"],
                          help="Könnyű: véletlen opciók. Közepes: hasonló fajták. Mester: szabad szöveges válaszok.")
    if st.button("Új feladatsor", type="primary", use_container_width=True, disabled=not selected_groups):
        new_quiz(count, selected_groups, difficulty)
    st.caption(f"Adatbázis: {len(DATA)} fajta, {len(GROUPS)} fajtacsoport")
    st.divider()
    st.markdown("**Pontozás:** képenként 4 pont: fajta + szőrtípus + ápolás + fajtacsoport.")

if not st.session_state.quiz:
    st.info("Válaszd ki a beállításokat, majd kattints az **Új feladatsor** gombra.")
    show_statistics()
    st.stop()

# Final results and targeted retry.
if st.session_state.pos >= len(st.session_state.quiz):
    maximum = len(st.session_state.quiz) * 4
    percent = 100 * st.session_state.score / maximum if maximum else 0
    st.success(f"Feladatsor kész! Eredmény: **{st.session_state.score}/{maximum} pont ({percent:.0f}%)**")
    if not st.session_state.result_logged:
        log_entry = build_log_entry(st.session_state.score, maximum, st.session_state.answers, st.session_state.difficulty_active)
        saved, log_error = append_github_log(log_entry)
        if saved:
            st.session_state.result_logged = True
            st.toast("Az eredmény bekerült a GitHub-naplóba.", icon="✅")
        else:
            st.warning(f"Az eredmény helyben elkészült, de a GitHub-napló mentése nem sikerült: {log_error}")
    df = pd.DataFrame(st.session_state.answers)
    if not df.empty:
        visible = ["Sorszám", "Helyes fajta", "Fajta", "Szőr", "Ápolás", "Fajtacsoport", "Pont"]
        st.dataframe(df[visible], hide_index=True, use_container_width=True)
        st.download_button("Eredmények letöltése CSV-ben", df.to_csv(index=False).encode("utf-8-sig"),
                           "fajtafelismero_eredmeny.csv", "text/csv", use_container_width=True)
        wrong_indices = df.loc[df["Pont"] < 4, "Adatindex"].astype(int).tolist()
        if wrong_indices:
            st.warning(f"{len(wrong_indices)} képnél volt legalább egy hibás válasz.")
            if st.button("🔁 Csak a hibás kérdéseket kérem újra", type="primary", use_container_width=True):
                new_quiz(len(wrong_indices), selected_groups, st.session_state.difficulty_active, wrong_indices)
                st.rerun()
        else:
            st.balloons()
            st.info("Minden válasz helyes volt, nincs újragyakorlandó kérdés.")
    if st.button("Teljes új feladatsor", use_container_width=True):
        new_quiz(count, selected_groups, difficulty)
        st.rerun()
    show_statistics()
    st.stop()

pos = st.session_state.pos
item_index = st.session_state.quiz[pos]
item = DATA[item_index]
mode = st.session_state.difficulty_active
rng = random.Random(st.session_state.seed + pos * 7919)

st.progress(pos / len(st.session_state.quiz), text=f"{pos + 1}. kérdés / {len(st.session_state.quiz)} | Pont: {st.session_state.score} | {mode}")
st.markdown(f'<div class="modebox"><b>{mode} szint</b> | Egy képen 4 pont szerezhető.</div>', unsafe_allow_html=True)
left, right = st.columns([1.05, 1], gap="large")

with left:
    st.image(str(BASE / item["image"]), use_container_width=True)
    st.markdown('<p class="smallmuted">A kép a mellékelt fajtafelismerési PDF-ből származik.</p>', unsafe_allow_html=True)

with right:
    disabled = st.session_state.checked
    if mode == "Mester":
        breed = st.text_input("1. Milyen fajta látható a képen?", key=f"breed_{pos}", disabled=disabled,
                              placeholder="Írd be a fajta nevét")
        coat = st.text_input("2. Milyen szőrtípusa van?", key=f"coat_{pos}", disabled=disabled,
                             placeholder="Írd be a szőrtípust")
        care = st.text_input("3. Milyen ápolást igényel?", key=f"care_{pos}", disabled=disabled,
                             placeholder="Írd be az ápolási módot")
        group = st.text_input("4. Melyik fajtacsoportba tartozik?", key=f"group_{pos}", disabled=disabled,
                              placeholder="Például: III vagy 3")
    else:
        breed_options = (random_options(item["breed"], BREEDS, 4, rng) if mode == "Könnyű"
                         else similar_breed_options(item, 4, rng))
        coat_options = random_options(item["coat"], COATS, 4, rng)
        care_options = random_options(item["care"], CARES, 4, rng)
        group_options = random_options(item["group"], GROUPS, 3, rng)
        breed = st.radio("1. Milyen fajta látható a képen?", breed_options, index=None, key=f"breed_{pos}", disabled=disabled)
        coat = st.radio("2. Milyen szőrtípusa van?", coat_options, index=None, key=f"coat_{pos}", disabled=disabled)
        care = st.radio("3. Milyen ápolást igényel?", care_options, index=None, key=f"care_{pos}", disabled=disabled)
        group = st.radio("4. Melyik fajtacsoportba tartozik?", group_options, index=None, key=f"group_{pos}", disabled=disabled,
                         format_func=lambda x: f"{x}. fajtacsoport")

    if not st.session_state.checked:
        if st.button("Válaszok ellenőrzése", type="primary", use_container_width=True):
            if mode == "Mester":
                missing = not all(str(x).strip() for x in (breed, coat, care, group))
            else:
                missing = None in (breed, coat, care, group)
            if missing:
                st.warning("Mind a négy kérdésre válaszolj!")
            else:
                checks = {
                    "Fajta": text_is_correct(breed, item["breed"]),
                    "Szőr": text_is_correct(coat, item["coat"]),
                    "Ápolás": text_is_correct(care, item["care"]),
                    "Fajtacsoport": group_is_correct(group, item["group"]),
                }
                points = sum(checks.values())
                st.session_state.score += points
                st.session_state.answers.append({
                    "Sorszám": pos + 1, "Adatindex": item_index, "Helyes fajta": item["breed"],
                    **{name: "✓" if ok else "✗" for name, ok in checks.items()}, "Pont": points,
                })
                st.session_state.checked = True
                st.rerun()
    else:
        last = st.session_state.answers[-1]
        css = "result" if last["Pont"] == 4 else "result wrong"
        st.markdown(
            f'<div class="{css}"><b>{last["Pont"]}/4 pont</b>'
            f'<div class="answerline">Fajta: {last["Fajta"]} <b>{item["breed"]}</b></div>'
            f'<div class="answerline">Szőrtípus: {last["Szőr"]} <b>{item["coat"]}</b></div>'
            f'<div class="answerline">Ápolás: {last["Ápolás"]} <b>{item["care"]}</b></div>'
            f'<div class="answerline">Fajtacsoport: {last["Fajtacsoport"]} <b>{item["group"]}.</b></div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Következő kérdés →", type="primary", use_container_width=True):
            st.session_state.pos += 1
            st.session_state.checked = False
            st.rerun()


show_statistics()
