import json
import os
import random

class Ingredient:
    def __init__(self, d):
        self.id = d.get('id')
        self.nume = d['nume']
        self.nutrienti = d['nutrienti_per_100g']
        self.pret = d['pret_mediu_per_100g'] if d.get('pret_mediu_per_100g') is not None else 1.5
        self.disponibilitate = d['disponibilitate'] if d.get('disponibilitate') is not None else 4
        
        self.alergeni = [a.lower() for a in d.get('alergeni', [])]

    def are_alergeni(self, lista_u):
        for a in lista_u:
            if a.lower() in self.alergeni:
                return True  
        return False 

class Reteta:
    def __init__(self, d, ing_dict):
        self.id = d['id']
        self.nume = d['nume_reteta']
        self.perioada = [p.lower() for p in d['perioade_zi']]
        self.ingrediente_info = d['ingrediente']
        self.calorii_baza = 0
        self.pret_baza = 0
        self.disp_totala = 0
        self.nutrienti_baza = {}
        self._calculeaza_statistici(ing_dict)

    def _calculeaza_statistici(self, ing_dict):
        for item in self.ingrediente_info:
            ing = ing_dict.get(item['nume'])
            if ing:
                f = item['cantitate_g'] / 100
                self.calorii_baza += ing.nutrienti.get('energie_kcal', 0) * f
                self.pret_baza += ing.pret * f
                self.disp_totala += ing.disponibilitate
                for n, val in ing.nutrienti.items():
                    self.nutrienti_baza[n] = self.nutrienti_baza.get(n, 0) + val * f
        
        if self.calorii_baza == 0:
            self.calorii_baza = 450.0  
            
        if self.ingrediente_info:
            self.disp_medie = self.disp_totala / len(self.ingrediente_info)
        else:
            self.disp_medie = 3.0

def interfata(intr):
    with open(intr, 'r', encoding='utf-8') as f:
        intrebari = json.load(f)

    raspunsuri = {}
    for i in intrebari:
        print(f"\n[{i['sectiune']}]")

        if i['tip'] == 'alegere':
            optiuni_str = ", ".join(i['optiuni'])
            print(f"{i['intrebare']}\nOpțiuni: {optiuni_str}")
        else:
            print(i['intrebare'])
    
        ans = input("Răspuns: ").strip()
        
        key_map = {
            1: 'varsta', 
            2: 'gen', 
            3: 'greutate', 
            4: 'inaltime', 
            5: 'buget', 
            6: 'alergii', 
            7: 'obiectiv', 
            8: 'deficienta',
            9: 'stil de viata'
        }
        k = key_map.get(i['id'])

        if k == 'alergii':
            list_alergeni = []
            if ans and ans.lower() != 'nu':
                bucati = ans.split(',')
                for j in bucati:
                    list_alergeni.append(j.strip().lower())
            raspunsuri[k] = list_alergeni
        else:
            raspunsuri[k] = ans
    
    age_str = raspunsuri.get('varsta', "0")
    age = int(age_str)
    
    if age < 12:
        a = 'copil'
    elif age < 18:
        a = 'adolescent'
    elif age < 55:
        a = 'adult'
    else:
        a = 'senior'

    profil_final = {
        "utilizator": {
            "nume": "Utilizator",
            "biometrie": {
                "varsta": int(raspunsuri.get('varsta', 0)),
                "inaltime": raspunsuri.get('inaltime'),
                "greutate": raspunsuri.get('greutate'),
                "gen": raspunsuri.get('gen')
            }
        },
        "restrictii": {
            "obiectiv": raspunsuri.get('obiectiv', 'sa imi pastrez greutatea actuala'),
            "alergeni": raspunsuri.get('alergii', []),
            "grupa_varsta": a,  
            "buget_maxim": float(raspunsuri.get('buget', 0)),
            "deficienta": raspunsuri.get('deficienta', '').lower().strip(),
            "stil_de_viata": raspunsuri.get('stil de viata', 'activ')
        }
    }

    with open('profil_utilizator.json', 'w', encoding='utf-8') as f:
        json.dump(profil_final, f, indent=4)

    return profil_final

class SolverDieta:
    def __init__(self, retete, ingrediente, profil, k_param=2):
        self.retete = retete
        self.ingrediente = ingrediente
        self.profil = profil
        self.k = k_param
        self.plan_final = {}
        
        bio = profil['utilizator']['biometrie']
        g = float(bio.get('greutate', 70))
        
        stil = profil['restrictii'].get('stil_de_viata', 'activ').lower()
        if 'sedentar' in stil:
            multiplicator = 25  
        elif 'usoara' in stil:
            multiplicator = 28
        elif 'foarte' in stil:
            multiplicator = 35  
        else:
            multiplicator = 31 
            
        self.tinta_kcal = g * multiplicator
        
        obj = profil['restrictii'].get('obiectiv', 'sa imi pastrez greutatea actuala').lower()
        if "slab" in obj:
            self.tinta_kcal -= 500
        elif "ingras" in obj:
            self.tinta_kcal += 500
        
        if self.tinta_kcal < 1300:
            self.tinta_kcal = 1300
        
        self.deficienta = profil['restrictii'].get('deficienta', '').lower().strip()
        if self.deficienta in ['nu', 'none', '-', '', 'nu am']:
            self.deficienta = None
            
        self.buget_maxim = profil['restrictii'].get('buget_maxim', 9999.0)
        
        self.valori_dv = {
            "vitamina_c_mg": 90.0,
            "calciu_mg": 1300.0,  
            "fier_mg": 18.0,      
            "proteine_g": 50.0   
        }

    def rezolva(self, nr_sapt):
        for s in range(nr_sapt):
            print(f"Generăm săptămâna {s+1}...")
            self.istoric_folosire_retete = {} 
            succes = self._backtracking_saptamana(s)
            if not succes:
                print(f" Eroare săptămâna {s+1}")
                return {}
        return self.plan_final

    
    def _backtracking_saptamana(self, s_idx):
        slots = [(z, m) for z in range(7) for m in ["pranz", "seara", "dimineata"]]
        
        asignare_initiala = {}

        def selecteaza_variabila_neasignata(asignare):
            cel_mai_bun_slot = None
            min_optiuni = float('inf')

            for slot in slots:
                if slot in asignare:
                    continue  

                zi, tip = slot
                retete_azi = [asignare[(zi, m)]['r'].id for m in ["dimineata", "pranz", "seara"] if (zi, m) in asignare]
                
                nr_valori_ramase = 0
                for r in self.retete:
                    if tip in r.perioada and r.id not in retete_azi:
                        ultima_zi = self.istoric_folosire_retete.get(r.id, -10)
                        if zi - ultima_zi > 7:
                            nr_valori_ramase += 1
                
                if nr_valori_ramase < min_optiuni:
                    min_optiuni = nr_valori_ramase
                    cel_mai_bun_slot = slot

            return cel_mai_bun_slot

        def ordoneaza_valori_domeniu(var, asignare):
            zi, tip = var
            optiuni = []
            retete_azi = [asignare[(zi, m)]['r'].id for m in ["dimineata", "pranz", "seara"] if (zi, m) in asignare]

            for r in self.retete:
                if tip in r.perioada and r.id not in retete_azi:
                    ultima_zi = self.istoric_folosire_retete.get(r.id, -10)
                    if zi - ultima_zi > 7:
                        optiuni.append(r)
            if self.deficienta and self.deficienta in ["vitamina_c_mg", "calciu_mg", "fier_mg", "proteine_g"]:
                optiuni.sort(key=lambda x: x.nutrienti_baza.get(self.deficienta, 0), reverse=True)
            else:
                optiuni.sort(key=lambda x: (x.disp_medie * 10) - (x.pret_baza * 0.3), reverse=True)

            if len(optiuni) > 1:
                top_k = optiuni[:4]
                random.shuffle(top_k)
                optiuni = top_k + optiuni[4:]

            valori_domeniu = []
            for r in optiuni:
                dist = {"dimineata": 0.25, "pranz": 0.45, "seara": 0.30}
                factor = (self.tinta_kcal * dist[tip]) / r.calorii_baza if r.calorii_baza > 0 else 1.0
                if 0.25 <= factor <= 4.0:
                    valori_domeniu.append({"r": r, "f": factor})
            
            return valori_domeniu

        def este_consistenta(var, valoare, asignare):
            zi, tip = var
            
            asignare_simulata = asignare.copy()
            asignare_simulata[var] = valoare

            if (zi, "dimineata") in asignare_simulata and (zi, "pranz") in asignare_simulata and (zi, "seara") in asignare_simulata:
                calorii_zi = sum(asignare_simulata[(zi, m)]['r'].calorii_baza * asignare_simulata[(zi, m)]['f'] for m in ["dimineata", "pranz", "seara"])
                marja = 0.10
                if not ((self.tinta_kcal * (1 - marja)) <= calorii_zi <= (self.tinta_kcal * (1 + marja))):
                    return False

            zile_completate = len({z for (z, m) in asignare_simulata.keys()})
            cost_acumulat = sum(v['r'].pret_baza * v['f'] for v in asignare_simulata.values())
            buget_partial = (self.buget_maxim / 7) * zile_completate
            if self.buget_maxim > 0 and cost_acumulat > buget_partial:
                return False

            return True
        def backtracking_recursiv(asignare):
            if len(asignare) == len(slots):
                if self._validare_finala(asignare):
                    return asignare
                return "eșec"

            var = selecteaza_variabila_neasignata(asignare)
            if not var:
                return "eșec"
            for valoare in ordoneaza_valori_domeniu(var, asignare):
                if este_consistenta(var, valoare, asignare):
                    asignare[var] = valoare
                    zi, tip = var
                    zi_veche = self.istoric_folosire_retete.get(valoare['r'].id)
                    self.istoric_folosire_retete[valoare['r'].id] = zi
                    rezultat = backtracking_recursiv(asignare)
                    
                    if rezultat != "eșec":
                        return rezultat
                    del asignare[var]
                    if zi_veche is not None:
                        self.istoric_folosire_retete[valoare['r'].id] = zi_veche
                    else:
                        self.istoric_folosire_retete.pop(valoare['r'].id, None)

            return "eșec"

        solutie = backtracking_recursiv(asignare_initiala)
        
        if solutie != "eșec":
            for cheie, data in solutie.items():
                self.plan_final[(s_idx, cheie[0], cheie[1])] = data
            return True
        return False

    def _validare_finala(self, solutie):
        suma_disp = sum(v['r'].disp_medie for v in solutie.values())
        if (suma_disp / 21) < 3:
            return False 
        
        cost_total_real = sum(v['r'].pret_baza * v['f'] for v in solutie.values())
        if self.buget_maxim > 0 and cost_total_real > self.buget_maxim:
            return False
        
        return True

    def alege_suplimente_k(self, zi_idx):
        alergeni_u = self.profil['restrictii'].get('alergeni', [])
        valide = []
        for i in self.ingrediente:
            if not i.are_alergeni(alergeni_u):
                valide.append(i)
        
        if self.deficienta:
            valide.sort(key=lambda x: x.nutrienti.get(self.deficienta, 0), reverse=True)
            return valide[:self.k]
        
        if len(valide) < self.k:
            return valide
        return random.sample(valide, self.k)

def main():
    if os.path.exists('profil_utilizator.json'):
        with open('profil_utilizator.json', 'r', encoding='utf-8') as f:
            profil = json.load(f)
        if 'restrictii' not in profil or 'stil_de_viata' not in profil['restrictii']:
            print("Profil vechi sau invalid detectat")
            profil = interfata("intrebari_utilizator.json")
    else:
        print("\nProfilul nu a fost găsit")
        profil = interfata("intrebari_utilizator.json")

    with open('ingrediente.json', 'r', encoding='utf-8') as f:
        date_i = json.load(f)
    with open('retete.json', 'r', encoding='utf-8') as f:
        date_r = json.load(f)

    ing_dict = {i['nume']: Ingredient(i) for i in date_i}
    
    alergeni_u = profil['restrictii'].get('alergeni', [])
    retete_valide = []
    for r_json in date_r:
        r_obj = Reteta(r_json, ing_dict)
        are_alergeni_in_reteta = False
        for i in r_obj.ingrediente_info:
            nume_ing = i['nume']
            if nume_ing in ing_dict and ing_dict[nume_ing].are_alergeni(alergeni_u):
                are_alergeni_in_reteta = True
                break
        if not are_alergeni_in_reteta:
            retete_valide.append(r_obj)
            
    lista_ingrediente = list(ing_dict.values())

    solver = SolverDieta(retete_valide, lista_ingrediente, profil, k_param=2)
    nr_sapt = int(input("\nCâte săptămâni doriți planul alimentar (1-4)? "))
    plan = solver.rezolva(nr_sapt)

    if not plan:
        print("Nu s-a putut genera un plan conform constrângerilor.")
        return

    for s in range(nr_sapt):
        print(f"\n{'='*20} PLAN SĂPTĂMÂNA {s+1} {'='*20}")
        for z in range(7):
            print(f"\n--- Ziua {z+1} ---")
            total_kcal_zi = 0
            ord_afisare = ["dimineata", "pranz", "seara"]
            for m in ord_afisare:
                d = plan.get((s, z, m))
                if d:
                    kcal = d['r'].calorii_baza * d['f']
                    total_kcal_zi += kcal
                    print(f" [{m.upper()}] {d['r'].nume} (Scalat x{d['f']:.2f}) -> {kcal:.0f} kcal")

            sup = solver.alege_suplimente_k(z)
            print(f" GUSTĂRI (K={solver.k}): {', '.join([i.nume for i in sup])}")
            print(f" Total Calorii Zi: {total_kcal_zi:.0f} kcal (Țintă: {solver.tinta_kcal:.0f} kcal)")

if __name__ == "__main__":
    main()