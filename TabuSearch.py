from utils import data
from utils import diagram
from utils import commun_functions

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 

class TS:
    def __init__(self, data, initial_solution, tabu_list_size, max_iterations):
        self.data = data
        self.initial_solution = initial_solution
        self.tabu_list_size = tabu_list_size
        self.max_iterations = max_iterations

    def tabu_search(self):
        t0 = time.perf_counter()
        tabu_list = []

        for _ in range(self.max_iterations):
            best_neighbor = None
            best_neighbor_score = float('inf')

            neighbors = commun_functions.VoisinageAll(current_solution, self.data)

            for neighbor in neighbors:
                if neighbor not in tabu_list:
                    neighbor_score = commun_functions.evaluate(neighbor, data)[2]
                    if neighbor_score < best_neighbor_score:
                        best_neighbor = neighbor
                        best_neighbor_score = neighbor_score

            if best_neighbor is None:
                break

            current_solution = best_neighbor
            if commun_functions.evaluate(current_solution, data) < commun_functions.evaluate(best_solution, data):
                best_solution = current_solution

            tabu_list.append(best_neighbor)
            if len(tabu_list) > self.tabu_list_size:
                tabu_list.pop(0)

        t1 = time.perf_counter()
        self.execution_time = t1 - t0
        return best_solution 

def call_TS(data_instance):
    best_solution = []
    best_energy = float('inf')

    t0 = time.perf_counter()
    tabu_list_size = [10,20,30]
    max_iterations = [80,90,100]

    total_execution_time = 0 
    for i in range(4):
        for tls in tabu_list_size:
            for ni in max_iterations:
                ti = time.perf_counter()
                if ti - t0 <= 120:
                    initial_solution = commun_functions.GenererSolution(data_instance)

                    TS_instance = TS(data_instance, initial_solution, tls, ni)
                    solution, energy, nb_iteration = TS_instance.tabu_search()

                    if(energy < best_energy):
                        best_energy = energy
                        best_solution = solution
                        total_execution_time += TS_instance.execution_time
                    else: 
                        return best_solution, best_energy, total_execution_time      
                            
    return best_solution, best_energy, total_execution_time

def test_TS(instancefilename):
    lambdaPM = [0.8]
    mu = [0]
    PM_time = [2]

    print("lambda 	Mu	PM_time	Cmax	nb PM	Execution (s)")
    for lbd in lambdaPM:
        for m in mu: 
            for pm in PM_time: 
                ProcTime=commun_functions.FJSInstanceReading(instancefilename)
                data_instance = data.data(lbd, m, pm, ProcTime)

                best_solution, best_energy, total_execution_time = call_TS(data_instance)
                nb_PM = sum([len(m) for id, m in enumerate(commun_functions.evaluate(best_solution, data_instance)[4])])

                print(f"{lbd}   {m} {pm}    {best_energy}   {nb_PM} {total_execution_time}")
                            
test_TS('Instances/5_Kacem/Kacem4.fjs')