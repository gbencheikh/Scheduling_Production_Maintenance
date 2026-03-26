from fonctions.CommonFunctions import parse_degradations_file, parse_operations_file
#from fonctions.colors import couleurMachines
from fonctions.data import Data

# from my_module import create_gantt_chart
from mip import Model, xsum, maximize, minimize, BINARY
import numpy as np
import matplotlib.pyplot as plt
import json
import time 
from fonctions.diagram import *
from fonctions.Save_Read_JSON import *

import gurobipy as gp
from gurobipy import GRB
import matplotlib.pyplot as plt
import numpy as np

# --- Small Instance Data ---
jobs = [0, 1]
ops_per_job = {0: [0, 1], 1: [0, 1]}
machines = [0, 1]
components = [0, 1] # 2 components per machine
THR = 100
maint_time = 15

# Processing times [job][op][machine]
p_time = { (0,0,0): 10, (0,0,1): 12, (0,1,0): 8, (0,1,1): 10,
           (1,0,0): 15, (1,0,1): 10, (1,1,0): 12, (1,1,1): 14 }

# Degradation per op [job][op][machine][comp]
deg_rate = 15 

extfile=True
if extfile:
    n1=1
    n2=1
    nbJobs, nbMachines, nbOperationsParJob, p_time, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
    DATA = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, p_time, processingTimes)
    
    # Update global variables for the solver
    jobs = list(range(nbJobs))
    machines = list(range(nbMachines))
    ops_per_job = {j: list(range(nbOperationsParJob[j])) for j in jobs}
    components = list(range(max(nbComposants))) if nbComposants else []

    # Convert p_time (list) to dictionary p_time[(job, op, machine)]
    p_time_dict = {}
    for j in jobs:
        for i in ops_per_job[j]:
            for mac in machines:
                # dureeOperations structure is [machine][job][op]
                dur = p_time[mac][j][i]
                if dur < 9999: # Filter invalid assignments
                    p_time_dict[(j, i, mac)] = dur
    p_time = p_time_dict
    #print(repr(data))
    alphakl=0.1         # quality degradation rate
    betakl=0.1         # average degradation rate of componenets 
    std_betakl=0.0      # standard deviation of degradation rate of componenets
    aql=0.85          # acceptable quality level triggering quality penality ()
    lambdakl=0.9        # degradation threshold triggering PdM 
    dureemaint=1        # maintenance duration
    

    DATA.alpha_kl = [[alphakl for l in range(nbComposants[k])] for k in range(nbMachines)]
    x=betakl #float(np.round(max(0,np.randomodel.normal(betakl, std_betakl, 1)[0]),3))
    #print(x)
    DATA.degradations=[[[[x  for ido in range(nbOperationsParJob[j])]  for j in range(nbJobs) ] for l in range(nbComposants[k])] for k in range(nbMachines)]
    DATA.Qjmin = [aql for j in range(nbJobs)] 
    #print(DATA.seuils_degradation)  
    DATA.seuils_degradation = [[lambdakl for l in range(nbComposants[k])] for k in range(nbMachines)] 
    DATA.dureeMaintenances = [[dureemaint for l in range(nbComposants[k])] for k in range(nbMachines)]
    
    nmax=5
    Weights = [0.5,0.5,1.0]
    alphas  = [[alphakl for l in range(nbComposants[k])] for k in range(nbMachines)]
    qinit   = [1.0 for j in range(nbJobs)]  # Exemple de taux de qualité initiale
    qmin    = [aql for j in range(nbJobs)]   # Exemple de taux de qualité minimale acceptable



def solve_milp():
    m = gp.Model("FJSP_Maintenance")
    
    # Variables
    x = m.addVars(p_time.keys(), vtype=GRB.BINARY, name="x")
    c = m.addVars([(j,i) for j in jobs for i in ops_per_job[j]], name="c")
    v = m.addVars([(j,i,k) for j in jobs for i in ops_per_job[j] for k in components], 
                  vtype=GRB.INTEGER, name="v")
    c_max = m.addVar(name="c_max")

    # 1. Assignment
    for j in jobs:
        for i in ops_per_job[j]:
            m.addConstr(x.sum(j, i, '*') == 1)

    # 2. Precedence
    for j in jobs:
        for i in range(len(ops_per_job[j])-1):
             # Ensure we access p_time with (j, i+1, mac) and only for valid machine assignments
            m.addConstr(c[j,i+1] >= c[j,i] + gp.quicksum(x[j,i+1,mac]*p_time[j,i+1,mac] for mac in machines if (j,i+1,mac) in x))

    # 3. Makespan
    for j in jobs:
        m.addConstr(c_max >= c[j, ops_per_job[j][-1]])

    # Simplified Maintenance Logic for small scale
    # (In a full MILP, sequence variables y[i,j,l,r,m] are needed to track degradation flow)
    
    m.setObjective(c_max, GRB.MINIMIZE)
    m.optimize()
    
    return m
import random

class ScheduleGA:
    def __init__(self, data):
        self.data = data # Dictionary containing job/machine/comp info
        
    def simulate_schedule(self, chromosome):
        """
        Calculates fitness by simulating the schedule and 
        tracking component degradation in real-time.
        """
        machine_clocks = {m: 0 for m in self.data['machines']}
        machine_deg = {m: {k: 0 for k in self.data['components']} for m in self.data['machines']}
        job_quality = {j: 0 for j in self.data['jobs']}
        maint_counts = 0
        
        # history for plotting
        history = {'gantt': [], 'deg': []}
        
        for job_id, machine_id in chromosome:
            # 1. Calculate Start Time
            start_t = machine_clocks[machine_id]
            dur = self.data['p_times'][job_id][machine_id]
            
            # 2. Track Degradation & Check Maintenance
            for k in self.data['components']:
                added_deg = self.data['deg_rates'][job_id][machine_id][k]
                
                if machine_deg[machine_id][k] + added_deg > self.data['THR']:
                    # Trigger Maintenance
                    maint_counts += 1
                    start_t += self.data['maint_time']
                    machine_deg[machine_id][k] = 0 # Reset
                
                machine_deg[machine_id][k] += added_deg
                # Quality impact (max degradation encountered)
                job_quality[job_id] = max(job_quality[job_id], machine_deg[machine_id][k])
                
                history['deg'].append((start_t + dur, machine_id, k, machine_deg[machine_id][k]))
            
            end_t = start_t + dur
            machine_clocks[machine_id] = end_t
            history['gantt'].append((job_id, machine_id, start_t, end_t))
            
        return history, max(machine_clocks.values()), maint_counts, sum(job_quality.values())

def plot_results(history):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # --- 1. GANTT CHART ---
    colors = plt.cm.tab10(np.linspace(0, 1, 10))
    for job_id, mac_id, start, end in history['gantt']:
        ax1.barh(mac_id, end-start, left=start, color=colors[job_id % 10], edgecolor='black', alpha=0.8)
        ax1.text(start + (end-start)/2, mac_id, f'J{job_id}', va='center', ha='center', color='white')

    ax1.set_ylabel('Machine ID')
    ax1.set_title('Production & Maintenance Schedule (Gantt)')
    ax1.grid(True, linestyle='--', alpha=0.5)

    # --- 2. DEGRADATION EVOLUTION ---
    # history['deg'] = (time, machine_id, comp_id, level)
    for m in [0, 1]: # Example machines
        for k in [0, 1]: # Example components
            data = [d for d in history['deg'] if d[1] == m and d[2] == k]
            if data:
                times = [d[0] for d in data]
                levels = [d[3] for d in data]
                ax2.step(times, levels, where='post', label=f'M{m}-K{k}')

    ax2.axhline(y=100, color='r', linestyle='--', label='Threshold')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Degradation Level')
    ax2.set_title('Component Degradation over Time')
    ax2.legend(loc='upper left', bbox_to_anchor=(1, 1))
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()

a=solve_milp()
# --- Sample execution of Plotting ---
sample_history = {
    'gantt': [(0, 0, 0, 10), (1, 1, 0, 15), (0, 1, 15, 25), (1, 0, 10, 25)],
    'deg': [(10, 0, 0, 20), (10, 0, 1, 30), (15, 1, 0, 40), (25, 1, 0, 10), (25, 0, 0, 50)]
}
plot_results(sample_history)

