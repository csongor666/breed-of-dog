# Kutyafajta-felismerő Streamlit app

## Funkciók

- 86 fajta a mellékelt PDF alapján
- 4 kérdés képenként: fajta, szőrtípus, ápolás, fajtacsoport
- A fajtacsoportnál 3 válaszlehetőség
- Könnyű szint: véletlenszerű válaszok
- Közepes szint: hasonló fajtákból képzett fajtaopciók
- Mester szint: mind a négy választ kézzel kell beírni
- A hibás kérdések külön újragyakorolhatók
- CSV eredményexport

## Indítás Windows alatt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
