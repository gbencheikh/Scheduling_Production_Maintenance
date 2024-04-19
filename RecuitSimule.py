from utils import data
from utils import diagram
from utils import commun_functions

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 

class RS:
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

    def CritMetropolis(self, delta, temperature):
        """
        This function corresponds to the decision criterion.

        Args:
        delta: the difference between the current solution and the candidate solution
        temperature: the current temperature

        Returns:
            True if the candidate solution is accepted, False otherwise
        """

        if delta <= 0: 
            return True
        else:
            if random.random() < math.exp((-1 * delta) / temperature):
                return True
            return False
    
    def simulated_annealing(self, data):
        t0 = time.perf_counter()
        current_solution = self.initial_solution
        current_energy = commun_functions.evaluate(current_solution, data)[2]
        best_solution = current_solution
        best_energy = current_energy
        temperature = self.initial_temperature

        iteration = 0
        while temperature > self.stopping_temperature:
            for i in range(self.size_iteration):
                neighbor_solution = commun_functions.VoisinageRS(current_solution, data.ProcTime)
                best_voisin = []
                best_voisin_energy = float('inf')

                for voisin in neighbor_solution: 
                    energy = commun_functions.evaluate(voisin, data)[2]
                    if best_voisin_energy > energy:
                        best_voisin = voisin
                        best_voisin_energy = energy

                delta = best_voisin_energy - best_energy
                # accept the neighbor solution
                if self.CritMetropolis(delta, temperature) == True: 
                    current_solution = best_voisin
                    current_energy = best_voisin_energy
                    
                if current_energy < best_energy : 
                    best_solution = current_solution
                    best_energy = current_energy

            # Cool down the temperature
            temperature *= self.cooling_rate
            
            #update number of iterations 
            iteration += 1
        t1 = time.perf_counter()
        self.execution_time = t1 - t0

        return best_solution, best_energy, iteration


# # Run the Simulated Annealing algorithm
def call_RS(data_instance):
    best_solution = []
    best_energy = float('inf')

    t0 = time.perf_counter()
    temperature_initial = [50, 70]
    temperature_final = [0.1, 0.2]
    cooling_rate = [0.01, 0.02]
    iterations = [50, 100]

    total_execution_time = 0 
    for i in range(4):
        for tpi in temperature_initial:
            for tpf in temperature_final:
                for cr in cooling_rate: 
                    for it in iterations:
                        ti = time.perf_counter()
                        if ti - t0 <= 120:
                            initial_solution = commun_functions.GenererSolution(data_instance)
                            RS_instance = RS(initial_solution, tpi, cr, tpf, it, it)
                            solution, energy, nb_iteration = RS_instance.simulated_annealing(data_instance)

                            if(energy < best_energy):
                                best_energy = energy
                                best_solution = solution
                                total_execution_time += RS_instance.execution_time
                        else: 
                            return best_solution, best_energy, total_execution_time
                            
    return best_solution, best_energy, total_execution_time               

def test_RS(instancefilename):
    lambdaPM = [0.8]
    mu = [0]
    PM_time = [2]

    print("lambda 	Mu	PM_time	Cmax	nb PM	Execution (s)")
    for lbd in lambdaPM:
        for m in mu: 
            for pm in PM_time: 
                ProcTime=commun_functions.FJSInstanceReading(instancefilename)
                data_instance = data.data(lbd, m, pm, ProcTime)

                best_solution, best_energy, total_execution_time = call_RS(data_instance)
                nb_PM = sum([len(m) for id, m in enumerate(commun_functions.evaluate(best_solution, data_instance)[4])])

                print(f"{lbd}   {m} {pm}    {best_energy}   {nb_PM} {total_execution_time}")
                            
test_RS('Instances/Kacem4.fjs')

# solution_19 = [(9, 1), (8, 4), (3, 2), (3, 1), (9, 5), (6, 0), (1, 0), (8, 1), (2, 3), (4, 1), (4, 0), (1, 0), (5, 2), (6, 4), (0, 6), (9, 1), (7, 3), (2, 5), (5, 2), (2, 3), (7, 6), (5, 2), (7, 4), (6, 5), (0, 5), (8, 6), (3, 1), (4, 3), (0, 5)]

# NM,NJ,cmax,schedule,maint,ehf = commun_functions.evaluate(best_solution,data_instance)

# plotfilename= "results/Figs/%s/%s"  % ("Ghita",instancefilename)
# # fileName = f"results/simulation_{time.strftime('%H%M%S')}_{int(time.time())}.jpg"

# print(f"Production scedhuling: {schedule}")
# print(f"Maintenance scedhuling: {maint}")

# GanttRS = diagram.diagram(NM,NJ,data_instance.PM_time,data_instance.lambdaPM,data_instance.mu,cmax,schedule,maint,ehf, plotfilename,1,1)
# GanttRS.plotGantt()
# GanttRS.plotEHF2()
