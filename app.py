import json, random
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Kutyafajta-felismerő", page_icon="🐕", layout="wide")
BASE=Path(__file__).parent
DATA=json.loads((BASE/"breeds.json").read_text(encoding="utf-8"))

st.markdown("""<style>
.block-container{max-width:1100px;padding-top:1.4rem}.hero{padding:1.1rem 1.35rem;border-radius:18px;background:linear-gradient(120deg,#17324d,#2d6a78);color:white;margin-bottom:1rem}.hero h1{margin:0;font-size:2.05rem}.hero p{margin:.35rem 0 0;opacity:.88}.question{font-size:1.05rem;font-weight:700;margin:.35rem 0}.stButton button{border-radius:10px;font-weight:650}.result{padding:.75rem 1rem;border-radius:12px;background:#eef8f2;border-left:5px solid #2e8b57}.wrong{background:#fff3f1;border-left-color:#c94c4c}.smallmuted{color:#65717c;font-size:.9rem}</style>""",unsafe_allow_html=True)

BREEDS=[d["breed"] for d in DATA]
COATS=sorted({d["coat"] for d in DATA})
CARES=sorted({d["care"] for d in DATA})

def four_options(correct,pool,rng):
    others=[x for x in pool if x!=correct]
    chosen=rng.sample(others,min(3,len(others)))
    ans=chosen+[correct]; rng.shuffle(ans); return ans

def new_quiz(count,groups,seed=None):
    available=[i for i,d in enumerate(DATA) if d["group"] in groups]
    rng=random.Random(seed)
    rng.shuffle(available)
    q=available[:min(count,len(available))]
    st.session_state.quiz=q; st.session_state.pos=0; st.session_state.score=0
    st.session_state.answers=[]; st.session_state.checked=False; st.session_state.seed=rng.randrange(1_000_000_000)

def init():
    for k,v in {"quiz":[],"pos":0,"score":0,"answers":[],"checked":False,"seed":0}.items():
        if k not in st.session_state: st.session_state[k]=v
init()

st.markdown('<div class="hero"><h1>🐕 Kutyafajta-felismerő</h1><p>Fajta, szőrtípus és a szükséges ápolási mód felismerése képről</p></div>',unsafe_allow_html=True)

with st.sidebar:
    st.header("Gyakorlás beállításai")
    all_groups=sorted({d["group"] for d in DATA},key=lambda x:["I","II","III","IV","V","VI","VII","VIII","IX","X"].index(x))
    groups=st.multiselect("Fajtacsoportok",all_groups,default=all_groups,format_func=lambda x:f"{x}. fajtacsoport")
    maxn=max(1,sum(d["group"] in groups for d in DATA))
    count=st.slider("Kérdések száma",1,maxn,min(10,maxn))
    if st.button("Új feladatsor",type="primary",use_container_width=True,disabled=not groups): new_quiz(count,groups)
    st.caption(f"Adatbázis: {len(DATA)} fajta, {len(all_groups)} fajtacsoport")
    st.divider()
    st.markdown("**Pontozás:** minden képnél 3 pont szerezhető: fajta + szőrtípus + ápolás.")

if not st.session_state.quiz:
    st.info("Válaszd ki a fajtacsoportokat, majd kattints az **Új feladatsor** gombra.")
    st.stop()

if st.session_state.pos>=len(st.session_state.quiz):
    maximum=len(st.session_state.quiz)*3
    pct=100*st.session_state.score/maximum if maximum else 0
    st.success(f"Feladatsor kész! Eredmény: **{st.session_state.score}/{maximum} pont ({pct:.0f}%)**")
    df=pd.DataFrame(st.session_state.answers)
    if not df.empty:
        st.dataframe(df[["Sorszám","Helyes fajta","Fajta","Szőr","Ápolás","Pont"]],hide_index=True,use_container_width=True)
        st.download_button("Eredmények letöltése CSV-ben",df.to_csv(index=False).encode("utf-8-sig"),"fajtafelismero_eredmeny.csv","text/csv",use_container_width=True)
    if st.button("Ugyanez új sorrendben",type="primary"): new_quiz(len(st.session_state.quiz),groups)
    st.stop()

pos=st.session_state.pos
item=DATA[st.session_state.quiz[pos]]
qseed=st.session_state.seed+pos*7919
rng=random.Random(qseed)
breed_opts=four_options(item["breed"],BREEDS,rng)
coat_opts=four_options(item["coat"],COATS,rng)
care_opts=four_options(item["care"],CARES,rng)

st.progress(pos/len(st.session_state.quiz),text=f"{pos+1}. kérdés / {len(st.session_state.quiz)} | Pont: {st.session_state.score}")
left,right=st.columns([1.06,1],gap="large")
with left:
    st.image(str(BASE/item["image"]),use_container_width=True)
    st.markdown('<p class="smallmuted">A képet a mellékelt fajtafelismerési PDF-ből nyertük ki.</p>',unsafe_allow_html=True)
with right:
    disabled=st.session_state.checked
    breed=st.radio("1. Milyen fajta látható a képen?",breed_opts,index=None,key=f"breed_{pos}",disabled=disabled)
    coat=st.radio("2. Milyen szőrtípusa van?",coat_opts,index=None,key=f"coat_{pos}",disabled=disabled)
    care=st.radio("3. Milyen ápolást igényel?",care_opts,index=None,key=f"care_{pos}",disabled=disabled)
    if not st.session_state.checked:
        if st.button("Válaszok ellenőrzése",type="primary",use_container_width=True):
            if None in (breed,coat,care): st.warning("Mindhárom kérdésre válaszolj!")
            else:
                points=sum([breed==item["breed"],coat==item["coat"],care==item["care"]])
                st.session_state.score+=points
                st.session_state.answers.append({"Sorszám":pos+1,"Helyes fajta":item["breed"],"Fajta":"✓" if breed==item["breed"] else "✗","Szőr":"✓" if coat==item["coat"] else "✗","Ápolás":"✓" if care==item["care"] else "✗","Pont":points})
                st.session_state.checked=True; st.rerun()
    else:
        b=st.session_state.answers[-1]
        cls="result" if b["Pont"]==3 else "result wrong"
        st.markdown(f'<div class="{cls}"><b>{b["Pont"]}/3 pont</b><br>Helyes megoldás: <b>{item["breed"]}</b><br>{item["coat"]} • {item["care"]}<br><span class="smallmuted">{item["group"]}. fajtacsoport</span></div>',unsafe_allow_html=True)
        if st.button("Következő kérdés →",type="primary",use_container_width=True):
            st.session_state.pos+=1; st.session_state.checked=False; st.rerun()
