from fonctions.CommonFunctions import *
from fonctions.data import Data 
import matplotlib.pyplot as plt
import json

def save_JSON(data, solution, fileName):
    taches = []
    
    t_ij, c_ij, Cmax, deg, y, i_s, Qj, nbMaintenance = completionTime(data,solution)
    
    for ind in range(sum(data.nbOperationsParJob)):
        k = solution[1][ind]
        j = solution[0][ind]
        i = i_s[ind]
        start = t_ij[j][i]
        end = c_ij[j][i]
        machine = k
        taches.append(dict(task=f"Machine {machine+1}",
                     start=start,
                     end=end,
                     rsc=f"J{j+1}",
                     label="$O_{%d,%d}$" % (j+1,i+1),
                     info=f"J{j+1}"))
    ############
    for ind in range(sum(data.nbOperationsParJob)):
        for k in range(data.nbMachines):
            for l in range(data.nbComposants[k]):
                i = i_s[ind]
                j = solution[0][ind]
                k_ = solution[1][ind]
                if (y[l][j][i] and k == k_):
                    for ind_ in range(ind+1, sum(data.nbOperationsParJob)):
                        if solution[1][ind_] == k_ :
                            machine = k+1
                            composant = l+1
                            start_time = c_ij[j][i]
                            finish_time = start_time + data.dureeMaintenances[k][l]
                            tache = dict(task=f"Machine {machine}", 
                                         start=start_time, 
                                         end=finish_time, 
                                         rsc=f"Maintenances",
                                         label=f"M", 
                                         info=f"Composant : {composant} (durée={data.dureeMaintenances[k][l]})")
                            taches.append(tache)
                            break
            
    taches = sorted(taches, key=lambda x: x['task'])

    data = {
        "Cmax_x": Cmax,
        "fig": taches,
        "quality": Qj,
        "degradations": deg
    }
    
    # Écrire les données dans un fichier JSON
    with open(fileName, 'w') as json_file:
        json.dump(data, json_file, indent=4)


def lire_fichier_json(chemin_fichier):
    with open(chemin_fichier, 'r') as fichier:
        data = json.load(fichier)

    # Afficher le contenu de chaque clé principale
    print("Cmax_x:", data["Cmax_x"])
    
    for item in data["fig"]:
        if (item['rsc'] != "Maintenances"):
            print(f"  Task: {item['task']}, Start: {item['start']}, End: {item['end']}, Resource: {item['rsc']}, Label: {item['label']}, Info: {item['info']}")
    
    print("\nQuality:")
    for quality_list in data["quality"]:
        print(" ", quality_list)
    
    print("\nDegradations:")
    for degradation_list in data["degradations"]:
        for sublist in degradation_list:
            print(" ", sublist)

    return data
    

if __name__ == "__main__": 
    lire_fichier_json(f"ComplexSystems/TESTS/k1/instance01/meta_heuristic_result.json")