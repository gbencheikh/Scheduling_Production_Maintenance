from fonctions import CommonFunctions as ComFuns

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 
import copy
import numpy as np

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

    def Run_RSCS(self,tempInit,tempFin,coolRate,iters):
        t0 = time.perf_counter()
        solution = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [0 for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [[[False for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))]
        ]
        opt_solution = copy.deepcopy(solution)
        opt_Cmax = ComFuns.completionTime(self.data,opt_solution)[2]
        T = tempInit
        iteration = 0
        iteration_max = iters
        cmax_tab = []
        T_tab=[]
        #tempFin=0
        ## itérations
        while iteration < iteration_max and T > tempFin:
            nouvelle_solution = self.etat_voisin(solution, self.data.nbMachines)
            cost1 = ComFuns.completionTime(self.data,nouvelle_solution)[7]
            cost2 = ComFuns.completionTime(self.data,solution)[7]
            DE =  cost1 - cost2
            if DE < 0:
                solution = copy.deepcopy(nouvelle_solution)
                if (cost1 <= opt_Cmax):
                    opt_solution = copy.deepcopy(nouvelle_solution)
                    opt_Cmax = cost1
            elif np.exp(-DE/T)>np.random.rand():
                solution = copy.deepcopy(nouvelle_solution)
            T *= coolRate
            iteration += 1
            Cmax = ComFuns.completionTime(self.data,solution)[2]
            cmax_tab.append(Cmax)
            T_tab.append(T)
        print(cmax_tab[-1])
        print(T_tab[-1])
        print(iteration)
        plt.plot(cmax_tab)
        plt.show()
        
        return opt_solution, opt_Cmax, time.perf_counter()-t0