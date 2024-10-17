
from functions import CommonFunctions as ComFuns

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 
import copy

class RSCS:
    def __init__(self, initial_solution, initial_temperature, cooling_rate, stopping_temperature, size_iteration, max_iterations):
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
    
    def inserer_maintenance(self,y):
        # Générer des indices aléatoires
        l = random.randint(0, len(y) - 1)
        j = random.randint(0, len(y[l]) - 1)
        i = random.randint(0, len(y[l][j]) - 1)
        if random.choice([True, False]):
            y[l][j][i] = random.choice([True, False])
        
    def etat_voisin(self, solution, nbMachines):
        voisin = copy.deepcopy(solution)
        
        i, j = random.sample(range(len(voisin[0])), 2)
        voisin[0][i], voisin[0][j] = voisin[0][j], voisin[0][i]
        
        k = random.randint(0, len(voisin[1]) - 1)
        voisin[1][k] = random.randint(0, nbMachines - 1)

        self.inserer_maintenance(voisin[2])
        return voisin

    def mise_a_jour_temperature(self,T):
        alpha = 0.99
        return T*alpha
    
    def RecuitSimule(self):
        ## initialisation
        maxComposants = max(nbComposants)
        solution = [
            [j for j in range(nbJobs) for i in range(nbOperationsParJob[j])],
            [0 for j in range(nbJobs) for i in range(nbOperationsParJob[j])],
            [[[False for i in range(nbOperationsParJob[j])] for j in range(nbJobs)] for l in range(maxComposants)]
        ]
        opt_solution = copy.deepcopy(solution)
        opt_Cmax = ComFuns.completionTime(opt_solution)[2]
        T = 100
        iteration = 0
        iteration_max = self.max_iterations
        cmax_tab = []

        ## itérations
        while iteration < iteration_max and T > 0:
            nouvelle_solution = self.etat_voisin(solution, nbMachines)
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
            T = mise_a_jour_temperature(T)
            iteration += 1
            Cmax = ComFuns.completionTime(solution)[2]
            cmax_tab.append(Cmax)