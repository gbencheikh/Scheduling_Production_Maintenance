# -*- coding: utf-8 -*-
"""
Created on Thu Feb  5 17:03:39 2026

@author: bbettayeb
"""

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
from mip import Model, xsum, BINARY, minimize, GRB
import gurobipy as gp
from gurobipy import GRB, quicksum as qsum

class FJSP_Maintenance_Quality_complex_systems__model:
    def __init__(self, datas,alphas, aql,qinit,qmin, n_max=3,weights=[1.0,0.0,0.0]): 
        self.data = datas
        self.n_max = n_max
        self.weights =weights
        self.alpha_kl = alphas # [[0.01 for l in range(datas.nbComposants[k])] for k in range(self.data.nbMachines)]
        self.AQL = aql #0.8
        self.Qinitj = qinit #[1.0 for j in range(self.data.nbJobs)]  # Exemple de taux de qualité initiale
        self.Qjmin = qmin #[0.8 for j in range(self.data.nbJobs)]   # Exemple de taux de qualité minimale acceptable
        self.inf= 999999
    def solve(self):
        # Récupération des données
        data = self.data
        
        # --- 1) Data placeholders (REMPLACÉ) ---
        J = range(data.nbJobs)                                       # jobs j
        I = {j: range(data.nbOperationsParJob[j]) for j in J}        # operations i of job j
        K = range(data.nbMachines)                                   # machines k
        L = {k: range(data.nbComposants[k]) for k in K}              # components l for machine k
        
        # Toutes les opérations (j, i)
        all_ops = [(j, i) for j in J for i in I[j]]
        
        # Paramètres (Inchagngés)
        p       = data.dureeOperations
        delta   = data.degradations
        m_kl    = data.dureeMaintenances
        theta   = data.seuils_degradation
        alpha   = self.alpha_kl
        Qinit   = self.Qinitj
        Qmin    = self.Qjmin
        lam1, lam2, lam3 = self.weights
        print("theta   =",theta)
    
        # Éligibilité (can_run[k][j][i])
        can_run = [[[int(data.dureeOperations[k][j][i]>0) for i in I[j]] for j in J] for k in K ]
        tmax0=max([sum([can_run[k][j][i]*data.dureeOperations[k][j][i] +sum([m_kl[k][l] for l in L[k]]) for j in J for i in I[j] ]) for k in K ])
        #print("can_run=",can_run)
        print("m_kl=",m_kl)
        print("tmax0=",tmax0)
        # Constantes Big-M
        Dmax = 1.1 # Borne sur la dégradation
        tmax = tmax0 #1000 # Borne sur les temps (à recalculer précisément si besoin)
        
        MQ   = 100 # Borne sur la qualité/dégradation (à recalculer précisément si besoin)
        M_E = max(1, Dmax)
    
        # --- 2) Model ---
        model = gp.Model("sequence_scheduling_degradation_quality")
    
        # --- 3) Decision variables (MODIFIÉ) ---
    
        # x[j,i,k] = 1 if operation (j,i) is assigned to machine k
        x = {(j, i, k): model.addVar(vtype=GRB.BINARY, name=f"x[{j},{i},{k}]")
             for j, i in all_ops for k in K if can_run[k][j][i]}
    
        # z[j,i, j',i', k] = 1 if operation (j,i) immediately precedes (j',i') on machine k # On ne crée z que si les deux opérations peuvent être exécutées sur k
        z = {}
        ybarZ={}
        for k in K:
            ops_k = [(j,i) for j,i in all_ops if can_run[k][j][i]]
            for j,i in ops_k:
                for j1,i1 in ops_k:
                    if (j,i) != (j1, i1):
                         z[j, i, j1, i1, k] = model.addVar(vtype=GRB.BINARY, name=f"z[{j},{i},{j1},{i1},{k}]")
                         for l in L[k]:
                             ybarZ[j, i, j1, i1, k, l] = model.addVar(vtype=GRB.BINARY, name=f"ybarZ[{j},{i},{j1},{i1},{k},{l}]")
    
        # y[j,i,k,l] = 1 if a maintenance for component l of machine k happens BEFORE operation (j,i) # y est ici indexé par l'opération qui suit la maintenance.
        y = {}
        
        for k in K:
            ops_k = [(j,i) for j,i in all_ops if can_run[k][j][i]]
            for j,i in all_ops:
                if (j,i,k) in x:
                    for l in L[k]:
                         y[j, i, k, l] = model.addVar(vtype=GRB.BINARY, name=f"y[{j},{i},{k},{l}]")
                         if (j,i) in ops_k:
                             for j1,i1 in ops_k:
                                 if (j,i) != (j1, i1):
                                     model.addConstr(ybarZ[j, i, j1, i1, k, l]<=z[j, i, j1, i1, k],                 name=f"Cstr-ybarZ0[{j},{i},{j1},{i1},{k},{l}]")
                                     model.addConstr(ybarZ[j, i, j1, i1, k, l]<=1-y[j, i, k, l],                    name=f"Cstr-ybarZ1[{j},{i},{j1},{i1},{k},{l}]")
                                     model.addConstr(ybarZ[j, i, j1, i1, k, l]>=z[j, i, j1, i1, k]-y[j, i, k, l],   name=f"Cstr-ybarZ2[{j},{i},{j1},{i1},{k},{l}]")
                             
        # Start times t[j,i] (Continuous)
        t = {(j,i): model.addVar(lb=0.0, ub=tmax, name=f"t[{j},{i}]") for j,i in all_ops}
    
        # Degradation accounting (Indexé par l'opération (j,i) et la machine (k) qui l'exécute)
        # D[j,i,k,l]: Degradation cumulative BEFORE operation (j,i) on machine k for component l
        D = {}
        D_before={}
        D_indices = []
        for j,i in all_ops:
            for k in K:
                if (j,i,k) in x:
                    for l in L[k]:
                        D_indices.append((j,i,k,l))
                        D[j,i,k,l] = model.addVar(lb=0.0,       name=f"D[{j},{i},{k},{l}]")
                        D_before[j,i,k,l]=model.addVar(lb=0.0,  name=f"Dbefore[{j},{i},{k},{l}]")
        
        # Pi_yD[j,i,k,l] = y[j,i,k,l] * D[j,i,k,l] (Maintenance reset linearization)
        pi_yD = {idx: model.addVar(lb=0.0,          name=f"pi_yD{idx}") for idx in D_indices}
    
        # Quality variables (Inchagngés)
        Qji = {(j,i): model.addVar(lb=0.0,          name=f"Q[{j},{i}]") for j,i in all_ops}
        Qj  = {j:     model.addVar(lb=0.0,          name=f"Qj[{j}]") for j in J}
        ZQ  = {(j,i): model.addVar(vtype=GRB.BINARY,name=f"ZQ[{j},{i}]") for j,i in all_ops} # max(0, prev - loss)
        
        # Objective auxiliaries (Inchagngés)
        Cmax  =     model.addVar(lb=0.0,                                       name="Cmax")
        Mcount =    model.addVar(lb=0.0,ub=sum([data.nbOperationsParJob[j] for j in J]),name="Mcount")
        TotPena =   model.addVar(lb=0.0,                                                name="TotPena")
        penal = {j: model.addVar(vtype=GRB.CONTINUOUS, lb=0.0, ub=1.0,                  name=f"penal[{j}]") for j in J}
        
        model.update()
    
        # --- 4) Constraints (MODIFIÉES) ---
        
        # B) Affectation unique à une machine
        for j, i in all_ops:
            # Chaque opération est affectée à exactement une machine k
            model.addConstr(gp.quicksum(x[j,i,k] for k in K if (j,i,k) in x) == 1, name=f"Cstr-B_{j}{i}")
    
        # --- Contraintes d'Ordonnancement (Remplacement A, F, I, J) ---
    
        # I) Precedence: Opérations séquentielles du même Job
        for j in J:
            for i in I[j][:-1]:
                # L'opération suivante (i+1) doit commencer après la fin de l'opération actuelle (i)
                # t[j,i+1] >= t[j,i] + sum_k x[j,i,k] * p[k][j][i]
                proc_time_ji = gp.quicksum(x[j,i,k] * p[k][j][i] for k in K if (j,i,k) in x)
                model.addConstr(t[j,i+1] >= t[j,i] + proc_time_ji, name=f"Cstr-I_{j}{i}")
    
        # Z) Sequence Precedence: Contraintes de non-chevauchement sur les machines (utilisation Big-M)
        M_non_overlap = 100*tmax # Big M for non-overlapping
        
        for k in K:
            ops_k = [(j,i) for j,i in all_ops if can_run[k][j][i]]
            for j, i in ops_k:
                for j1, i1 in ops_k:
                    if (j,i) == (j1, i1): continue
    
                    # Opération (j,i) sur k est affectée: x[j,i,k]=1
                    # Opération (j',i') sur k est affectée: x[j',i',k]=1
    
                    # Condition 1: Si (j,i) précède (j',i') (z=1), alors t[j',i'] doit être après t[j,i] + durée
                    if (j, i, j1, i1, k) in z:
                        # t[j',i'] >= t[j,i] + p[k][j][i] - M * (1 - z) - M * (1 - x[j,i,k]) - M * (1 - x[j',i',k])
                        
                        # Simplification: Seuls les z où x est 1 peuvent être 1
                        model.addConstr(z[j, i, j1, i1, k] <= x[j,i,k],     name=f"Cstr-Z0_{j}{i}_{j1}{i1}_{k}")
                        model.addConstr(z[j, i, j1, i1, k] <= x[j1,i1,k],   name=f"Cstr-Z1_{j}{i}_{j1}{i1}_{k}")
                        model.addConstr(z[j1, i1, j, i, k] <= x[j,i,k],     name=f"Cstr-Z01_{j}{i}_{j1}{i1}_{k}")
                        model.addConstr(z[j1, i1, j, i, k] <= x[j1,i1,k],   name=f"Cstr-Z11_{j}{i}_{j1}{i1}_{k}")
    
                        # Contrainte de non-chevauchement
                        model.addConstr(t[j1, i1] >= t[j, i] + p[k][j][i] + gp.quicksum(y[j, i, k, l] * m_kl[k][l] for l in L[k] if (j, i, k, l) in y)
                            - M_non_overlap * (1 - z[j, i, j1, i1, k]), name=f"Cstr-Z2_{j}{i}_{j1}{i1}_{k}")
                    
                    # Condition 2: Si les deux sont sur la machine k, elles doivent être séquencées (z ou z_reverse = 1)
                    # z + z_reverse >= x[j,i,k] + x[j',i',k] - 1
                    #if (j, i, j1, i1, k) in z and (j1, i1, j, i, k) in z:
                        #model.addConstr(z[j, i, j1, i1, k] + z[j1, i1, j, i, k] >= x[j,i,k] + x[j1,i1,k] - 1, name=f"Cstr-Z3_{j}{i}_{j1}{i1}_{k}")
                        #model.addConstr(z[j, i, j1, i1, k] + z[j1, i1, j, i, k] <= x[j1,i1,k],                name=f"Cstr-Z4_{j}{i}_{j1}{i1}_{k}")
                        #model.addConstr(z[j, i, j1, i1, k] + z[j1, i1, j, i, k] <= x[j,i,k],                  name=f"Cstr-Z5_{j}{i}_{j1}{i1}_{k}")
    
        # ---------- Machine sequencing structure for "immediate predecessor" z ----------
        # Create an order/position variable u for each op that can run on k
        u = {}
        N_k = {}  # number of candidate ops per machine (for MTZ big-M)
        
        for k in K:
            ops_k = [(j,i) for (j,i) in all_ops if can_run[k][j][i]]
            N_k[k] = len(ops_k)
            for (j,i) in ops_k:
                u[j,i,k] = model.addVar(lb=0.0, ub=N_k[k], vtype=GRB.CONTINUOUS,
                                        name=f"u[{j},{i},{k}]")
        
        model.update()
        
        for k in K:
            ops_k = [(j,i) for (j,i) in all_ops if can_run[k][j][i]]
            N = N_k[k]
        
            # (A) Degree constraints: at most one successor and one predecessor if assigned to k
            for (j,i) in ops_k:
                model.addConstr(
                    gp.quicksum(z[j,i,j1,i1,k] for (j1,i1) in ops_k if (j1,i1)!=(j,i))
                    <= x[j,i,k],
                    name=f"deg_succ[{j},{i},{k}]"
                )
                model.addConstr(
                    gp.quicksum(z[j1,i1,j,i,k] for (j1,i1) in ops_k if (j1,i1)!=(j,i))
                    <= x[j,i,k],
                    name=f"deg_pred[{j},{i},{k}]"
                )
        
                # if not assigned, u can be 0; if assigned, force u >= 1 (optional but helps)
                model.addConstr(u[j,i,k] >= x[j,i,k], name=f"u_lb[{j},{i},{k}]")
        
            # (B) MTZ subtour elimination / enforce acyclic single ordering when arcs are chosen
            # If z[a,b,k]=1 then u[b] >= u[a] + 1
            for (j,i) in ops_k:
                for (j1,i1) in ops_k:
                    if (j,i) == (j1,i1):
                        continue
                    model.addConstr(
                        u[j1,i1,k] >= u[j,i,k] + 1 - N * (1 - z[j,i,j1,i1,k]),
                        name=f"mtz[{j},{i},{j1},{i1},{k}]"
                    )
        
            # (C) Exactly one "first" and one "last" operation among those assigned to machine k
            # first = assigned ops with no predecessor; last = assigned ops with no successor
            first_k = model.addVar(vtype=GRB.BINARY, name=f"first_dummy[{k}]")  # not used, placeholder
            # Count of arcs on machine k equals (#assigned ops) - (#chains).
            # Enforcing exactly one chain: arcs = assigned_ops - 1, if assigned_ops >=1
            assigned_ops = gp.quicksum(x[j,i,k] for (j,i) in ops_k)
            arcs = gp.quicksum(z[j,i,j1,i1,k]
                               for (j,i) in ops_k for (j1,i1) in ops_k if (j,i)!=(j1,i1))
        
            # If machine unused (assigned_ops=0) => arcs=0 ; if used => arcs = assigned_ops - 1
            # Use big-M with binary use_k
            use_k = model.addVar(vtype=GRB.BINARY, name=f"use_k[{k}]")
            model.addConstr(assigned_ops <= N * use_k, name=f"use_k_ub[{k}]")
            model.addConstr(assigned_ops >= use_k,     name=f"use_k_lb[{k}]")
            model.addConstr(arcs == assigned_ops - use_k, name=f"one_chain[{k}]")
    
    
    # --- Contraintes de Dégradation et Maintenance (Remplacement C, D, E, D1, D2) ---
    
        # D) Dégradation Récurrente (basée sur la séquence Z)

        M_D = 1000  # Big-M for degradation propagation
        M_T = 2     # Big-M for trigger (keep your value if you want)
        
        # 1) Reset when maintenance is performed BEFORE the operation (successor op)
        #    If y=1 => Dbefore = 0; if y=0 => Dbefore is free (bounded by propagation constraints)
        for (j1, i1, k, l) in D_indices:
            # If operation (j1,i1) is not assigned to k, relax with (1-x)
            model.addConstr(
                D_before[j1, i1, k, l] <= M_D * (1 - y[j1, i1, k, l]) + M_D * (1 - x[j1, i1, k]),
                name=f"Cstr-DbeforeReset[{j1},{i1},{k},{l}]"
            )
        
        # 2) Propagate degradation along the immediate-precedence arcs on each machine
        #    If z[j,i,j1,i1,k]=1 and y[j1,i1,k,l]=0 and x[j1,i1,k]=1 => Dbefore[j1,i1,k,l] == D[j,i,k,l]
        for (j1, i1, k, l) in D_indices:
            for (j, i) in all_ops:
                if (j, i, k, l) not in D:
                    continue
                if (j, i, j1, i1, k) not in z:
                    continue
        
                # Lower bound: Dbefore >= Dpred - M*((1-z) + y_succ + (1-x_succ))
                model.addConstr(
                    D_before[j1, i1, k, l] >= D[j, i, k, l]
                    - M_D * ((1 - z[j, i, j1, i1, k]) + y[j1, i1, k, l] + (1 - x[j1, i1, k])),
                    name=f"Cstr-DbeforeLB[{j},{i},{j1},{i1},{k},{l}]"
                )
        
                # Upper bound: Dbefore <= Dpred + M*((1-z) + y_succ + (1-x_succ))
                model.addConstr(
                    D_before[j1, i1, k, l] <= D[j, i, k, l]
                    + M_D * ((1 - z[j, i, j1, i1, k]) + y[j1, i1, k, l] + (1 - x[j1, i1, k])),
                    name=f"Cstr-DbeforeUB[{j},{i},{j1},{i1},{k},{l}]"
                )
        
        # 3) Accumulate degradation during the operation:
        #    If x=1 => D = Dbefore + p*delta ; else relax with Big-M
        for (j1, i1, k, l) in D_indices:
            inc = p[k][j1][i1] * delta[k][l][j1][i1]
            model.addConstr(
                D[j1, i1, k, l] >= D_before[j1, i1, k, l] + inc - M_D * (1 - x[j1, i1, k]),
                name=f"Cstr-DaccLB[{j1},{i1},{k},{l}]"
            )
            model.addConstr(
                D[j1, i1, k, l] <= D_before[j1, i1, k, l] + inc + M_D * (1 - x[j1, i1, k]),
                name=f"Cstr-DaccUB[{j1},{i1},{k},{l}]"
            )
        
        # 4) Maintenance trigger:
        #    If D > theta => y must be 1 (when op is actually on machine k)
        for (j, i, k, l) in D_indices:
            model.addConstr(
                D[j, i, k, l] - theta[k][l] <= M_T * y[j, i, k, l] + M_T * (1 - x[j, i, k]),
                name=f"Cstr-Trigger[{j},{i},{k},{l}]"
            )            
    
            
            
            
        # E) Maintenance Trigger
        M_T = 2 # Big M pour le trigger
        for j,i,k,l in D_indices:
            # Si D > theta, maintenance y doit être 1 (Déclenchement AVANT l'opération (j,i))
            # D[j,i,k,l] - theta[k][l] <= M_T * y[j,i,k,l]
            model.addConstr(D[j,i,k,l] - theta[k][l] <= M_T * y[j,i,k,l], name=f"Cstr-E0_{j}{i}{k}{l}")
    
        # D1) McCormick pour pi_yD = y * D
        for j,i,k,l in D_indices:
            # pi_yD[j,i,k,l] = y[j,i,k,l] * D[j,i,k,l]
            model.addConstr(pi_yD[j,i,k,l] <= Dmax * y[j,i,k,l],                    name=f"Cstr-D11_{j}{i}{k}{l}")
            model.addConstr(pi_yD[j,i,k,l] <= D[j,i,k,l],                           name=f"Cstr-D12_{j}{i}{k}{l}")
            model.addConstr(pi_yD[j,i,k,l] >= D[j,i,k,l] -Dmax * (1 - y[j,i,k,l]),  name=f"Cstr-D13_{j}{i}{k}{l}")
    
    
        # --- Contraintes de Qualité (Remplacement K) ---
        # K) Qualité Récurrente (basée sur D)
        M_Q = MQ # Big M pour la qualité
    
        for j in J:
            # i = 0 (Première opération)
            k_affect = [k for k in K if (j,0,k) in x]
            #if not k_affect: continue
            #k0 = k_affect[0] # La machine est unique (par Cstr-B)
    
            # Perte: sum_l alpha[k][l] * D[j,0,k,l]
            loss0 = gp.quicksum(alpha[k0][l] * D[j,0,k0,l] for _,k0 in enumerate(k_affect) for l in L[k0] if (j,0,k0,l) in D)
    
            # Q[j,0] = max(0, Qinit[j] - loss0)
            # Utilisation de la linéarisation MAX(0, expr) (inchangée)
            model.addConstr(loss0 - Qinit[j] <= M_Q * (1 - ZQ[j,0]) ,           name=f"Cstr-K0_{j}")
            model.addConstr(Qinit[j] - loss0 <= M_Q * ZQ[j,0],                  name=f"Cstr-K1_{j}")
            model.addConstr(Qji[j,0] <= Qinit[j] - loss0 + M_Q * (1 - ZQ[j,0]), name=f"Cstr-K2_{j}")
            model.addConstr(Qji[j,0] >= Qinit[j] - loss0,                       name=f"Cstr-K3_{j}")
            model.addConstr(Qji[j,0] <= M_Q * ZQ[j,0],                          name=f"Cstr-K4_{j}")
    
            # i >= 1
            for i in I[j][1:]:
                k_affect = [k for k in K if (j,i,k) in x]
                #if not k_affect: continue
                #ki = k_affect[0]
    
                # Perte: sum_l alpha[k][l] * D[j,i,k,l]
                lossi = gp.quicksum(alpha[ki][l] * D[j,i,ki,l] for _,ki in enumerate(k_affect) for l in L[ki] if (j,i,ki,l) in D)
                
                # Q[j,i] = max(0, Qji[j,i-1] - lossi) (inchangée)
                model.addConstr(lossi - Qji[j,i-1] <= M_Q * (1 - ZQ[j,i]),              name=f"Cstr-K50_{j}{i}" )
                model.addConstr(Qji[j,i-1] - lossi <= M_Q * ZQ[j,i],                    name=f"Cstr-K51_{j}{i}")
                model.addConstr(Qji[j,i] <= Qji[j,i-1] - lossi + M_Q * (1 - ZQ[j,i]),   name=f"Cstr-K52_{j}{i}")
                model.addConstr(Qji[j,i] >= Qji[j,i-1] - lossi,                         name=f"Cstr-K53_{j}{i}")
                model.addConstr(Qji[j,i] <= M_Q * ZQ[j,i],                              name=f"Cstr-K54_{j}{i}")
      
            # Link final Qj
            last_i = data.nbOperationsParJob[j]-1
            model.addConstr(Qj[j] == Qji[j,last_i], name=f"Cstr-K6_{j}")
    
    
        # --- Contraintes Objectif (L, M) ---
        
        # L) Quality penalties (Inchagngées)
        for j in J:
            # penal[j] = max(0, Qmin[j] - Qj[j])
            model.addConstr(penal[j] >= Qmin[j] - Qj[j],            name=f"Cstr-L00_{j}")
            model.addConstr(penal[j] >= 0,                          name=f"Cstr-L01_{j}")
            # Note: L02 (penal[j] <= 1) est omise car Qj peut être > Qmin et penal est cont.
        model.addConstr(TotPena == gp.quicksum(penal[j] for j in J), name=f"Cstr-L1")
    
        # M) Makespan and maintenance counter (MODIFIÉES)
        # Cmax est le temps de fin de la dernière opération.
        for j in J:
            last_i = I[j][-1]
            proc_time_j_last = gp.quicksum(x[j,last_i,k] * p[k][j][last_i] for k in K if (j,last_i,k) in x)
            # Cmax >= t[j,last_i] + proc_time_j_last
            model.addConstr(Cmax >= t[j,last_i] + proc_time_j_last,         name=f"Cstr-M0_{j}")
        # Mcount (total maintenances)
        model.addConstr(Mcount == gp.quicksum(y[j,i,k,l] for j,i,k,l in y), name=f"Cstr-M")
        
        #contraint sur AOQ<=AQL
        #print("self.AQL=",self.AQL)
        #model.addConstr(gp.quicksum((1-Qj[j]) for j in range(self.data.nbJobs))<=(1-self.AQL)*self.data.nbJobs,name=f"Cstr-AQL")
        
        # ------------- 5) Objective -------------
        #model.setObjective(lam1*Cmax + lam2*Mcount + lam3*AvgOQ, GRB.MINIMIZE)
        model.setObjective(lam1*Cmax + lam2*Mcount + lam3*TotPena, GRB.MINIMIZE)
        # ------------- 6) Gurobi parameters (optional) -------------
        model.Params.MIPGap = 0.01      # 1% gap target
        model.Params.TimeLimit = 3600   # 1 hour
        model.Params.Threads = 0        # use all cores
        # model.Params.Presolve = 2
        # model.Params.Heuristics = 0.1
        model.update()
        # ------------- 7) Solve -------------
        t0 = time.perf_counter()
        model.optimize()
        cputime1 = time.perf_counter()-t0
        # ------------- 8) Retrieve solution (example) -------------
        if model.status == GRB.OPTIMAL or model.status == GRB.TIME_LIMIT:
            print(f"Obj = {model.objVal:.4f}, Cmax={Cmax.X:.3f}, Maint={Mcount.X:.0f}, Pen={TotPena.X:.0f}")
            # Example: list scheduled ops by (k,n)
            schedule = []
            for j in J:
                for i in I[j]:
                    for k in K:
                        if x[j,i,k].X ==1:
                                #schedule.append((k,n,j,i,t[j,i].X,p[k][j][i]))
                                schedule.append((k,j,i,t[j,i].X,p[k][j][i],(t[j,i].X+p[k][j][i]) ))
            schedule.sort()
            for rec in schedule:
                print("Machine %d: job %d op %d starts at %.2f (dur=%.2f) and ends at %.1f" % rec)
      
            
        
        if model.Status in [GRB.INFEASIBLE, GRB.INF_OR_UNBD]:
            # Make sure we disambiguate "infeasible or unbounded"
            model.setParam(GRB.Param.DualReductions, 0)
            model.optimize()
            if model.Status == GRB.INFEASIBLE:
                print("\nModel is INFEASIBLE. Computing IIS...")
                model.computeIIS()
        
                # Write the IIS to a file you can open in a text editor
                model.write("iis.ilp")   # also try "iis.mps" if you prefer
        
                # List members of the IIS
                print("\n=== Constraints in IIS ===")
                for c in model.getConstrs():
                    if c.IISConstr:
                        print(f"  {c.ConstrName}")
        
                # Quadratic constraints (if you have any)
                print("Quadratic constraints (if you have any)")
                try:
                    for qc in model.getQConstrs():
                        if qc.IISQConstr:
                            # .QCName exists on recent Gurobi; fall back to index if needed
                            name = getattr(qc, "QCName", f"QConstr_{qc.index}")
                            print(f"  {name}")
                except AttributeError:
                    pass
        
                # SOS constraints (rare)
                try:
                    for s in model.getSOSs():
                        if s.IISSOS:
                            print(f"  SOS_{s.index}")
                except AttributeError:
                    pass
        
                print("\n=== Variable bounds in IIS ===")
                for v in model.getVars():
                    if v.IISLB or v.IISUB:
                        print(f"  {v.VarName}  LB_in_IIS={bool(v.IISLB)}  UB_in_IIS={bool(v.IISUB)}")
        
                # Optionally stop here to avoid continuing into solution readout
                return 0, 0, cputime1,0,0,0
        
                
        optCmax1 = Cmax.X
        qualpenal1 = sum(penal[j].x for j in range(self.data.nbJobs))
        nbrmaint1  = Mcount.x

        
        optsolution1 = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [sum(k*int(x[j,i,k].X) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            #[[[max([(int(x[n,k,j,i].x)*int(y[n][k][l].x)) for n in range(self.n_max) for k in range(self.data.nbMachines)])  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))]
            [[[False  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))],
            [[t[j,i].X for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)],
            [1+sum((int(t[j_,i_].x)<int(t[j,i].x)) for k in range(self.data.nbMachines) for j_ in J for i_ in I[j_] if (x[j,i,k].x and x[j_,i_,k].x)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])]
        ]
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                mach=sum(k*int(x[j,i,k].x) for k in range(self.data.nbMachines))
                rank= 1+sum((int(t[j_,i_].x)<int(t[j,i].x)) for k in range(self.data.nbMachines) for j_ in J for i_ in I[j_] if x[j_,i_,mach].x) # sum(n*int(x[j,i,mach].x) for n in range(self.n_max))
                maxdeg=max([D[j,i,mach,l].x for l in range(self.data.nbComposants[mach])] )
                stime=int(t[j,i].x)
                ptime=self.data.dureeOperations[mach][j][i]
                maintafter=False
                for l in range(self.data.nbComposants[mach]):
                    if y[j,i,mach,l].x:
                        maintafter=True
                        l=self.data.nbComposants[mach]
                        #break
                #print("O_%d,%d : machine=%d  start=%d end=%d rank=%d max_machDeg=%.2f maintAfter=%s" % (j+1,i+1,mach+1,stime,stime+ptime,rank, maxdeg,maintafter))
                
        for k in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[k]):
                for j in range(self.data.nbJobs):
                    #temp=False
                    for i in range(self.data.nbOperationsParJob[j]):
                        temp=(x[j,i,k].x and y[j,i,k,l].x)
                        if temp==True:
                            optsolution1[2][l][j][i] =True
                            #print("break 1 -->", " on machine=",k+1 , "component =",l+1, " job ",j+1," operation ",i+1, " n=",n+1)
                            i=self.data.nbOperationsParJob[j]
                            #break
        print(optsolution1)
        avgoq1=sum((1-Qj[j].x) for j in range(self.data.nbJobs))/self.data.nbJobs
        #for k in range(self.data.nbMachines):
        #    print([["{:.2f}".format(D[n,k,l].x) for l in range(self.data.nbComposants[k]) ] for n in range(self.n_max)])
        
        for j in range(self.data.nbJobs):
            plt.plot([Qji[j,i].x for i in range(self.data.nbOperationsParJob[j])], marker='s')
            plt.title(f"Qj evolution of job {j+1}",fontsize=15)
            for i in range(self.data.nbOperationsParJob[j]) :
                plt.text(i,Qji[j,i].x+0.005,f"{Qji[j,i].x:.2f}")
            plt.show()
            #print([Qji[j,i].x for i in range(self.data.nbOperationsParJob[j])])
            #print([max(pi_xD[n,k,l,j,i].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k])) for i in range(self.data.nbOperationsParJob[j])])
        plt.plot([Qj[j].x for j in range(self.data.nbJobs)], marker='s')
        for j in range(self.data.nbJobs):
            plt.text(j,Qj[j].x+0.005,f"{Qj[j].x:.2f}")
        plt.title(f"Qj of jobs",fontsize=15)
        plt.show()
 
        return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1

if __name__ == "__main__": 
    n1=1
    n2=1
    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
    DATA = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    #print(repr(data))
    alphakl=0.1         # quality degradation rate
    betakl=0.1         # average degradation rate of componenets 
    std_betakl=0.0      # standard deviation of degradation rate of componenets
    aql=0.85          # acceptable quality level triggering quality penality ()
    lambdakl=0.7        # degradation threshold triggering PdM 
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
    
    model   = FJSP_Maintenance_Quality_complex_systems__model(DATA,alphas, aql,qinit,qmin,n_max=nmax,weights=Weights)
  
    
    optsolution1, optCmax1, cputime1, nbrmaint1, avgoq1, qualpenal1 = model.solve()
    print("***!!!!!!!!!! SOLVER FINISHED !!!!!")
    if optsolution1 == 0:
        print("Optimization failed (Infeasible or Unbounded). Skipping Gantt plotting.")
    else:
        print("data=",DATA)
        print("optsolution1=",optsolution1)
        print("weights=",Weights)
        #Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost,NbMaint,AOQ,penality = completionTime_previous(DATA, optsolution1, Weights)
        Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost, NbMaint, AOQ, penality, feasability = completionTime(DATA, optsolution1, Weights)
        print("optCmax1=",optCmax1, " CMAX=",CMAX)
        print("nbrmaint1=",nbrmaint1," NbMaint=",NbMaint)
        print("avgoq1=",avgoq1, " AOQ=",AOQ)
        print("optsolution1=", optsolution1)
        k = 1
        save_JSON(DATA,optsolution1,f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json",Weights)
        result = lire_fichier_json(f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json")
        plotGantt(result, f"Results/Gantts/MILP4testk{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showgantt=True)
        #plotDEGRAD(result, model.data,  f"Results/EHFs/MILP{n1}inst{n2}_figure_{k}",f"MILP-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showdegrad=True)
        plotEHF(result, DATA, f"Results/EHFs/MILP4{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showdegrad=True)
        
        print("optCmax1=", optCmax1," avgoq1=", avgoq1, " qualpenal1=",qualpenal1, " nbrmaint1=",nbrmaint1,  "CPUTime=",cputime1)              
    
        plt.show()   
def Run_solver(data):
    model = FJSP_Maintenance_Quality_complex_systems__model(data)
    model.data=data
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=model.solve()
    return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1


