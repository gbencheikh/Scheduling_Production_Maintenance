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
                for loop4 in range(nbopmac):
                    idop = data[col_num]
                    col_num+=1
                    deg = data[col_num]
                    col_num+=1
                    degradations[idmac][idcmp][idj][idop] = deg

    max_len = max(len(ligne) for ligne in dureeMaintenances)
    dureeMaintenances = [ligne + [0] * (max_len - len(ligne)) for ligne in dureeMaintenances]
    return nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations

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
    # Parcourir les lignes restantes pour extraire les données
    for line in lines[1:]:
        parts = list(map(int, line.split()))
        index = 0
        nb_operations = parts[index]  # La première valeur est le nombre d'opérations par job
        nbOperationsParJob.append(nb_operations)
        for k_ in range(nbMachines):
            for _ in range(nb_operations):
                dureeOperations[k_][j].append(inf)
        for i in range(nb_operations):
            index += 1  # Commencer après le nombre d'opérations
            k_max = parts[index]
            for k in range(k_max):
                index += 1
                num_machine = parts[index]
                index += 1
                duree = parts[index]
                dureeOperations[num_machine][j][i] = duree
        j += 1
    return nbJobs, nbMachines, nbOperationsParJob, dureeOperations