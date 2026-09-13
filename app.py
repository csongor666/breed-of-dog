import json
import random
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


def init():
    defaults = {"quiz": [], "pos": 0, "score": 0, "answers": [], "checked": False,
                "seed": 0, "difficulty_active": "Könnyű"}
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
    st.stop()

# Final results and targeted retry.
if st.session_state.pos >= len(st.session_state.quiz):
    maximum = len(st.session_state.quiz) * 4
    percent = 100 * st.session_state.score / maximum if maximum else 0
    st.success(f"Feladatsor kész! Eredmény: **{st.session_state.score}/{maximum} pont ({percent:.0f}%)**")
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
