# -*- coding: utf-8 -*-
"""
Created on Fri Nov 28 17:52:12 2025

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
        data = self.data
        # ------------- 1) Data placeholders (REPLACE with your real data) -------------
        # Sets
        J = range(data.nbJobs)                                 # jobs j
        I = {j: range(data.nbOperationsParJob[j]) for j in J}       # operations i of job j
        K = range(data.nbMachines)                             # machines k
        L = {k: range(data.nbComposants[k]) for k in K}        # components l for machine k
        N = range(self.n_max)                                   # sequence slots n (1..n_max)

        # Parameters
        # p[k][j][i] : processing time; delta[k][l][j][i] : degradation rate
        # m_kl[k][l] : maintenance duration; theta[k][l] : degradation threshold
        # alpha[k][l] : quality weight of degradation
        # Qinit[j], Qmin[j] : initial/min required quality
        p     = data.dureeOperations #[[[data.dureeOperations[k][j][i] for i in range(data.nbOperationsParJob[j])] for j in J] for k in K ]   # shape [K][J][i_j]
        delta = data.degradations  # shape [K][l_k][J][i_j]
        m_kl  = data.dureeMaintenances  # shape [K][l_k]
        theta = data.seuils_degradation   # shape [K][l_k]
        alpha = self.alpha_kl   # shape [K][l_k]
        Qinit = self.Qinitj   # shape [J]
        Qmin  = self.Qjmin   # shape [J]

        # Weights for objective
        lam1, lam2, lam3 = self.weights  # e.g., (1.0, 0.1, 10.0)
        print("lam1, lam2, lam3=",lam1, lam2, lam3)
        # Optional eligibility mask: can_run[k][j][i] in {0,1}
        # If an op (j,i) cannot run on k, set 0 to avoid creating those x's.
        can_run = [[[int(data.dureeOperations[k][j][i]>0) for i in range(data.nbOperationsParJob[j])] for j in J] for k in K ]  # dict or 3D list [K][J][i_j], 1 if eligible else 0
        Nk=[sum([sum([int(data.dureeOperations[k][j][i]>0) for i in range(data.nbOperationsParJob[j])]) for j in J]) for k in K]
        print("nmax=",self.n_max,"Nk=",Nk)
        # Safe Big-M values
        """
        Dmax  = max(max( [[ sum(data.dureeOperations[k][j][i] * data.degradations[k][l][j][i]  
                       for j in J  
                       for i in I[j]) 
                  for l in L[k]
                  ]
                 for k in K
                 ])) # upper bound on cumulative degradation D_{nkl}
        """
        Dmax=1.1
        M_E=max(1, Dmax)
        # tmax (borne sur les dates de début) : somme, par job, du max_k p[k][j][i]
        tmax_j = [
            sum(max(data.dureeOperations[k][j][i] for k in K) for i in I[j])
            for j in J
        ]
        tmax = sum(tmax_j)+sum(data.nbOperationsParJob[j] for j in J)
        print("alpha=",alpha)
        print("max(Qinit)=", max(Qinit))
        print("Dmax=",Dmax)
        MQ    = max(max(Qinit), sum(alpha[k][l] * Dmax for k in K for l in L[k]))
        print("MQ=",MQ)
        # ------------- 2) Model -------------
        model = gp.Model("joint_scheduling_degradation_quality")

        # ------------- 3) Decision variables -------------

        # x[n,k,j,i] = 1 if operation (j,i) is assigned to machine k at slot n
        x = {}
        for n in N:
            for k in K:
                for j in J:
                    for i in I[j]:
                        if can_run[k][j][i]:
                            x[n,k,j,i] = model.addVar(vtype=GRB.BINARY, name=f"x[{n},{k},{j},{i}]")
        # y[n,k,l] = 1 if a maintenance for component l of machine k happens at slot n
        y = {(n,k,l): model.addVar(vtype=GRB.BINARY, name=f"y[{n},{k},{l}]")
            for n in N for k in K for l in L[k]}

        # v[n,k] = 1 if slot n of machine k is used (compactness)
        v = {(n,k): model.addVar(vtype=GRB.BINARY, name=f"v[{n},{k}]") for n in N for k in K}

        # Start times t[j,i]
        t = {(j,i): model.addVar(lb=0.0, name=f"t[{j},{i}]") for j in J for i in I[j]}

        # SlotStart[n,k] = Start time of slot n on machine k
        SlotStart = {(n,k): model.addVar(lb=0.0, ub=tmax,name=f"SlotStart[{n},{k}]") 
                     for n in N for k in K}

        # Degradation accounting
        d = {(n,k,l): model.addVar(lb=0.0, name=f"d[{n},{k},{l}]") for n in N for k in K for l in L[k]}
        D = {(n,k,l): model.addVar(lb=0.0, name=f"D[{n},{k},{l}]") for n in N for k in K for l in L[k]}
        E = {(n,k,l): model.addVar(lb=0.0, name=f"E[{n},{k},{l}]") for n in N for k in K for l in L[k]}
        b = {(n,k,l): model.addVar(vtype=GRB.BINARY, name=f"b[{n},{k},{l}]") for n in N for k in K for l in L[k]}
        # Products for linearizations:
        # pi_yD[n,k,l] = y[n,k,l] * D[n,k,l]
        pi_yD = {(n,k,l): model.addVar(lb=0.0, name=f"pi_yD[{n},{k},{l}]") for n in N for k in K for l in L[k]}
        # pi_xD[n,k,l,j,i] = x[n,k,j,i] * D[n,k,l]
        pi_xD = {}
        for n in N:
            for k in K:
                for l in L[k]:
                    for j in J:
                        for i in I[j]:
                            if can_run[k][j][i]:
                                pi_xD[n,k,l,j,i] = model.addVar(lb=0.0, name=f"pi_xD[{n},{k},{l},{j},{i}]")



        # Quality variables
        Qji = {(j,i): model.addVar(lb=0.0, name=f"Q[{j},{i}]") for j in J for i in I[j]}
        Qj  = {j: model.addVar(lb=0.0, name=f"Qj[{j}]") for j in J}
        ZQ  = {(j,i): model.addVar(vtype=GRB.BINARY, name=f"ZQ[{j},{i}]") for j in J for i in I[j]}

        # Objective auxiliaries
        Cmax    = model.addVar(lb=0.0, name="Cmax")
        Mcount  = model.addVar(lb=0.0, name="Mcount")     # total maintenances
        TotPena = model.addVar(lb=0.0, name="TotPena")
        AvgOQ   = model.addVar(lb=0.0,ub=1.0, name="AvgOQ")
        penal   = {j: model.addVar(vtype=GRB.BINARY, name=f"penal[{j}]") for j in J}

        model.update()

        # ------------- 4) Constraints -------------

        # A) Slot-use and contiguity, and link v <-> x
        for k in K:
            for n in N:
                # v[n,k] = sum_{j,i} x[n,k,j,i]
                model.addConstr(v[n,k] == qsum(x[n,k,j,i] for j in J for i in I[j] if (n,k,j,i) in x), name=f"Cstr-A0_{k}{n}")
            for n in N[:-1]:
                model.addConstr(v[n,k] >= v[n+1,k], name=f"Cstr-A1_{k}{n}")  # compactness (no holes)

        # B) Each operation scheduled exactly once (somewhere)
        for j in J:
            for i in I[j]:
                model.addConstr(qsum(x[n,k,j,i] for n in N for k in K if (n,k,j,i) in x) == 1, name=f"Cstr-B_{j}{i}")

        # C) Degradation per slot and cumulative recursion
        for n in N:
            for k in K:
                for l in L[k]:
                    model.addConstr(
                        d[n,k,l] == qsum(x[n,k,j,i] * p[k][j][i] * delta[k][l][j][i] for j in J for i in I[j] if (n,k,j,i) in x), name=f"Cstr-C_{n}{k}{l}"
                    )

        # D recursion: D[0]=d[0]; D[n+1]=D[n] - pi_yD[n] + d[n+1]
        for k in K:
            for l in L[k]:
                """
                model.addConstr(D[0,k,l] == d[0,k,l], name=f"Cstr-D00_{k}{l}")
                for n in N[:-1]:
                    model.addConstr(D[n+1,k,l] == D[n,k,l] - pi_yD[n,k,l] + d[n+1,k,l], name=f"Cstr-D01_{k}{l}")
                """
                model.addConstr( E[0,k,l] == qsum(x[0,k,j,i]*p[k][j][i]*delta[k][l][j][i] for j in J for i in I[j] if (0,k,j,i) in x), name=f"Cstr-D01_{k}{l}")
                model.addConstr( D[0,k,l] <= E[0,k,l] + M_E * (1 - b[0,k,l]),                                                               name=f"Cstr-D02_{k}{l}")
                model.addConstr( D[0,k,l] >= E[0,k,l] - M_E * (1 - b[0,k,l]) ,                                       name=f"Cstr-D03_{k}{l}")
                model.addConstr( D[0,k,l] <= 1 ,                                                                     name=f"Cstr-D04_{k}{l}")
                model.addConstr( D[0,k,l] >= 1 - M_E * b[0,k,l],                                                     name=f"Cstr-D05_{k}{l}")
                model.addConstr( E[0,k,l] <= 1 + M_E * (1 - b[0,k,l]),                                               name=f"Cstr-D06_{k}{l}")
                model.addConstr( E[0,k,l] >= 1 - M_E * b[0,k,l],                                                     name=f"Cstr-D07_{k}{l}")
                 
                for n in range(1,self.n_max):
                    model.addConstr( E[n,k,l] == D[n-1,k,l] - pi_yD[n-1,k,l] + qsum(x[n,k,j,i]*p[k][j][i]*delta[k][l][j][i] for j in J for i in I[j] if (n,k,j,i) in x), name=f"Cstr-D08_{k}{l}{n}" )
                for n in range(self.n_max):
                    
                    model.addConstr( D[n,k,l] <= E[n,k,l] + M_E * (1 - b[n,k,l]),                                                               name=f"Cstr-D09_{k}{l}{n}")
                    model.addConstr( D[n,k,l] >= E[n,k,l] - M_E * (1 - b[n,k,l]) ,                                       name=f"Cstr-D010_{k}{l}{n}")
                    model.addConstr( D[n,k,l] <= 1 ,                                                                     name=f"Cstr-D011_{k}{l}{n}")
                    model.addConstr( D[n,k,l] >= 1 - M_E * b[n,k,l],                                                     name=f"Cstr-D012_{k}{l}{n}")
                    model.addConstr( E[n,k,l] <= 1 + M_E * (1 - b[n,k,l]),                                               name=f"Cstr-D013_{k}{l}{n}")
                    model.addConstr( E[n,k,l] >= 1 - M_E * b[n,k,l],                                                     name=f"Cstr-D014_{k}{l}{n}")     
        # D1) McCormick for pi_yD = y * D
        for n in N:
            for k in K:
                for l in L[k]:
                    model.addConstr(pi_yD[n,k,l] >= 0,                                 name=f"Cstr-D10_{n}{k}{l}")
                    model.addConstr(pi_yD[n,k,l] <= Dmax * y[n,k,l],                   name=f"Cstr-D11_{n}{k}{l}")
                    model.addConstr(pi_yD[n,k,l] <= D[n,k,l],                          name=f"Cstr-D12_{n}{k}{l}")
                    model.addConstr(pi_yD[n,k,l] >= D[n,k,l] - Dmax * (1 - y[n,k,l]),  name=f"Cstr-D13_{n}{k}{l}")

        # D2) McCormick for pi_xD = x * D
        for n,k,l,j,i in pi_xD:
            model.addConstr(pi_xD[n,k,l,j,i] >= 0,                                  name=f"Cstr-D20_{n}{k}{l}{j}{i}")
            model.addConstr(pi_xD[n,k,l,j,i] <= Dmax * x[n,k,j,i],                  name=f"Cstr-D21_{n}{k}{l}{j}{i}")
            model.addConstr(pi_xD[n,k,l,j,i] <= D[n,k,l],                           name=f"Cstr-D22_{n}{k}{l}{j}{i}")
            model.addConstr(pi_xD[n,k,l,j,i] >= D[n,k,l] - Dmax * (1 - x[n,k,j,i]), name=f"Cstr-D23_{n}{k}{l}{j}{i}")

        # E) Maintenance trigger vs threshold (one-sided ⇒ trigger if above threshold)
        for n in N:
            for k in K:
                for l in L[k]:
                    model.addConstr(MQ * y[n,k,l] - D[n,k,l] + theta[k][l] >= 0.001, name=f"Cstr-E0_{n}{k}{l}")
                    #model.addConstr(y[n,k,l] - D[n,k,l] <= 0        , name=f"Cstr-E1_{n}{k}{l}")  # softer; or use two-sided if needed
                    model.addConstr(MQ *y[n,k,l]  <= MQ + D[n,k,l] - theta[k][l]         , name=f"Cstr-E2_{n}{k}{l}")

        # F) Slot Timing Evolution: Slot n+1 starts after Slot n finishes + maintenance
        for k in K:
            model.addConstr(SlotStart[0, k] == 0, name=f"Cstr-F0_{k}")
            for n in range(len(N) - 1):
                #proc_time = qsum(x[n,k,j,i] * p[k][j][i] for j in J for i in I[j])
                #maint_time = qsum(y[n,k,l] * m_kl[k][l] for l in L[k])
                
                model.addConstr(SlotStart[n+1, k] >= SlotStart[n, k] + qsum(x[n,k,j,i] * p[k][j][i] for j in J for i in I[j]) + qsum(y[n,k,l] * m_kl[k][l] for l in L[k]), name=f"Cstr-F_{k}_{n}")
                """
                for j in J:
                    for i in I[j]:
                        model.addConstr(
                            SlotStart[n+1, k] >= t[j,i] + x[n,k,j,i] * p[k][j][i] + qsum(y[n,k,l] * m_kl[k][l] for l in L[k]) - 
                                        tmax * (1 - x[n,k,j,i]) , name=f"Cstr-F1_{k}_{n}_{j}{i}"
                        )
                        model.addConstr(
                            SlotStart[n, k] <= SlotStart[n+1, k] - x[n,k,j,i] * p[k][j][i] - qsum(y[n,k,l] * m_kl[k][l] for l in L[k]) , name=f"Cstr-F2_{k}_{n}_{j}{i}"
                        )
                            """
        # I) Precedence within each job
        for j in J:
            for i in I[j][:-1]:
                # t[j,i+1] >= t[j,i] + processing time of operation (j,i) on its chosen (n,k)
                model.addConstr(
                    t[j,i+1] >= t[j,i] + qsum(x[n,k,j,i] * p[k][j][i] for n in N for k in K if (n,k,j,i) in x), name=f"Cstr-I_{j}{i}"
                )

        # J) Link t[j,i] to SlotStart
        # If x[n,k,j,i] == 1, then t[j,i] >= SlotStart[n,k]
        for j in J:
            for i in I[j]:
                # model.addConstr(qsum(x[n,k,j,i] for n in N for k in K)==1 , name=f"Cstr-J1_{j}{i}") # Already in B
                for n in N:
                    for k in K:
                        if can_run[k][j][i]:
                            # Big-M constraint
                            model.addConstr(t[j,i] >= SlotStart[n, k] - tmax * (1 - x[n,k,j,i]), name=f"J0_{j}_{i}_{n}_{k}")
                            if n>1:
                                model.addConstr(t[j,i] >= SlotStart[n-1, k] + qsum(x[n-1,k,j2,i2] * p[k][j2][i2] for j2 in J for i2 in I[j2]) + qsum(y[n-1,k,l] * m_kl[k][l] for l in L[k]) - tmax * (1 - x[n,k,j,i]), name=f"J0_{j}_{i}_{n}_{k}")
                            if n < self.n_max-1:    
                                model.addConstr(t[j,i] <= SlotStart[n+1, k] + tmax * (1 - x[n,k,j,i]), name=f"J1_{j}_{i}_{n}_{k}")
                                model.addConstr(t[j,i] <=tmax, name=f"J2_{j}_{i}_{n}_{k}")
                                
        # K) Quality recursion with Big-M (Qji[j,i] = max(0, prev - loss))
        for j in J:
            # i = 0
            loss0 = qsum(alpha[k][l] * pi_xD[n,k,l,j,0]
                        for n in N for k in K for l in L[k] if (n,k,l,j,0) in pi_xD)
            # Q[j,0] = max(0, Qinit[j] - loss0)
            model.addConstr(loss0 - Qinit[j] <= MQ * (1 - ZQ[j,0]) ,            name=f"Cstr-K0_{j}")
            model.addConstr(Qinit[j] - loss0 <= MQ * ZQ[j,0],                   name=f"Cstr-K1_{j}")
            model.addConstr(Qji[j,0] <= Qinit[j] - loss0 + MQ * (1 - ZQ[j,0]),  name=f"Cstr-K2_{j}")
            model.addConstr(Qji[j,0] >= Qinit[j] - loss0,                       name=f"Cstr-K3_{j}")
            model.addConstr(Qji[j,0] <= MQ * ZQ[j,0],                           name=f"Cstr-K4_{j}")
            # i >= 1
            for i in I[j][1:]:
                lossi = qsum(alpha[k][l] * pi_xD[n,k,l,j,i]
                            for n in N for k in K for l in L[k] if (n,k,l,j,i) in pi_xD)
                model.addConstr(lossi - Qji[j,i-1] <= MQ * (1 - ZQ[j,i]),               name=f"Cstr-K50_{j}{i}" )
                model.addConstr(Qji[j,i-1] - lossi <= MQ * ZQ[j,i],                     name=f"Cstr-K51_{j}{i}")
                model.addConstr(Qji[j,i] <= Qji[j,i-1] - lossi + MQ * (1 - ZQ[j,i]),    name=f"Cstr-K52_{j}{i}")
                model.addConstr(Qji[j,i] >= Qji[j,i-1] - lossi,                         name=f"Cstr-K53_{j}{i}")
                model.addConstr(Qji[j,i] <= MQ * ZQ[j,i],                               name=f"Cstr-K54_{j}{i}")

            # Link final Qj
            last_i = I[j][-1]
            model.addConstr(Qj[j] == Qji[j,last_i],                           name=f"Cstr-K6_{j}")

        # L) Quality penalties
        for j in J:
            model.addConstr(penal[j] >= Qmin[j] - Qj[j],    name=f"Cstr-L00_{j}")
            model.addConstr(penal[j] >= 0,                  name=f"Cstr-L01_{j}")
            model.addConstr(penal[j] <= 1,                  name=f"Cstr-L02_{j}")
        model.addConstr(TotPena == qsum(penal[j] for j in J), name=f"Cstr-L1")
        model.addConstr(AvgOQ == qsum((1-Qj[j]) for j in J)/data.nbJobs, name=f"Cstr-L2")
        # M) Makespan and maintenance counter
        for j in J:
            last_i = I[j][-1]
            model.addConstr(
                Cmax >= t[j,last_i] +
                qsum(x[n,k,j,last_i] * p[k][j][last_i] for n in N for k in K), name=f"Cstr-M0_{j}"
            )
        model.addConstr(Mcount == qsum(y[n,k,l] for n in N for k in K for l in L[k]),  name=f"Cstr-M")
        
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
            for k in K:
                for n in N:
                    for j in J:
                        for i in I[j]:
                            if (n,k,j,i) in x and x[n,k,j,i].X > 0.5:
                                #schedule.append((k,n,j,i,t[j,i].X,p[k][j][i]))
                                schedule.append((k,n,SlotStart[n, k].X,j,i,t[j,i].X,p[k][j][i],(t[j,i].X+p[k][j][i]) ))
            schedule.sort()
            for rec in schedule:
                print("Machine %d, slot %d starts at %d: job %d op %d starts at %.2f (dur=%.2f) and ends at %.1f" % rec)
      
            
        
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

        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                degradation_sumi = sum(pi_xD[n,k,l,j,i].x * self.alpha_kl[k][l] for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k]))
                aa=[(k,n) for n in range(self.n_max) for k in range(self.data.nbMachines) if x[n,k,j,i].x]
                bb=[D[n,k,l].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k]) if x[n,k,j,i].x]
                #print(f"j={j} i={i} x={aa} D={bb} degradation_sum{i} {degradation_sumi}")
                Dkln=[D[n,k,l].x for l in range(self.data.nbComposants[k])]
        
        optsolution1 = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [sum(k*int(x[n,k,j,i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            #[[[max([(int(x[n,k,j,i].x)*int(y[n][k][l].x)) for n in range(self.n_max) for k in range(self.data.nbMachines)])  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))]
            [[[False  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))],
            [[int(t[j,i].x) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)],
            [sum(n*int(x[n,k,j,i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])]
        ]
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                mach=sum(k*int(x[n,k,j,i].x) for n in range(self.n_max) for k in range(self.data.nbMachines))
                rank=sum(n*int(x[n,mach,j,i].x) for n in range(self.n_max))
                maxdeg=max([D[rank,mach,l].x for l in range(self.data.nbComposants[mach])] )
                stime=int(t[j,i].x)
                ptime=sum([int(x[n,k,j,i].x) * self.data.dureeOperations[k][j][i]  for n in range(self.n_max)  for k in range(self.data.nbMachines)])
                maintafter=False
                for l in range(self.data.nbComposants[mach]):
                    if y[rank,mach,l].x:
                        maintafter=True
                        break
                #print("O_%d,%d : machine=%d  start=%d end=%d rank=%d max_machDeg=%.2f maintAfter=%s" % (j+1,i+1,mach+1,stime,stime+ptime,rank, maxdeg,maintafter))
                
        for k in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[k]):
                for j in range(self.data.nbJobs):
                    #temp=False
                    for i in range(self.data.nbOperationsParJob[j]):
                        for n in range(self.n_max):
                            temp=(x[n,k,j,i].x and y[n,k,l].x)
                            if temp==True:
                                optsolution1[2][l][j][i] =True
                                #print("break 1 -->", " on machine=",k+1 , "component =",l+1, " job ",j+1," operation ",i+1, " n=",n+1)
                                break
        avgoq1=sum((1-Qj[j].x) for j in range(self.data.nbJobs))/self.data.nbJobs
        #for k in range(self.data.nbMachines):
        #    print([["{:.2f}".format(D[n,k,l].x) for l in range(self.data.nbComposants[k]) ] for n in range(self.n_max)])
        
        for j in range(self.data.nbJobs):
            plt.plot([Qji[j,i].x for i in range(self.data.nbOperationsParJob[j])])
            plt.title(f"Qj evolution of job {j}",fontsize=15)
            plt.show()
            #print([Qji[j,i].x for i in range(self.data.nbOperationsParJob[j])])
            #print([max(pi_xD[n,k,l,j,i].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k])) for i in range(self.data.nbOperationsParJob[j])])
        plt.plot([Qj[j].x for j in range(self.data.nbJobs)])
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
    alphakl=0.5         # quality degradation rate
    betakl=0.1         # average degradation rate of componenets 
    std_betakl=0.0      # standard deviation of degradation rate of componenets
    aql=0.95          # acceptable quality level triggering quality penality ()
    lambdakl=1.0        # degradation threshold triggering PdM 
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
    Weights = [1.0,1.0,1.0]
    alphas  = [[alphakl for l in range(nbComposants[k])] for k in range(nbMachines)]
    qinit   = [1.0 for j in range(nbJobs)]  # Exemple de taux de qualité initiale
    qmin    = [aql for j in range(nbJobs)]   # Exemple de taux de qualité minimale acceptable
    
    model   = FJSP_Maintenance_Quality_complex_systems__model(DATA,alphas, aql,qinit,qmin,n_max=nmax,weights=Weights)
  
    
    optsolution1, optCmax1, cputime1, nbrmaint1, avgoq1, qualpenal1 = model.solve()
    #print(optsolution1)

    #Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost,NbMaint,AOQ,penality = completionTime_previous(DATA, optsolution1, Weights)
    Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost,NbMaint,AOQ,penality,feasability = completionTime(model.data, optsolution1, Weights)
    
    print("optCmax1=",optCmax1, " CMAX=",CMAX)
    print("nbrmaint1=",nbrmaint1," NbMaint=",NbMaint)
    print("avgoq1=",avgoq1, " AOQ=",AOQ)
    #print("optsolution1=",optsolution1)
    k=1
    save_JSON(model.data,optsolution1,f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json",Weights)
    result = lire_fichier_json(f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json")
    plotGantt(result, f"Results/Gantts/MILP4testk{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showgantt=True)
    #plotDEGRAD(result, model.data,  f"Results/EHFs/MILP{n1}inst{n2}_figure_{k}",f"MILP-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showdegrad=True)
    plotEHF(   result, model.data,  f"Results/EHFs/MILP4{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showdegrad=True)
    
    print("optCmax1=", optCmax1," avgoq1=", avgoq1, " qualpenal1=",qualpenal1, " nbrmaint1=",nbrmaint1,  "CPUTime=",cputime1)              
   
    plt.show()   
def Run_solver(data):
    model = FJSP_Maintenance_Quality_complex_systems__model(data)
    model.data=data
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=model.solve()
    return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1
