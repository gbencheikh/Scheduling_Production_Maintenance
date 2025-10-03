from fonctions import CommonFunctions as ComFuns
from fonctions.CommonFunctions import parse_degradations_file, parse_operations_file
from fonctions.data import Data
import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 
import copy
import numpy as np
from fonctions.Save_Read_JSON import *

class RSCS:
    def __init__(self, data):
        self.execution_time = 0
        self.data = data
    
    def inserer_maintenance(self,y):
        # Générer des indices aléatoires
        l = random.randint(0, len(y) - 1)
        j = random.randint(0, len(y[l]) - 1)
        i = random.randint(0, len(y[l][j]) - 1)
        while y[l][j][i] == True and sum(y[l][j])<len(y[l][j]):
            l = random.randint(0, len(y) - 1)
            j = random.randint(0, len(y[l]) - 1)
            i = random.randint(0, len(y[l][j]) - 1)
        y[l][j][i] = True
        #if random.choice([True, False]):
        #    y[l][j][i] = True # random.choice([True, False])
        return y
    def etat_voisin(self, solution, nbMachines):
        voisin = copy.deepcopy(solution)
        
        i, j = random.sample(range(len(voisin[0])), 2)
        voisin[0][i], voisin[0][j] = voisin[0][j], voisin[0][i]
        
        k = random.randint(0, len(voisin[1]) - 1)
        voisin[1][k] = random.randint(0, nbMachines - 1)

        voisin[2]=self.inserer_maintenance(voisin[2])
        return voisin

    def Run_RSCS(self,tempInit,tempFin,coolRate,iters, objweights,plotshow):
        t0 = time.perf_counter()
        solution = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])], #operation's job index
            [0 for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])], #operation's assigned machine index 
            [[[False for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))], #components maintained after operation  
            [[-1 for i in range(self.data.nbOperationsParJob[j]) ]  for j in range(self.data.nbJobs) ] #operation's starting times
        ]
        opt_solution = copy.deepcopy(solution)

        opt_Cmax = ComFuns.completionTime(self.data,opt_solution,objweights)[2]
        T = tempInit
        iteration = 0
        iteration_max = iters
        cmax_tab = []
        T_tab=[]
        #tempFin=0
        ## itérations
        while iteration < iteration_max and T > tempFin:
            nouvelle_solution = self.etat_voisin(solution, self.data.nbMachines)
            cost1 = ComFuns.completionTime(self.data,nouvelle_solution,objweights)[7]
            cost2 = ComFuns.completionTime(self.data,solution,objweights)[7]
            DE =  cost1 - cost2
            if DE < 0:
                solution = copy.deepcopy(nouvelle_solution)
                #if (cost1 <= opt_Cmax):
                #    opt_solution = copy.deepcopy(nouvelle_solution)
                #    opt_Cmax = cost1
                opt_solution = copy.deepcopy(nouvelle_solution)
            elif np.exp(-DE/T)>np.random.rand():
                solution = copy.deepcopy(nouvelle_solution)
            elif np.exp(-DE/T)>np.random.rand():
                solution = copy.deepcopy(nouvelle_solution)
            #elif np.exp(-DE/T)>np.random.rand():
            #    solution = copy.deepcopy(nouvelle_solution)
            #elif np.exp(-DE/T)>np.random.rand():
            #    solution = copy.deepcopy(nouvelle_solution)
            T *= coolRate
            iteration += 1
            Cmax = ComFuns.completionTime(self.data,solution,objweights)[2]
            cmax_tab.append(Cmax)
            T_tab.append(T)
        if plotshow: 
            #print(cmax_tab[-1], ",", T_tab[-1], "," , iteration)
            plt.plot(cmax_tab)
            plt.show()
        opt_Cmax = ComFuns.completionTime(self.data,opt_solution,objweights)[2]
        nbrmaintenances=ComFuns.completionTime(self.data,opt_solution,objweights)[8]
        avgoutqual=ComFuns.completionTime(self.data,opt_solution,objweights)[9]
        qualpenality=ComFuns.completionTime(self.data,opt_solution,objweights)[10]
        return opt_solution, opt_Cmax, time.perf_counter()-t0,nbrmaintenances,avgoutqual,qualpenality

if __name__ == "__main__": 
    n1=1
    n2=1
    tempInit=100
    tempFin=0
    coolRate=0.99
    iters=30000
    weights=[0.7,0.2,0.1]
 
    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
    data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    #print(repr(data))
    alphakl=0.0    # quality degradation rate
    betakl=0.0         # average degradation rate of componenets 
    std_betakl=0.0     # standard deviation of degradation rate of componenets
    qjmin=0.95          # acceptable quality level triggering quality penality ()
    lambdakl=0.95       # degradation threshold triggering PdM 
    data.alpha_kl = [[alphakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    x=float(np.round(max(0,np.random.normal(betakl, std_betakl, 1)[0]),3))
    #print(x)
    data.degradations=[[[[x  for ido in range(data.nbOperationsParJob[j])]  for j in range(data.nbJobs) ] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    data.Qjmin = [qjmin for j in range(data.nbJobs)] 
    #print(data.seuils_degradation)  
    data.seuils_degradation = [[lambdakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)] 
    rscs=RSCS(data)
    ## Solve with SA algorithm
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=rscs.Run_RSCS(tempInit,tempFin,coolRate,iters,weights,True)
    #print("optsolution1=",optsolution1)
    k=1
    save_JSON(data,optsolution1,f"Results/RSCStestk{n1}inst{n2}_{k}.json",weights)
    result = lire_fichier_json(f"Results/RSCStestk{n1}inst{n2}_{k}.json")
    plotGantt(result, f"Results/Gantts/RSCStestk{n1}inst{n2}_figure_{k}",f"k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showgantt=True)
    plotDEGRAD(result, data,  f"Results/EHFs/RSCStestk{n1}inst{n2}_figure_{k}",f"k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showdegrad=False)
    #print("obj1=", optCmax1, "CPUTime=",cputime1)   