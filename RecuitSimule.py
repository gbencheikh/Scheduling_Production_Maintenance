from utils import data
from utils import diagram
from utils import commun_functions
import random
import math
import matplotlib.pyplot as plt
from PIL import Image

class data:
    def __init__(self):
        self.lambdaC=0.99 # Degradtion threshold of Corrective Maintenance  
        self.lambdaQ=0.8  # Degradation threshold of Quality maintenance
        self.lambdaPM=0.7 # Degradation threshold of Preventive Maintenance
        self.mu=0.01      # reliability degradation rate
        self.ProcTime=[ #(machine_id, process_time) 
                [ [(2, 10)], [(0, 5)], [(1, 4)]   ],	#Job0
                [ [(0, 6) ], [(1, 7)]                       ],	#Job1
                [ [(1, 4)],  [(2, 5)]                       ],	#Job2
            ]
        self.PM_time=2
        self.CM_time=5
        self.NM = 4
        self.NJ = 5

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
data_instance = data()
# initial_solution = commun_functions.GenererSolution(data_instance)
# RS_instance = RS(initial_solution, 50, 0.1, 0.1, 10, 100)

# best_solution, best_energy, nb_iteration = RS_instance.simulated_annealing(data_instance)

# print("intial Solution:", initial_solution)
# print("Best Solution:", best_solution, "Best energy:", best_energy)
# print("Number of iterations:", nb_iteration)

# #evaluate : NM,NJ,cmax,schedule,maint,ehf
# #diagram : self,NM,NJ,PMT,mu, cmax,schedule,maint,ehf

# NM,NJ,cmax,schedule,maint,ehf = commun_functions.evaluate(best_solution,data_instance)

solution = [(1,1), (0,3), (2,2), (1,2), (0,1), (0,2), (2,3)]
NM,NJ,cmax,schedule,maint,ehf = commun_functions.evaluate(solution,data_instance)

print("Schedule=", schedule)

Gantt = diagram.diagram(NM,NJ,data_instance.ProcTime,data_instance.mu,cmax,schedule,maint,ehf)

print(f"Production scedhuling: {schedule}")
print(f"Maintenance scedhuling: {maint}")

# Gantt.plotEHF()
Gantt.plotGantt()

# Charger les images enregistrées
image_gantt = Image.open("gantt_chart.png")
image_ehf = Image.open("ehf_chart.png")

# Afficher les deux images dans une seule fenêtre
fig, ax = plt.subplots(1, 2, figsize=(10, 5))

ax[0].imshow(image_gantt)
ax[0].axis('off')
ax[0].set_title('Gantt Chart')

ax[1].imshow(image_ehf)
ax[1].axis('off')
ax[1].set_title('EHF Chart')

plt.show()


