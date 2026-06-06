from flask import Flask, render_template, request
import json
import os
from dieta import Ingredient, Reteta, SolverDieta

app = Flask(__name__)

with open('ingrediente.json', 'r', encoding='utf-8') as f:
    date_i = json.load(f)
with open('retete.json', 'r', encoding='utf-8') as f:
    date_r = json.load(f)

ing_dict = {i['nume']: Ingredient(i) for i in date_i}

@app.route('/')
def home():
    profil_existent = None
    if os.path.exists('profil_utilizator.json'):
        try:
            with open('profil_utilizator.json', 'r', encoding='utf-8') as f:
                profil_existent = json.load(f)
        except:
            pass 

    return render_template('formular.html', profil=profil_existent)

@app.route('/genereaza', methods=['POST'])
def genereaza_dieta():
    greutate = float(request.form.get('greutate', 55))
    varsta = int(request.form.get('varsta', 21))
    inaltime = request.form.get('inaltime', '168')
    gen = request.form.get('gen', 'feminin')
    buget = float(request.form.get('buget', 500))
    
    obiectiv = request.form.get('obiectiv', '').strip().lower()
    deficienta = request.form.get('deficienta', 'nu').strip().lower()
    
    alergii_raw = request.form.get('alergii', '')
    alergeni_utilizator = [a.strip().lower() for a in alergii_raw.split(',')] if alergii_raw and alergii_raw.lower() != 'nu' else []
    
    age = int(varsta)
    if age < 12: a = 'copil'
    elif age < 18: a = 'adolescent'
    elif age < 55: a = 'adult'
    else: a = 'senior'

    profil = {
        "utilizator": {
            "nume": "Utilizator",
            "biometrie": {"varsta": varsta, "inaltime": inaltime, "greutate": greutate, "gen": gen}
        },
        "restrictii": {
            "obiectiv": obiectiv,
            "alergeni": list(set(alergeni_utilizator)),
            "grupa_varsta": a,
            "buget_maxim": buget,
            "deficienta": deficienta,
            "stil_de_viata": request.form.get('stil_de_viata', 'activ')
        }
    }
    
    with open('profil_utilizator.json', 'w', encoding='utf-8') as f:
        json.dump(profil, f, indent=4)

    retete_valide = []
    for r_json in date_r:
        r_obj = Reteta(r_json, ing_dict)
        are_alergie = False
        for i in r_obj.ingrediente_info:
            if i['nume'] in ing_dict and ing_dict[i['nume']].are_alergeni(profil['restrictii']['alergeni']):
                are_alergie = True
                break
        if not are_alergie:
            retete_valide.append(r_obj)

    nr_saptamani = int(request.form.get('saptamani', 2))
    
    solver = SolverDieta(retete_valide, list(ing_dict.values()), profil)
    plan_alimentar = solver.rezolva(nr_saptamani)

    if not plan_alimentar:
        return "Nu s-a putut genera un plan dietetic conform constrângerilor introduse. Încearcă să mărești bugetul sau să scoți din alergii!"

    return render_template('rezultat.html', plan=plan_alimentar, nr_sapt=nr_saptamani, tinta_kcal=solver.tinta_kcal, solver=solver)

if __name__ == '__main__':
    app.run(debug=True)