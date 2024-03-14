from utils import data
from utils import diagram
from utils import commun_functions
from utils import data

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 

class RS:
    def __init__(self, initial_solution, initial_temperature, cooling_rate, stopping_temperature, size_iteration, max_iterations):
        # Simulated Annealing parameters
        self.initial_solution = initial_solution
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
        self.stopping_temperature = stopping_temperature
        self.size_iteration = size_iteration
        self.max_iterations = max_iterations 

    def CritMetropolis(self, delta, temperature):
        if delta <= 0: 
            return True
        else:
            if random.random() < math.exp((-1 * delta) / temperature):
                return True
            return False
    
    def simulated_annealing(self, data_instance):
        print("Initial solution: ", self.initial_solution)
        current_solution = self.initial_solution
        current_energy = commun_functions.evaluate(current_solution, data_instance)[2]
        best_solution = current_solution
        best_energy = current_energy
        temperature = self.initial_temperature

        iteration = 0
        while temperature > self.stopping_temperature:
            for i in range(self.size_iteration):
                #print(f"Iteration {iteration} current temperature: {temperature} ")
                #print(f"Current solution: {current_solution} Cmax = {current_energy}")
                neighbor_solution = commun_functions.Voisinage(current_solution, 1, 1, data_instance)[0]
                neighbor_energy = commun_functions.evaluate(neighbor_solution,data_instance)[2]
                #print(f"Current solution: {neighbor_solution} Cmax = {neighbor_energy}")
                delta = neighbor_energy - best_energy
                # accept the neighbor solution
                if self.CritMetropolis(delta, temperature) == True: 
                    current_solution = neighbor_solution
                    current_energy = neighbor_energy
                    
                if current_energy < best_energy : 
                    best_solution = current_solution
                    best_energy = current_energy

            # Cool down the temperature
            temperature *= self.cooling_rate
            
            #update number of iterations 
            iteration += 1
        return best_solution, best_energy, iteration


# Run the Simulated Annealing algorithm
    
instancefilename='Instances/Kacem1.fjs'

lambdaPM = 0.7
mu = 0.1
PM_time = 2
ProcTime=commun_functions.FJSInstanceReading(instancefilename)

print("ProcTime=", ProcTime)

data_instance = data.data(lambdaPM, mu, PM_time, ProcTime)

initial_solution = commun_functions.GenererSolution(data_instance)
RS_instance = RS(initial_solution, 50, 0.1, 0.1, 100, 100)
best_solution, best_energy, nb_iteration = RS_instance.simulated_annealing(data_instance)

iterations = 100
x = [i for i in range(iterations)]

solutions = []
for i in range(iterations): 
    initial_solution = commun_functions.GenererSolution(data_instance)
    RS_instance = RS(initial_solution, 50, 0.1, 0.1, 10, 100)

    best_sub_solution, best_sub_energy, nb_sub_iteration = RS_instance.simulated_annealing(data_instance)
    
    solutions.append(best_energy)

    if best_sub_energy < best_energy : 
        best_solution = best_sub_solution
        best_energy = best_sub_energy
        nb_iteration = nb_sub_iteration


print("intial Solution:", initial_solution)
print("Best Solution:", best_solution, "Best energy:", best_energy)
print("Number of iterations:", nb_iteration)
print("Solutions ", solutions)

plt.plot(x, solutions, 'r-', label="RS")
plt.axhline(y=15, color="green")  # Barre horizontale

plt.grid(True)
plt.title("FJSP - 4J-7M (Recuit Simulé)")
plt.ylabel("Cmax")
plt.xlabel("Iterations")
plt.show()

# NM,NJ,cmax,schedule,maint,ehf = commun_functions.evaluate(best_solution,data_instance)

# print("Schedule=", schedule)

# fileName = f"results/simulation_{time.strftime('%H%M%S')}_{int(time.time())}.jpg"

# Gantt = diagram.diagram(NM,NJ,data_instance.ProcTime,data_instance.mu,cmax,schedule,maint,ehf,fileName)

# print(f"Production scedhuling: {schedule}")
# print(f"Maintenance scedhuling: {maint}")


# Gantt.plotEHF()
# Gantt.plotGantt()

# Charger les images enregistrées
# image_gantt = Image.open(Gantt.ganttsavefilename)
# image_ehf = Image.open(Gantt.ehfplotsavefilename)

# # Afficher les deux images dans une seule fenêtre
# fig, ax = plt.subplots(1, 2, figsize=(10, 5))

# ax[0].imshow(image_gantt)
# ax[0].axis('off')
# ax[0].set_title('Gantt Chart')

# ax[1].imshow(image_ehf)
# ax[1].axis('off')
# ax[1].set_title('EHF Chart')

# plt.show()


