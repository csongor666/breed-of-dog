import json
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Kutyakozmetikus tanuló app",
    page_icon="🐕",
    layout="wide",
)

BASE = Path(__file__).parent
BREEDS_FILE = BASE / "breeds.json"
QUESTIONS_FILE = BASE / "questions_001_500.json"
STATS_FILE = BASE / "quiz_statistics.json"

st.markdown(
    """
<style>
.block-container{max-width:1150px;padding-top:1.2rem}
.hero{padding:1.1rem 1.35rem;border-radius:18px;background:linear-gradient(120deg,#17324d,#2d6a78);color:white;margin-bottom:1rem}
.hero h1{margin:0;font-size:2.05rem}.hero p{margin:.35rem 0 0;opacity:.9}
.stButton button{border-radius:10px;font-weight:650}
.result{padding:.8rem 1rem;border-radius:12px;background:#eef8f2;border-left:5px solid #2e8b57}
.wrong{background:#fff3f1;border-left-color:#c94c4c}
.smallmuted{color:#65717c;font-size:.9rem}
.metricbox{padding:.65rem .8rem;border-radius:12px;background:#f4f7f9}
</style>
""",
    unsafe_allow_html=True,
)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def load_questions():
    """Use the merged file when present, otherwise combine question blocks."""
    if QUESTIONS_FILE.exists():
        raw = read_json(QUESTIONS_FILE, {})
        questions = raw.get("questions", raw if isinstance(raw, list) else [])
    else:
        questions = []
        for path in sorted(BASE.glob("questions_*.json")):
            if path.name == QUESTIONS_FILE.name:
                continue
            raw = read_json(path, {})
            block = raw.get("questions", raw if isinstance(raw, list) else [])
            questions.extend(block)

    valid = []
    seen = set()
    for q in questions:
        try:
            qid = int(q["id"])
            answers = list(q["answers"])
            correct = int(q["correct"])
            if qid in seen or len(answers) < 2 or not 0 <= correct < len(answers):
                continue
            seen.add(qid)
            valid.append({**q, "id": qid, "answers": answers, "correct": correct})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(valid, key=lambda x: x["id"])


BREED_DATA = read_json(BREEDS_FILE, [])
QUESTION_DATA = load_questions()


def init_state():
    defaults = {
        "breed_quiz": [], "breed_pos": 0, "breed_score": 0,
        "breed_answers": [], "breed_checked": False, "breed_seed": 0,
        "theory_quiz": [], "theory_pos": 0, "theory_score": 0,
        "theory_answers": [], "theory_checked": False, "theory_seed": 0,
        "theory_retry_mode": False, "theory_history": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


def four_options(correct, pool, rng):
    others = [x for x in pool if x != correct]
    chosen = rng.sample(others, min(3, len(others)))
    answers = chosen + [correct]
    rng.shuffle(answers)
    return answers


def start_breed_quiz(count, groups):
    available = [i for i, d in enumerate(BREED_DATA) if d.get("group") in groups]
    rng = random.Random()
    rng.shuffle(available)
    st.session_state.breed_quiz = available[:min(count, len(available))]
    st.session_state.breed_pos = 0
    st.session_state.breed_score = 0
    st.session_state.breed_answers = []
    st.session_state.breed_checked = False
    st.session_state.breed_seed = rng.randrange(1_000_000_000)


def start_theory_quiz(count, difficulties, tickets, topics, source_ids=None, retry=False):
    pool = [q for q in QUESTION_DATA if q.get("difficulty", 1) in difficulties]
    if tickets:
        pool = [q for q in pool if q.get("tetel", "") in tickets]
    if topics:
        pool = [q for q in pool if q.get("tema", "") in topics]
    if source_ids is not None:
        wanted = set(source_ids)
        pool = [q for q in pool if q["id"] in wanted]
    rng = random.Random()
    rng.shuffle(pool)
    st.session_state.theory_quiz = [q["id"] for q in pool[:min(count, len(pool))]]
    st.session_state.theory_pos = 0
    st.session_state.theory_score = 0
    st.session_state.theory_answers = []
    st.session_state.theory_checked = False
    st.session_state.theory_seed = rng.randrange(1_000_000_000)
    st.session_state.theory_retry_mode = retry


def save_theory_run():
    if not st.session_state.theory_answers:
        return
    total = len(st.session_state.theory_answers)
    correct = sum(r["Helyes"] for r in st.session_state.theory_answers)
    record = {
        "Időpont": datetime.now().isoformat(timespec="seconds"),
        "Mód": "Hibás kérdések ismétlése" if st.session_state.theory_retry_mode else "Normál teszt",
        "Kérdések": total,
        "Helyes": correct,
        "Százalék": round(correct * 100 / total, 1) if total else 0,
    }
    st.session_state.theory_history.append(record)
    try:
        old = read_json(STATS_FILE, [])
        if not isinstance(old, list):
            old = []
        old.append(record)
        STATS_FILE.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


st.markdown(
    '<div class="hero"><h1>🐕 Kutyakozmetikus tanuló app</h1>'
    '<p>Fajtafelismerés és az 1.A–19.C szóbeli tételek gyakorlása egy helyen</p></div>',
    unsafe_allow_html=True,
)

breed_tab, theory_tab = st.tabs(["🖼️ Fajtafelismerő", "📚 Tételfelkészítő teszt"])

with breed_tab:
    if not BREED_DATA:
        st.error("A fajtafelismerőhöz hiányzik vagy hibás a breeds.json fájl.")
    else:
        left_cfg, main_area = st.columns([0.28, 0.72], gap="large")
        with left_cfg:
            st.subheader("Gyakorlás beállításai")
            order = ["I","II","III","IV","V","VI","VII","VIII","IX","X"]
            groups_all = sorted({d["group"] for d in BREED_DATA}, key=lambda x: order.index(x) if x in order else 99)
            groups = st.multiselect("Fajtacsoportok", groups_all, default=groups_all, format_func=lambda x:f"{x}. fajtacsoport", key="breed_groups")
            maximum = max(1, sum(d.get("group") in groups for d in BREED_DATA))
            count = st.slider("Kérdések száma", 1, maximum, min(10, maximum), key="breed_count")
            if st.button("Új fajtafelismerő feladatsor", type="primary", use_container_width=True, disabled=not groups):
                start_breed_quiz(count, groups); st.rerun()
            st.caption(f"Adatbázis: {len(BREED_DATA)} fajta")

        with main_area:
            if not st.session_state.breed_quiz:
                st.info("Válaszd ki a fajtacsoportokat, majd indíts új feladatsort.")
            elif st.session_state.breed_pos >= len(st.session_state.breed_quiz):
                maximum_score = len(st.session_state.breed_quiz) * 3
                pct = 100 * st.session_state.breed_score / maximum_score if maximum_score else 0
                st.success(f"Feladatsor kész: **{st.session_state.breed_score}/{maximum_score} pont ({pct:.0f}%)**")
                df = pd.DataFrame(st.session_state.breed_answers)
                if not df.empty:
                    st.dataframe(df, hide_index=True, use_container_width=True)
                    st.download_button("Eredmény CSV letöltése", df.to_csv(index=False).encode("utf-8-sig"), "fajtafelismero_eredmeny.csv", "text/csv", use_container_width=True)
            else:
                pos = st.session_state.breed_pos
                item = BREED_DATA[st.session_state.breed_quiz[pos]]
                rng = random.Random(st.session_state.breed_seed + pos * 7919)
                breeds = [d["breed"] for d in BREED_DATA]
                coats = sorted({d["coat"] for d in BREED_DATA})
                cares = sorted({d["care"] for d in BREED_DATA})
                st.progress(pos / len(st.session_state.breed_quiz), text=f"{pos+1}. kérdés / {len(st.session_state.breed_quiz)} | Pont: {st.session_state.breed_score}")
                image_col, answer_col = st.columns([1.06, 1], gap="large")
                with image_col:
                    image_path = BASE / item["image"]
                    if image_path.exists():
                        st.image(str(image_path), use_container_width=True)
                    else:
                        st.warning(f"A kép nem található: {item['image']}")
                with answer_col:
                    disabled = st.session_state.breed_checked
                    breed = st.radio("1. Milyen fajta?", four_options(item["breed"], breeds, rng), index=None, key=f"breed_{pos}", disabled=disabled)
                    coat = st.radio("2. Milyen szőrtípus?", four_options(item["coat"], coats, rng), index=None, key=f"coat_{pos}", disabled=disabled)
                    care = st.radio("3. Milyen ápolást igényel?", four_options(item["care"], cares, rng), index=None, key=f"care_{pos}", disabled=disabled)
                    if not disabled:
                        if st.button("Válaszok ellenőrzése", type="primary", use_container_width=True, key="breed_check"):
                            if None in (breed, coat, care):
                                st.warning("Mindhárom kérdésre válaszolj!")
                            else:
                                points = sum([breed == item["breed"], coat == item["coat"], care == item["care"]])
                                st.session_state.breed_score += points
                                st.session_state.breed_answers.append({"Sorszám":pos+1,"Helyes fajta":item["breed"],"Fajta":"✓" if breed==item["breed"] else "✗","Szőr":"✓" if coat==item["coat"] else "✗","Ápolás":"✓" if care==item["care"] else "✗","Pont":points})
                                st.session_state.breed_checked = True; st.rerun()
                    else:
                        row = st.session_state.breed_answers[-1]
                        css = "result" if row["Pont"] == 3 else "result wrong"
                        st.markdown(f'<div class="{css}"><b>{row["Pont"]}/3 pont</b><br>Helyes megoldás: <b>{item["breed"]}</b><br>{item["coat"]} • {item["care"]}</div>', unsafe_allow_html=True)
                        if st.button("Következő kérdés →", type="primary", use_container_width=True, key="breed_next"):
                            st.session_state.breed_pos += 1; st.session_state.breed_checked = False; st.rerun()

with theory_tab:
    if not QUESTION_DATA:
        st.error("Nem található kérdésadatbázis. Tedd az app.py mellé a questions_001_500.json fájlt vagy a questions_*.json blokkokat.")
    else:
        q_by_id = {q["id"]: q for q in QUESTION_DATA}
        cfg, content = st.columns([0.3, 0.7], gap="large")
        with cfg:
            st.subheader("Tételteszt beállításai")
            diff_labels = {1:"1 – könnyű", 2:"2 – közepes", 3:"3 – nehéz"}
            difficulties = st.multiselect("Nehézség", [1,2,3], default=[1,2,3], format_func=lambda x:diff_labels[x])
            tickets_all = sorted({q.get("tetel", "") for q in QUESTION_DATA if q.get("tetel") and q.get("tetel") != "Összefoglaló"}, key=lambda x:(int(x.split('.')[0]) if x.split('.')[0].isdigit() else 99, x))
            tickets = st.multiselect("Tételek, opcionális", tickets_all)
            topics_all = sorted({q.get("tema", "") for q in QUESTION_DATA if q.get("tema")})
            topics = st.multiselect("Témakörök, opcionális", topics_all)
            eligible = [q for q in QUESTION_DATA if q.get("difficulty",1) in difficulties and (not tickets or q.get("tetel") in tickets) and (not topics or q.get("tema") in topics)]
            max_count = max(1, len(eligible))
            test_count = st.slider("Kérdések száma", 1, max_count, min(20,max_count), key="theory_count")
            if st.button("Új tételteszt", type="primary", use_container_width=True, disabled=not eligible):
                start_theory_quiz(test_count, difficulties, tickets, topics); st.rerun()
            st.caption(f"Betöltött kérdések: {len(QUESTION_DATA)} | A beállításnak megfelelő: {len(eligible)}")

            st.divider()
            st.subheader("Statisztika")
            history = read_json(STATS_FILE, [])
            combined_history = history if history else st.session_state.theory_history
            if combined_history:
                hdf = pd.DataFrame(combined_history)
                st.metric("Kitöltött tesztek", len(hdf))
                st.metric("Átlagos eredmény", f"{hdf['Százalék'].mean():.1f}%")
                st.download_button("Statisztika letöltése", hdf.to_csv(index=False).encode("utf-8-sig"), "tetelteszt_statisztika.csv", "text/csv", use_container_width=True)
            else:
                st.caption("Még nincs mentett teszteredmény.")

        with content:
            if not st.session_state.theory_quiz:
                st.info("Állítsd be a nehézséget és a kérdésszámot, majd indíts új tételtesztet.")
            elif st.session_state.theory_pos >= len(st.session_state.theory_quiz):
                total = len(st.session_state.theory_answers)
                correct_n = st.session_state.theory_score
                pct = 100 * correct_n / total if total else 0
                if not st.session_state.get("theory_run_saved", False):
                    save_theory_run(); st.session_state.theory_run_saved = True
                st.success(f"Teszt kész: **{correct_n}/{total} helyes válasz ({pct:.0f}%)**")
                df = pd.DataFrame(st.session_state.theory_answers)
                wrong = df[~df["Helyes"]] if not df.empty else pd.DataFrame()
                c1,c2,c3 = st.columns(3)
                c1.metric("Helyes", correct_n)
                c2.metric("Hibás", total-correct_n)
                c3.metric("Eredmény", f"{pct:.0f}%")
                if not wrong.empty:
                    st.subheader("Hibás kérdések")
                    st.dataframe(wrong[["ID","Tétel","Kérdés","Saját válasz","Helyes válasz","Magyarázat"]], hide_index=True, use_container_width=True)
                    if st.button("Csak a hibás kérdések újra", type="primary", use_container_width=True):
                        ids = wrong["ID"].astype(int).tolist()
                        start_theory_quiz(len(ids), [1,2,3], [], [], source_ids=ids, retry=True)
                        st.session_state.theory_run_saved = False; st.rerun()
                else:
                    st.balloons(); st.info("Minden válasz helyes volt, nincs ismétlendő kérdés.")
                if not df.empty:
                    st.download_button("Részletes eredmény letöltése", df.to_csv(index=False).encode("utf-8-sig"), "tetelteszt_eredmeny.csv", "text/csv", use_container_width=True)
                if st.button("Új teszt indítása", use_container_width=True):
                    st.session_state.theory_quiz=[]; st.session_state.theory_run_saved=False; st.rerun()
            else:
                pos = st.session_state.theory_pos
                item = q_by_id[st.session_state.theory_quiz[pos]]
                st.progress(pos/len(st.session_state.theory_quiz), text=f"{pos+1}. kérdés / {len(st.session_state.theory_quiz)} | Pont: {st.session_state.theory_score}")
                st.caption(f"Tétel: {item.get('tetel','–')} | Téma: {item.get('tema','–')} | Nehézség: {item.get('difficulty',1)}/3")
                st.markdown(f"### {item['question']}")
                answer = st.radio("Válassz egy választ:", item["answers"], index=None, key=f"theory_{item['id']}_{pos}", disabled=st.session_state.theory_checked)
                if not st.session_state.theory_checked:
                    if st.button("Válasz ellenőrzése", type="primary", use_container_width=True, key="theory_check"):
                        if answer is None:
                            st.warning("Jelölj meg egy választ!")
                        else:
                            selected_idx = item["answers"].index(answer)
                            is_correct = selected_idx == item["correct"]
                            st.session_state.theory_score += int(is_correct)
                            st.session_state.theory_answers.append({"ID":item["id"],"Tétel":item.get("tetel",""),"Téma":item.get("tema",""),"Nehézség":item.get("difficulty",1),"Kérdés":item["question"],"Saját válasz":answer,"Helyes válasz":item.get("correct_answer", item["answers"][item["correct"]]),"Helyes":is_correct,"Magyarázat":item.get("explanation","")})
                            st.session_state.theory_checked=True; st.rerun()
                else:
                    row=st.session_state.theory_answers[-1]
                    css="result" if row["Helyes"] else "result wrong"
                    label="Helyes válasz" if row["Helyes"] else "Hibás válasz"
                    st.markdown(f'<div class="{css}"><b>{label}</b><br>Helyes megoldás: <b>{row["Helyes válasz"]}</b><br><span class="smallmuted">{row["Magyarázat"]}</span></div>',unsafe_allow_html=True)
                    if st.button("Következő kérdés →", type="primary", use_container_width=True, key="theory_next"):
                        st.session_state.theory_pos += 1; st.session_state.theory_checked=False; st.rerun()
