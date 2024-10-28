from fonctions import CommonFunctions as ComFuns

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 
import copy
import numpy as np

class RSCS:
    def __init__(self, data, initial_solution, initial_temperature, cooling_rate, stopping_temperature, size_iteration, max_iterations):
        """ 
            initial_solution: the initial solution.
            initial_temperature: the initial temperature.
            cooling_rate: the cooling rate.
            stopping_temperature: the final temperature.
            size_iteration: the size of one iteration of simulated annealing.
            max_iterations: the total number of iterations.
        """
        self.initial_solution = initial_solution
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.stopping_temperature = stopping_temperature
        self.size_iteration = size_iteration
        self.max_iterations = max_iterations 
        self.execution_time = 0
        self.data = data
    
    def inserer_maintenance(self,y):
        # Générer des indices aléatoires
        l = random.randint(0, len(y) - 1)
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

    def mise_a_jour_temperature(self,T):
        alpha = 0.99
        return T*alpha
    
    def RecuitSimule(self):
        ## initialisation
        maxComposants = max(self.data.nbComposants)
        solution = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [0 for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [[[False for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(maxComposants)]
        ]
        opt_solution = copy.deepcopy(solution)
        opt_Cmax = ComFuns.completionTime(opt_solution)[2]
        T = 100
        iteration = 0
        iteration_max = self.max_iterations
        cmax_tab = []

        ## itérations
        while iteration < iteration_max and T > 0:
            nouvelle_solution = self.etat_voisin(solution, self.data.nbMachines)
            cost1 = ComFuns.completionTime(nouvelle_solution)[7]
            cost2 = ComFuns.completionTime(solution)[7]
            DE =  cost1 - cost2
            if DE < 0:
                solution = copy.deepcopy(nouvelle_solution)
                if (cost1 <= opt_Cmax):
                    opt_solution = copy.deepcopy(nouvelle_solution)
                    opt_Cmax = cost1
            elif np.exp(-DE/T)>np.random.rand():
                solution = copy.deepcopy(nouvelle_solution)
            T = self.mise_a_jour_temperature(T)
            iteration += 1
            Cmax = ComFuns.completionTime(solution)[2]
            cmax_tab.append(Cmax)
        return solution

    def Run_RSCS(self,instance,tempInit,tempFin,coolRate,iters):
        t0 = time.perf_counter()
        temperature_initial = tempInit
        temperature_final = tempFin
        cooling_rate = coolRate
        iterations = iters
        solution = [
            [j for j in range(instance.nbJobs) for i in range(instance.nbOperationsParJob[j])],
            [0 for j in range(instance.nbJobs) for i in range(instance.nbOperationsParJob[j])],
            [[[False for i in range(instance.nbOperationsParJob[j])] for j in range(instance.nbJobs)] for l in range(max(instance.nbComposants))]
        ]
        alpha_kl = [[.01 for l in range(instance.nbComposants[k])] for k in range(instance.nbMachines)]
        Qjmin = [0.8 for j in range(instance.nbJobs)]

        opt_solution = copy.deepcopy(solution)
        opt_Cmax = ComFuns.completionTime(instance,opt_solution,alpha_kl,Qjmin)[2]
        T = 100
        iteration = 0
        iteration_max = 1000
        cmax_tab = []
        
        ## itérations
        while iteration < iteration_max and T > 0:
            nouvelle_solution = self.etat_voisin(solution, instance.nbMachines)
            cost1 = ComFuns.completionTime(instance,nouvelle_solution,alpha_kl,Qjmin)[7]
            cost2 = ComFuns.completionTime(instance,solution,alpha_kl,Qjmin)[7]
            DE =  cost1 - cost2
            if DE < 0:
                solution = copy.deepcopy(nouvelle_solution)
                if (cost1 <= opt_Cmax):
                    opt_solution = copy.deepcopy(nouvelle_solution)
                    opt_Cmax = cost1
            elif np.exp(-DE/T)>np.random.rand():
                solution = copy.deepcopy(nouvelle_solution)
            T = self.mise_a_jour_temperature(T)
            iteration += 1
            Cmax = ComFuns.completionTime(instance,solution,alpha_kl,Qjmin)[2]
            cmax_tab.append(Cmax)
        
        return opt_solution, opt_Cmax, time.perf_counter()-t0