from fonctions.CommonFunctions import *
from fonctions.data import Data 
import matplotlib.pyplot as plt
import json
import numpy as np

def convert_ndarray_to_list(obj):
    if isinstance(obj, dict):
        return {k: convert_ndarray_to_list(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_ndarray_to_list(x) for x in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def save_JSON(data, solution, fileName,weights):
    taches = []
    
    t_ij, c_ij, Cmax, deg, y, i_s, Qj, cout,nbMaintenance,outqual,penality = completionTime(data,solution,weights)
    print(" y:")
    for i,s in enumerate(y):
        print(s)
    print("solution[2]:")
    for i,s in enumerate(solution[2]):
        print(s)
    for ind in range(sum(data.nbOperationsParJob)):
        k = solution[1][ind]
        j = solution[0][ind]
        i = i_s[ind]
        start = t_ij[j][i]
        end = c_ij[j][i]
        machine = k+1
        taches.append(dict(task=f"Machine {machine}",
                     start=t_ij[j][i],
                     end=c_ij[j][i],
                     rsc=f"J{j+1}",
                     label="$O_{%d,%d}$" % (j+1,i+1),
                     info=f"J{j+1}"))
    ############
    
    for k in range(data.nbMachines):
        for l in range(data.nbComposants[k]):
            for ind in range(sum(data.nbOperationsParJob)):
                i = i_s[ind]
                j = solution[0][ind]
                #k_ = solution[1][ind]
                if (y[l][j][i] and solution[1][ind]==k):
                    machine = k+1
                    composant = l+1
                    start_time = c_ij[j][i]
                    finish_time = start_time + data.dureeMaintenances[k][l]
                    tache = dict(task=f"Machine {machine}", 
                                 start=start_time, 
                                 end=finish_time, 
                                 rsc=f"Maintenances",
                                 label=f"M", 
                                 info=f"Composant : {composant} (duree={data.dureeMaintenances[k][l]})")
                    taches.append(tache)
                    """
                    for ind_ in range(ind, sum(data.nbOperationsParJob)):
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
                                         info=f"Composant : {composant} (duree={data.dureeMaintenances[k][l]})")
                            taches.append(tache)
                            break
                    """
    taches = sorted(taches, key=lambda x: (x["task"], x["start"],x["end"]))
    data = {
        "Cmax_x": Cmax,
        "fig": taches,
        "quality": Qj,
        "degradations": deg
    }
    
    #dumped = json.dumps(data, cls=NumpyEncoder)
    #with open(fileName, 'w') as f:
    #    json.dump(dumped, f)
    # Écrire les données dans un fichier JSON
    data = convert_ndarray_to_list(data)
    with open(fileName, 'w') as json_file:
        json.dump(data, json_file, indent=4)


def lire_fichier_json(chemin_fichier):
    with open(chemin_fichier, 'r') as fichier:
        data = json.load(fichier)
    return data
def afficher_fichier_json(data):
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

    


if __name__ == "__main__": 
    lire_fichier_json(f"ComplexSystems/TESTS/k1/instance01/meta_heuristic_result.json")