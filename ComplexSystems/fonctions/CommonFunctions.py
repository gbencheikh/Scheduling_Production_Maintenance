import copy

def parse_degradations_file(filename, inf=99999):
    line_num = 0
    # Lire les lignes du fichier
    with open(filename, 'r') as file:
        lines = file.readlines()
    # Extraire nbJobs et nbMachines de la première ligne
    first_line = lines[line_num].split()
    line_num+=1
    nbJobs = int(first_line[0])
    nbMachines = int(first_line[1])
    # Initialiser les listes pour stocker les données
    nbComposants = [1 for _ in range(nbMachines)]
    seuils_degradation = [[] for _ in range(nbMachines)]
    dureeMaintenances = [[] for _ in range(nbMachines)]
    degradations = [[] for _ in range(nbMachines)]
    degradations_2 = []

    # Parcourir les lignes restantes pour extraire les données
    for loop1 in range(nbMachines):
        line = lines[line_num]
        line_num+=1
        idmac,nbjmac,nbcmp = list(map(int, line.split()))
        nbComposants[idmac] = nbcmp
        seuils_degradation[idmac] = [0 for _ in range(nbcmp)]
        dureeMaintenances[idmac] = [0 for _ in range(nbcmp)]
        degradations[idmac] = [[[] for __ in range(nbJobs)] for _ in range(nbcmp)]
        
        for loop2 in range(nbcmp):
            line = lines[line_num]
            line_num+=1
            idcmp, seuil, dureemaint = list(map(int, line.split()))
            seuils_degradation[idmac][idcmp] = seuil
            dureeMaintenances[idmac][idcmp] = dureemaint
            
            for loop3 in range(nbjmac):
                col_num = 0
                line = lines[line_num]
                line_num+=1
                data = list(map(int, line.split()))
                idj = data[col_num]
                col_num+=1
                nbop = data[col_num]
                col_num+=1
                nbopmac = data[col_num]
                col_num+=1
                degradations[idmac][idcmp][idj] = [inf for _ in range(nbop)]
                temp = []
                for loop4 in range(nbopmac):
                    idop = data[col_num]
                    col_num+=1
                    deg = data[col_num]
                    col_num+=1
                    degradations[idmac][idcmp][idj][idop] = deg
                    temp.append((idop,deg))

                degradations_2.append([idj, nbop, nbopmac, temp])

    #max_len = max(len(ligne) for ligne in dureeMaintenances)
    #dureeMaintenances = [ligne + [0] * (max_len - len(ligne)) for ligne in dureeMaintenances]
    return nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations_2

def parse_operations_file(filename, inf=9999):
    # Lire les lignes du fichier
    with open(filename, 'r') as file:
        lines = file.readlines()
    # Extraire nbJobs et nbMachines de la première ligne
    first_line = lines[0].split()
    nbJobs = int(first_line[0])
    nbMachines = int(first_line[1])
    # Initialiser les listes pour stocker les données
    nbOperationsParJob = []
    dureeOperations = [[[] for j in range(nbJobs)] for k in range(nbMachines)]
    j = 0
    processingTimes=[]
    # Parcourir les lignes restantes pour extraire les données
    for line in lines[1:]:
        processingTimes.append([])
        parts = list(map(int, line.split()))
        index = 0
        nb_operations = parts[index]  # La première valeur est le nombre d'opérations par job
        nbOperationsParJob.append(nb_operations)
        
        for k_ in range(nbMachines):
            for _ in range(nb_operations):
                dureeOperations[k_][j].append(inf)
        
        for i in range(nb_operations):
            processingTimes[j].append([])
            index += 1  # Commencer après le nombre d'opérations
            k_max = parts[index]
            for k in range(k_max):
                index += 1
                num_machine = parts[index]
                index += 1
                duree = parts[index]
                dureeOperations[num_machine][j][i] = duree
                processingTimes[j][i].append((num_machine,duree))
        j += 1
    return nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes
import copy

def completionTime(data, solution, weights, debug=True):
    """
    Simulation cohérente avec OPTION B + y sans indice machine :

    solution =
      solution[0] : liste (longueur = nb_ops_total) des jobs dans l'ordre (séquence globale)
      solution[1] : liste (longueur = nb_ops_total) des machines affectées à chaque opération de solution[0]
      solution[2] : y_set = set() de tuples (j,i,l) indiquant une maintenance APRES l'opération (j,i) sur le composant l
                   (k est implicite car (j,i) est affectée à une machine unique via solution[1])
      solution[3] : tij[j][i] (matrice) ou -1 si "à recalculer"
      (solution[4] optionnel : rangs, ignoré)

    Politique :
      - On exécute l'opération (j,i) sur k
      - On met à jour la dégradation D_kl
      - Si D dépasse theta => maintenance APRES l'opération => machine indispo jusqu'à end_op + m_kl
      - Reset du composant maintenu à 0 après maintenance
    """

    nb_ops_total = sum(data.nbOperationsParJob)

    # Map "ind" -> op index i dans chaque job j
    j_iter = [0 for _ in range(data.nbJobs)]
    i_s = [0 for _ in range(nb_ops_total)]
    for ind in range(nb_ops_total):
        j = solution[0][ind]
        i_s[ind] = j_iter[j]
        j_iter[j] += 1

    # Times
    t_ij = [[0.0 for _ in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    c_ij = [[0.0 for _ in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]

    # Degradation history per machine/component
    D_kl = [[[0.0] for _ in range(data.nbComposants[k])] for k in range(data.nbMachines)]

    # Quality history per job
    # (si tu as des Qinitj différents, remplace 1.0 par data.Qinitj[j] ou autre)
    Qj = [[1.0] for _ in range(data.nbJobs)]
    
    # DEBUG: Check alpha_kl type
    if debug or True:
        print(f"DEBUG: Type of data.alpha_kl: {type(data.alpha_kl)}")
        if isinstance(data.alpha_kl, list):
             print(f"DEBUG: Type of data.alpha_kl[0]: {type(data.alpha_kl[0]) if len(data.alpha_kl)>0 else 'Empty'}")
             print(f"DEBUG: data.alpha_kl sample: {data.alpha_kl}")

    # y : maintenances après op (j,i) pour composant l
    if isinstance(solution[2], set):
        max_comp = max(data.nbComposants) if data.nbComposants else 0
        y = [[[False for _ in range(data.nbOperationsParJob[jj])] 
              for jj in range(data.nbJobs)] 
             for _ in range(max_comp)]
        for (jj, ii, ll) in solution[2]:
             if ll < max_comp and jj < data.nbJobs and ii < data.nbOperationsParJob[jj]:
                 y[ll][jj][ii] = True
    else:
        y = copy.deepcopy(solution[2])
    tij = copy.deepcopy(solution[3])  # matrice start times, ou -1

    dispo_machines = [0.0 for _ in range(data.nbMachines)]
    nbMaintenance = 0
    feasible = True

    for ind in range(nb_ops_total):
        k = solution[1][ind]        # machine index
        j = solution[0][ind]        # job index
        i = i_s[ind]                # operation index

        p = data.dureeOperations[k][j][i]
        if p <= 0:
            feasible = False
            if debug:
                print(f"INFEASIBLE: O_{j}_{i} assigned to machine {k} with p<=0")
            continue

        # Début au plus tôt : max(dispo machine, fin op précédente du job)
        if tij[j][i] == -1:
            prev_c = c_ij[j][i - 1] if i > 0 else 0.0
            t_ij[j][i] = max(dispo_machines[k], prev_c)
        else:
            t_ij[j][i] = float(tij[j][i])

        end_op = t_ij[j][i] + p
        c_ij[j][i] = end_op

        if debug:
            print(f"O_{j}_{i} on M{k} p={p:.2f} start={t_ij[j][i]:.2f} end={end_op:.2f}")

        # Mise à jour dégradation + déclenchement maintenance APRES op
        maint_end = end_op

        for l in range(data.nbComposants[k]):
            last_deg = D_kl[k][l][-1]
            newdeg = p * data.degradations[k][l][j][i]
            newTotdeg = last_deg + newdeg
            D_kl[k][l].append(newTotdeg)

            # Dégradation qualité
            newQdeg = newdeg * data.alpha_kl[k][l]
            Qj[j].append(max(0.0, Qj[j][-1] - newQdeg))

            if debug:
                print(f"  comp {l}: D={last_deg:.4f}+{newdeg:.4f}={newTotdeg:.4f} theta={data.seuils_degradation[k][l]}")

            # Dépassement seuil => maintenance après op
            if newTotdeg >= data.seuils_degradation[k][l]:
                # key = (j, i, l)  # pas de k dans y_set (k implicite par affectation)
                if y[l][j][i] == False:
                    y[l][j][i] = True
                    nbMaintenance += 1

                    # reset après maintenance
                    D_kl[k][l].append(0.0)

                    m = data.dureeMaintenances[k][l]
                    maint_end = max(maint_end, end_op + m)

                    if debug:
                        print(f"    MAINT AFTER: (j={j},i={i}) M{k} comp{l} dur={m:.2f} -> maint_end={maint_end:.2f}")

        # disponibilité machine après op ou après maintenance
        dispo_machines[k] = max(dispo_machines[k], maint_end)

    # Makespan
    Cmax = max(c_ij[j][data.nbOperationsParJob[j] - 1] for j in range(data.nbJobs))

    # Pénalité qualité
    penality = 0
    for j in range(data.nbJobs):
        if Qj[j][-1] < data.Qjmin[j]:
            penality += 1

    AOQ = sum(Qj[j][-1] for j in range(data.nbJobs)) / data.nbJobs
    cout = weights[0] * Cmax + weights[1] * nbMaintenance + weights[2] * penality

    return t_ij, c_ij, Cmax, D_kl, y, i_s, Qj, cout, nbMaintenance, AOQ, penality, feasible


def completionTime2(data, solution, weights, debug=False):
    if debug:
        print(f"Solution 0 {solution[0]}")
        print(f"Solution 1 {solution[1]}")
        print(f"Solution 2 {solution[2]}")
        print(f"Solution 3 {solution[3]}")

    j_iter = [0 for _ in range(data.nbJobs)]
    i_s  = [0 for j in range(data.nbJobs) for i in range(data.nbOperationsParJob[j])]
    t_ij = [[0 for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    c_ij = [[0 for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    D_kl = [[[0] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    Qj   = [[1.0]  for _ in range(data.nbJobs)]
    nbMaintenance = 0
    y    = copy.deepcopy(solution[2])
    tij  = copy.deepcopy(solution[3])
    
    dispo_machines = [0 for _ in range(data.nbMachines)]
    
    for ind in range(sum(data.nbOperationsParJob)):
        j = solution[0][ind]
        i_s[ind] = j_iter[j]
        j_iter[j] += 1

    for ind in range(sum(data.nbOperationsParJob)):
        k = solution[1][ind]        # machine index
        j = solution[0][ind]        # job index
        i = i_s[ind]                # operation index
    
        if debug: 
            print(f"O_{j}_{i} on machine {k} duration {data.dureeOperations[k][j][i]}")

        # calcul de la date de début au plus tôt 
        if tij[j][i]==-1:
            t_ij[j][i] = dispo_machines[k]
            if i > 0 and  c_ij[j][i-1] >= dispo_machines[k]:
                t_ij[j][i] = c_ij[j][i-1] 
        else:
            t_ij[j][i] = solution[3][j][i]

        if debug: 
            print(f"t_{j}{i} = {t_ij[j][i]}")

        feasible = True

        # Mise à jour de la dégradation
        for l in range(data.nbComposants[k]):
            if debug: 
                print(f"    Component {l} degradation {D_kl[k][l][len(D_kl[k][l])-1]}")

            # calcul de la dégradation potentielle pour le composant l de la machine k
            newdeg = data.dureeOperations[k][j][i] * data.degradations[k][l][j][i]    # component RUL degradation
            newTotdeg = D_kl[k][l][-1] + newdeg
            if debug:
                print(f"        new to degred = {newTotdeg} <? {data.seuils_degradation[k][l]}")
            
            D_kl[k][l].append(newTotdeg)
            newQdeg = newdeg * data.alpha_kl[k][l] # quality degradation 
            #newQdeg =0.0
            Qj[j].append(max(0,Qj[j][-1]-newQdeg))
            if Qj[j][-1] >= data.seuils_degradation[k][l]:
                if y[l][j][i] == False:
                    y[l][j][i] = True
                    if debug: 
                        print(f"        maintenance planned")
                    nbMaintenance += 1
                    D_kl[k][l].append(0)
                    #D_kl[k][l].append(newdeg)

                    # mettre à jour la disponibilité de la machine 
                    new_dispo_machine = c_ij[j][i] + data.dureeMaintenances[k][l]
                    if new_dispo_machine > dispo_machines[k]:
                        dispo_machines[k] = new_dispo_machine

                    # mettre à jour la date de début de la tâche
                    #if new_dispo_machine > t_ij[j][i] :
                    #       t_ij[j][i]  = dispo_machines[k]

                    if debug: 
                        print(f"        dispo machine = {new_dispo_machine}")
                """
                # si la degradation dépasse le seuil
                # chercher la dernière opération executée sur la machine pour placer une tâche de maintenance
                found = False
                ind_ = ind-1
                while(ind_ >= 0) :
                    if solution[1][ind_] == k:
                        found = True
                        j_ = solution[0][ind_]
                        i_ = i_s[ind_]
                        if y[l][j_][i_] == False:
                            y[l][j_][i_] = True

                            if debug: 
                                print(f"        maintenance planned")

                            nbMaintenance += 1
                            D_kl[k][l].append(0)
                            D_kl[k][l].append(newdeg)

                            # mettre à jour la disponibilité de la machine 
                            new_dispo_machine = c_ij[j_][i_] + data.dureeMaintenances[k][l]
                            if new_dispo_machine > dispo_machines[k]:
                                dispo_machines[k] = new_dispo_machine

                            # mettre à jour la date de début de la tâche
                            if new_dispo_machine > t_ij[j][i] :
                                t_ij[j][i]  = dispo_machines[k]

                            if debug: 
                                print(f"        dispo machine = {new_dispo_machine}")
                        break
                    ind_ -= 1
                if found == False: 
                    feasible = False
            else:
                
                """
        # calcul de la date de fin de la tâche 
        c_ij[j][i] = t_ij[j][i] + data.dureeOperations[k][j][i]
        if dispo_machines[k] < c_ij[j][i]: 
            dispo_machines[k] = c_ij[j][i]

        if debug: 
            print(f"    C_{j}{i} = {c_ij[j][i]}")

        

    Cmax = max(c_ij[j][data.nbOperationsParJob[j]-1] for j in range(data.nbJobs))
    penality = 0
    for j in range(data.nbJobs):
        if Qj[j][-1] < data.Qjmin[j]:
            penality += 1
    AOQ = sum([Qj[j][-1] for j in range(data.nbJobs)]) / data.nbJobs
    cout = weights[0]*Cmax + weights[1]*nbMaintenance + weights[2]*penality

    return t_ij, c_ij, Cmax, D_kl, y, i_s, Qj, cout, nbMaintenance, AOQ, penality, feasible

def completionTime_previous(data, solution, weights):
    maxComposants = max(data.nbComposants)
    j_iter = [0 for _ in range(data.nbJobs)]
    i_s  = [0 for j in range(data.nbJobs) for i in range(data.nbOperationsParJob[j])]
    t_ij = [[0 for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    c_ij = [[0 for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    D_kl = [[[0] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    Qj   = [[1.0]  for _ in range(data.nbJobs)]

    y    = copy.deepcopy(solution[2])
    tij  = copy.deepcopy(solution[3])
    
    dispo_machines = [0 for _ in range(data.nbMachines)]
    
    for ind in range(sum(data.nbOperationsParJob)):
        j = solution[0][ind]
        i_s[ind] = j_iter[j]
        j_iter[j] += 1
    for ind in range(sum(data.nbOperationsParJob)):
        k = solution[1][ind]        # machine index
        j = solution[0][ind]        # job index
        i = i_s[ind]                # operation index
        if tij[j][i]==-1:
            if i != 0 :
                t_ij[j][i] = c_ij[j][i-1] if (c_ij[j][i-1] >= dispo_machines[k]) else dispo_machines[k]
            else :
                t_ij[j][i] = dispo_machines[k]
        else:
            t_ij[j][i] = solution[3][j][i]
        print(f'k={k} --> tij[{j}][{i}]={t_ij[j][i]}')
        print(f'data.dureeOperations[{k}][{j}][{i}]={data.dureeOperations[k][j][i]}')
        c_ij[j][i] = t_ij[j][i] + data.dureeOperations[k][j][i]
        for l in range(data.nbComposants[k]):
            ind_ = ind
            while(ind_ >= 0) :
                if solution[1][ind_] == k:
                    j_ = solution[0][ind_]
                    i_ = i_s[ind_]
                    if y[l][j_][i_]:
                        D_kl[k][l].append(0)
                    break
                ind_ -= 1         
            newdeg = data.dureeOperations[k][j][i] * data.degradations[k][l][j][i]    # component RUL degradation
            newQdeg = newdeg * data.alpha_kl[k][l] # quality degradation 
            newTotdeg = D_kl[k][l][-1] + newdeg 
            D_kl[k][l].append(newTotdeg)
            if (newTotdeg >= data.seuils_degradation[k][l]):
                y[l][j][i] = True
            else:
                y[l][j][i] = False
        dispo_machines[k] = c_ij[j][i] + sum([int(y[l][j][i])*data.dureeMaintenances[k][l] for l in range(data.nbComposants[k])])
        Qj[j].append(max(0,Qj[j][-1]-newQdeg))
    Cmax = max(c_ij[j][data.nbOperationsParJob[j]-1] for j in range(data.nbJobs))
    nbMaintenance=0
    for l in range(maxComposants):
        for j in range(data.nbJobs):
            for i in range(data.nbOperationsParJob[j]):
                if solution[2][l][j][i]==True:
                    nbMaintenance += 1
    penality = 0
    for j in range(data.nbJobs):
        if Qj[j][-1] < data.Qjmin[j]:
            penality += 1
    AOQ=sum([(1-Qj[j][-1]) for j in range(data.nbJobs)])/data.nbJobs
    cout = weights[0]*Cmax + weights[1]*nbMaintenance + weights[2]*penality
    
    return t_ij, c_ij, Cmax, D_kl, y, i_s, Qj, cout,nbMaintenance,AOQ,penality