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

def completionTime(data, solution,weights):
    maxComposants = max(data.nbComposants)
    j_iter = [0 for j in range(data.nbJobs)]
    i_s  = [0 for j in range(data.nbJobs) for i in range(data.nbOperationsParJob[j])]
    t_ij = [[0 for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    c_ij = [[0 for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]
    D_kl = [[[0] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    Qj   = [[1.0]  for j in range(data.nbJobs)]
    y    = copy.deepcopy(solution[2])
    tij  = copy.deepcopy(solution[3])
    dispo_machines = [0 for _ in range(data.nbMachines)]
    #print("data.nbOperationsParJob=",data.nbOperationsParJob,"-->",sum(data.nbOperationsParJob)," operations")
    #print("solution=",solution)
    FromMILP=False
    if tij[0][0]>-1:
        FromMILP=True
    for ind in range(sum(data.nbOperationsParJob)):
        j = solution[0][ind]
        i_s[ind] = j_iter[j]
        j_iter[j] += 1
    print(solution[0])
    print(i_s)    
    for ind in range(sum(data.nbOperationsParJob)):
        k = solution[1][ind]
        j = solution[0][ind]
        #i_s[ind] = j_iter[j]
        i = i_s[ind]
        print(j,i)
        if tij[j][i]<=-1:
            if i != 0 :
                t_ij[j][i] = c_ij[j][i-1] if (c_ij[j][i-1] >= dispo_machines[k]) else dispo_machines[k]
            else :
                t_ij[j][i] = dispo_machines[k]
        else:
            #print(f"solution[3][{j}][{i}]=",solution[3][j][i])
            t_ij[j][i] = solution[3][j][i]
        c_ij[j][i] = t_ij[j][i] + data.dureeOperations[k][j][i]
        temp_var = 0
        for l in range(data.nbComposants[k]):
            ind_ = ind#-1
            while(ind_ >= 0) :
                if solution[1][ind_] == k:
                    j_ = solution[0][ind_]
                    i_ = i_s[ind_]
                    if y[l][j_][i_]:
                        D_kl[k][l].append(0)
                    break
                ind_ -= 1
            newdeg=data.dureeOperations[k][j][i]*data.degradations[k][l][j][i]
            newQdeg=newdeg*data.alpha_kl[k][l]
            newTotdeg=D_kl[k][l][len(D_kl[k][l])-1] + newdeg 
            D_kl[k][l].append(newTotdeg)
            if (newTotdeg >=data.seuils_degradation[k][l]):
                #if y[l][j][i] == False and FromMILP:
                    #print("error in degradation calculation--Case 1")
                y[l][j][i] = True
                #print(f'Degr[{k},{l}]={D_kl[k][l][-1]} and DegThreshold={data.seuils_degradation[k][l]} --> Maintenance of component {l} of machine {k} performed after operation {i} of job {j}')
            else:
                #if y[l][j][i] == True and FromMILP:
                   # print("error in degradation calculation--Case 2")
                y[l][j][i] = False
            
            #if #print(f'degr[{k},{l}]={D_kl[k][l][-1]} Seuil={data.seuils_degradation[k][l]}')
        print("maintenances machine",k,"=",[int(y[l][j][i])*data.dureeMaintenances[k][l] for l in range(data.nbComposants[k])])
        dispo_machines[k] = c_ij[j][i] + max([int(y[l][j][i])*data.dureeMaintenances[k][l] for l in range(data.nbComposants[k])])
        #print([y[l][j][i]*data.dureeMaintenances[k][l] for l in range(data.nbComposants[k])], max([y[l][j][i]*data.dureeMaintenances[k][l] for l in range(data.nbComposants[k])]))
        Qj[j].append(Qj[j][-1]-newQdeg)

        #j_iter[j] += 1
    for k in range(data.nbMachines):
        for l in range(data.nbComposants[k]):
            print("Machine ",k+1," composant ",l+1, " Dkl=",D_kl[k][l])
    Cmax = max(c_ij[j][data.nbOperationsParJob[j]-1] for j in range(data.nbJobs))
    nbMaintenance=0
    for l in range(maxComposants):
        for j in range(data.nbJobs):
            for i in range(data.nbOperationsParJob[j]):
                if solution[2][l][j][i]==True:
                    #if y[l][j][i]==False:
                       # print("y[",l,"][",j,"][",i,"]==False")
                    #print("solution[2][",l,"][",j,"][",i,"]==True")
                    nbMaintenance += 1
    penality = 0
    for j in range(data.nbJobs):
        if Qj[j][-1] < data.Qjmin[j]:
            penality += 1
    AOQ=sum([Qj[j][-1] for j in range(data.nbJobs)])/data.nbJobs
    cout = weights[0]*Cmax + weights[1]*nbMaintenance + weights[2]*penality
    return t_ij, c_ij, Cmax, D_kl, y, i_s, Qj, cout,nbMaintenance,AOQ,penality