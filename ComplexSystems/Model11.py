# -*- coding: utf-8 -*-
"""
Created on Mon Feb  9 11:05:15 2026

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

class FJSP_Maintenance_Quality_complex_systems_model:
    """
    Position-based MILP (Gurobi), Option B:
      - Maintenance happens AFTER the operation/slot where D_after exceeds theta
      - Maintenance duration after a slot = SUM of component maintenance durations whose threshold is exceeded
      - Quality loss uses D_after

    Returns (same structure as your previous version):
      optsolution, optCmax, cputime, nbrmaint, avgoq, qualpenal

    where:
      optsolution = [seq_jobs, seq_machs, y_set, t_matrix, rank]
        - seq_jobs: list of jobs in global order (sorted by start time)
        - seq_machs: list of machines corresponding to seq_jobs
        - y_set: set of tuples (j,i,l) meaning maintenance AFTER operation (j,i) for component l
                (k implicit via machine assignment of (j,i))
        - t_matrix: [[T[j,i] for i] for j]
        - rank: placeholder list of 1's
    """

    def __init__(self, datas, alphas, aql, qinit, qmin, weights=(1.0, 0.0, 0.0)):
        self.data = datas
        self.alpha_kl = alphas
        self.AQL = aql
        self.Qinitj = qinit
        self.Qjmin = qmin
        self.weights = weights

    def solve(self, time_limit=3600, mip_gap=0.01, threads=0, verbose=True):
        data = self.data
        lam1, lam2, lam3 = self.weights

        # -------------------------
        # Sets
        # -------------------------
        J = range(data.nbJobs)
        I = {j: range(data.nbOperationsParJob[j]) for j in J}
        K = range(data.nbMachines)
        L = {k: range(data.nbComposants[k]) for k in K}

        O = [(j, i) for j in J for i in I[j]]   # all operations
        N = len(O)

        # eligible operations per machine
        O_k = {k: [(j, i) for (j, i) in O if data.dureeOperations[k][j][i] > 0] for k in K}

        # positions per machine: Nk = number of eligible operations
        R = {k: range(len(O_k[k])) for k in K}  # r = 0..Nk-1

        # -------------------------
        # Bounds / Big-M (tight-ish)
        # -------------------------
        Dmax_kl = {}
        for k in K:
            for l in L[k]:
                th = float(data.seuils_degradation[k][l])
                # if you have a better bound, use it; this is a safe-ish default
                Dmax_kl[k, l] = max(1.0, 1.2 * th)

        # LossSlot upper bound per machine/slot: sum_l alpha[k][l] * Dmax_kl[k,l]
        LossSlotMax = {}
        for k in K:
            LossSlotMax[k] = float(sum(self.alpha_kl[k][l] * Dmax_kl[k, l] for l in L[k]))

        # rough time bound
        totP = 0.0
        for (j, i) in O:
            maxp = 0.0
            for k in K:
                maxp = max(maxp, float(data.dureeOperations[k][j][i]))
            totP += maxp
        maxMaintSum = sum(sum(float(data.dureeMaintenances[k][l]) for l in L[k]) for k in K)
        tmax = max(1.0, totP + N * maxMaintSum)

        # -------------------------
        # Model
        # -------------------------
        m = gp.Model("FJSP_PositionBased_OptionB_SumMaint_Quality_Dafter")
        if not verbose:
            m.Params.OutputFlag = 0

        # -------------------------
        # Variables
        # -------------------------

        # a[j,i,k,r] = 1 if op (j,i) on machine k at position r (only if eligible)
        a = {}
        for k in K:
            for r in R[k]:
                for (j, i) in O_k[k]:
                    a[j, i, k, r] = m.addVar(vtype=GRB.BINARY, name=f"a[{j},{i},{k},{r}]")

        # slot start times S[k,r]
        S = {(k, r): m.addVar(lb=0.0, ub=tmax, vtype=GRB.CONTINUOUS, name=f"S[{k},{r}]")
             for k in K for r in R[k]}

        # operation start times T[j,i]
        T = {(j, i): m.addVar(lb=0.0, ub=tmax, vtype=GRB.CONTINUOUS, name=f"T[{j},{i}]")
             for (j, i) in O}

        # slot occupancy U[k,r]
        U = {(k, r): m.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"U[{k},{r}]")
             for k in K for r in R[k]}

        # y[k,l,r] maintenance AFTER slot r for component l
        y = {(k, l, r): m.addVar(vtype=GRB.BINARY, name=f"y[{k},{l},{r}]")
             for k in K for l in L[k] for r in R[k]}

        # degradation before/after slot
        D_before = {(k, l, r): m.addVar(lb=0.0, ub=Dmax_kl[k, l], vtype=GRB.CONTINUOUS, name=f"Db[{k},{l},{r}]")
                    for k in K for l in L[k] for r in R[k]}
        D_after = {(k, l, r): m.addVar(lb=0.0, ub=Dmax_kl[k, l], vtype=GRB.CONTINUOUS, name=f"Da[{k},{l},{r}]")
                   for k in K for l in L[k] for r in R[k]}

        # w = y * D_after for reset linearization
        w = {(k, l, r): m.addVar(lb=0.0, ub=Dmax_kl[k, l], vtype=GRB.CONTINUOUS, name=f"w[{k},{l},{r}]")
             for k in K for l in L[k] for r in R[k]}

        # Quality: LossSlot[k,r] = sum_l alpha[k][l]*D_after[k,l,r]
        LossSlot = {(k, r): m.addVar(lb=0.0, ub=LossSlotMax[k], vtype=GRB.CONTINUOUS, name=f"LossSlot[{k},{r}]")
                    for k in K for r in R[k]}

        # qloss[j,i,k,r] = a[j,i,k,r] * LossSlot[k,r]  (McCormick)
        qloss = {}
        for k in K:
            for r in R[k]:
                for (j, i) in O_k[k]:
                    qloss[j, i, k, r] = m.addVar(lb=0.0, ub=LossSlotMax[k], vtype=GRB.CONTINUOUS,
                                                 name=f"qloss[{j},{i},{k},{r}]")

        # LossOp[j,i] = sum_{k,r} qloss
        LossOp = {(j, i): m.addVar(lb=0.0, ub=max(LossSlotMax.values()) if len(K) else 0.0,
                                  vtype=GRB.CONTINUOUS, name=f"LossOp[{j},{i}]")
                  for (j, i) in O}

        # Quality evolution per op
        Qji = {(j, i): m.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"Q[{j},{i}]")
               for (j, i) in O}
        ZQ = {(j, i): m.addVar(vtype=GRB.BINARY, name=f"ZQ[{j},{i}]")
              for (j, i) in O}
        Qj = {j: m.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"Qj[{j}]") for j in J}

        penal = {j: m.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"penal[{j}]") for j in J}
        TotPena = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="TotPena")

        # Objective auxiliaries
        Cmax = m.addVar(lb=0.0, ub=tmax, vtype=GRB.CONTINUOUS, name="Cmax")
        Mcount = m.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="Mcount")

        m.update()

        # -------------------------
        # Key constraints
        # -------------------------

        # (1) Occupancy definition
        for k in K:
            for r in R[k]:
                m.addConstr(U[k, r] == gp.quicksum(a[j, i, k, r] for (j, i) in O_k[k]),
                            name=f"occ[{k},{r}]")
                m.addConstr(U[k, r] <= 1.0, name=f"occ_ub[{k},{r}]")

        # (2) Each operation assigned exactly once
        for (j, i) in O:
            m.addConstr(
                gp.quicksum(a[j, i, k, r]
                            for k in K if (j, i) in O_k[k]
                            for r in R[k]) == 1,
                name=f"assign[{j},{i}]"
            )

        # (3) No holes: U[k,r+1] <= U[k,r]
        for k in K:
            rk = list(R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                m.addConstr(U[k, r + 1] <= U[k, r], name=f"contig[{k},{r}]")

        # (4) Link T[j,i] = sum a * S
        for (j, i) in O:
            m.addConstr(
                T[j, i] == gp.quicksum(a[j, i, k, r] * S[k, r]
                                       for k in K if (j, i) in O_k[k]
                                       for r in R[k]),
                name=f"linkT[{j},{i}]"
            )

        # (5) Job precedence
        for j in J:
            for i in list(I[j])[:-1]:
                m.addConstr(
                    T[j, i + 1] >= T[j, i] + gp.quicksum(a[j, i, k, r] * data.dureeOperations[k][j][i]
                                                         for k in K if (j, i) in O_k[k]
                                                         for r in R[k]),
                    name=f"jobprec[{j},{i}]"
                )

        # (6) Machine chain with summed maintenance after slot
        for k in K:
            rk = list(R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                Pkr = gp.quicksum(a[j, i, k, r] * data.dureeOperations[k][j][i] for (j, i) in O_k[k])
                MaintKr = gp.quicksum(y[k, l, r] * data.dureeMaintenances[k][l] for l in L[k])
                m.addConstr(S[k, r + 1] >= S[k, r] + Pkr + MaintKr, name=f"chain[{k},{r}]")

        # (7) Maintenance off on empty slots: y <= U
        for k in K:
            for r in R[k]:
                for l in L[k]:
                    m.addConstr(y[k, l, r] <= U[k, r], name=f"y_off_empty[{k},{l},{r}]")

        # (8) Degradation accumulation: D_after = D_before + sum a * (p*delta)
        for k in K:
            for r in R[k]:
                for l in L[k]:
                    Inc = gp.quicksum(
                        a[j, i, k, r] * (data.dureeOperations[k][j][i] * data.degradations[k][l][j][i])
                        for (j, i) in O_k[k]
                    )
                    m.addConstr(D_after[k, l, r] == D_before[k, l, r] + Inc, name=f"Dacc[{k},{l},{r}]")

        # (9) Initialize D_before at first slot = 0
        for k in K:
            if len(O_k[k]) == 0:
                continue
            for l in L[k]:
                m.addConstr(D_before[k, l, 0] == 0.0, name=f"Dinit[{k},{l}]")

        # (10) Reset propagation: D_before[r+1] = D_after[r] - w, w = y * D_after
        for k in K:
            rk = list(R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                for l in L[k]:
                    m.addConstr(D_before[k, l, r + 1] == D_after[k, l, r] - w[k, l, r],
                                name=f"Dprop[{k},{l},{r}]")

                    Dmax = Dmax_kl[k, l]
                    m.addConstr(w[k, l, r] <= Dmax * y[k, l, r], name=f"w1[{k},{l},{r}]")
                    m.addConstr(w[k, l, r] <= D_after[k, l, r], name=f"w2[{k},{l},{r}]")
                    m.addConstr(w[k, l, r] >= D_after[k, l, r] - Dmax * (1 - y[k, l, r]),
                                name=f"w3[{k},{l},{r}]")

        # (11) Trigger: if D_after > theta then y=1 (>=theta in MILP)
        for k in K:
            for r in R[k]:
                for l in L[k]:
                    th = float(data.seuils_degradation[k][l])
                    Mtrig = max(1e-6, Dmax_kl[k, l] - th)
                    m.addConstr(D_after[k, l, r] - th <= Mtrig * y[k, l, r], name=f"trigger[{k},{l},{r}]")

        # -------------------------
        # Quality using D_after
        # -------------------------

        # LossSlot[k,r] = sum_l alpha[k][l] * D_after[k,l,r]
        for k in K:
            for r in R[k]:
                m.addConstr(
                    LossSlot[k, r] == gp.quicksum(self.alpha_kl[k][l] * D_after[k, l, r] for l in L[k]),
                    name=f"lossSlotDef[{k},{r}]"
                )
                # Optional tightening: LossSlot <= LossSlotMax * U
                m.addConstr(LossSlot[k, r] <= LossSlotMax[k] * U[k, r], name=f"lossSlotEmpty[{k},{r}]")

        # qloss[j,i,k,r] = a * LossSlot (McCormick, a is binary)
        for k in K:
            Mloss = LossSlotMax[k]
            for r in R[k]:
                for (j, i) in O_k[k]:
                    m.addConstr(qloss[j, i, k, r] <= LossSlot[k, r], name=f"ql1[{j},{i},{k},{r}]")
                    m.addConstr(qloss[j, i, k, r] <= Mloss * a[j, i, k, r], name=f"ql2[{j},{i},{k},{r}]")
                    m.addConstr(qloss[j, i, k, r] >= LossSlot[k, r] - Mloss * (1 - a[j, i, k, r]),
                                name=f"ql3[{j},{i},{k},{r}]")
                    m.addConstr(qloss[j, i, k, r] >= 0.0, name=f"ql4[{j},{i},{k},{r}]")

        # LossOp[j,i] = sum_{k,r} qloss
        for (j, i) in O:
            m.addConstr(
                LossOp[j, i] == gp.quicksum(qloss[j, i, k, r]
                                            for k in K if (j, i) in O_k[k]
                                            for r in R[k]),
                name=f"LossOpDef[{j},{i}]"
            )

        # Quality recurrence: Qji = max(0, prev - LossOp)
        # max(0, expr) linearization using ZQ (same pattern as your previous model)
        M_Q = 1.0  # quality is within [0,1], so a tight M is 1

        for j in J:
            # i = 0: Q[j,0] = max(0, Qinitj[j] - LossOp[j,0])
            expr0 = float(self.Qinitj[j]) - LossOp[j, 0]
            m.addConstr(-expr0 <= M_Q * (1 - ZQ[j, 0]), name=f"Q0_a[{j}]")  # expr0 >= 0 when ZQ=1
            m.addConstr(expr0 <= M_Q * ZQ[j, 0], name=f"Q0_b[{j}]")
            m.addConstr(Qji[j, 0] <= expr0 + M_Q * (1 - ZQ[j, 0]), name=f"Q0_c[{j}]")
            m.addConstr(Qji[j, 0] >= expr0, name=f"Q0_d[{j}]")
            m.addConstr(Qji[j, 0] <= M_Q * ZQ[j, 0], name=f"Q0_e[{j}]")

            for i in list(I[j])[1:]:
                expri = Qji[j, i - 1] - LossOp[j, i]
                m.addConstr(-expri <= M_Q * (1 - ZQ[j, i]), name=f"Qi_a[{j},{i}]")
                m.addConstr(expri <= M_Q * ZQ[j, i], name=f"Qi_b[{j},{i}]")
                m.addConstr(Qji[j, i] <= expri + M_Q * (1 - ZQ[j, i]), name=f"Qi_c[{j},{i}]")
                m.addConstr(Qji[j, i] >= expri, name=f"Qi_d[{j},{i}]")
                m.addConstr(Qji[j, i] <= M_Q * ZQ[j, i], name=f"Qi_e[{j},{i}]")

            last_i = data.nbOperationsParJob[j] - 1
            m.addConstr(Qj[j] == Qji[j, last_i], name=f"QjLink[{j}]")

        # Penalties and TotPena
        for j in J:
            m.addConstr(penal[j] >= float(self.Qjmin[j]) - Qj[j], name=f"pen_a[{j}]")
            m.addConstr(penal[j] >= 0.0, name=f"pen_b[{j}]")
        m.addConstr(TotPena == gp.quicksum(penal[j] for j in J), name="TotPenaDef")

        # -------------------------
        # Makespan and maintenance count
        # -------------------------
        for j in J:
            last_i = data.nbOperationsParJob[j] - 1
            proc_last = gp.quicksum(a[j, last_i, k, r] * data.dureeOperations[k][j][last_i]
                                    for k in K if (j, last_i) in O_k[k]
                                    for r in R[k])
            m.addConstr(Cmax >= T[j, last_i] + proc_last, name=f"Cmax[{j}]")

        m.addConstr(Mcount == gp.quicksum(y[k, l, r] for k in K for r in R[k] for l in L[k]), name="McountDef")

        # -------------------------
        # Objective
        # -------------------------
        m.setObjective(lam1 * Cmax + lam2 * Mcount + lam3 * TotPena, GRB.MINIMIZE)

        # Params
        m.Params.TimeLimit = time_limit
        m.Params.MIPGap = mip_gap
        m.Params.Threads = threads

        # -------------------------
        # Solve
        # -------------------------
        t0 = time.perf_counter()
        m.optimize()
        cputime = time.perf_counter() - t0

        if m.Status in [GRB.INFEASIBLE, GRB.INF_OR_UNBD]:
            m.setParam(GRB.Param.DualReductions, 0)
            m.optimize()
            if m.Status == GRB.INFEASIBLE and verbose:
                print("\nModel is INFEASIBLE. Computing IIS...")
                m.computeIIS()
                m.write("iis.ilp")
                
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
                
            return 0, 0, cputime, 0, 0, 0

        optCmax = float(Cmax.X)
        nbrmaint = float(Mcount.X)
        qualpenal = float(sum(penal[j].X for j in J))
        avgoq = float(sum((1.0 - Qj[j].X) for j in J) / data.nbJobs)

        if verbose:
            print(f"Obj={m.objVal:.6f}, Cmax={optCmax:.3f}, Maint={nbrmaint:.0f}, TotPena={TotPena.X:.6f}, AvgOQ={avgoq:.6f}")

        # -------------------------
        # Extract solution in same format as before
        # -------------------------

        # Determine for each op (j,i): assigned (k,r), and T
        assign = {}  # (j,i) -> (k,r)
        for k in K:
            for r in R[k]:
                for (j, i) in O_k[k]:
                    if a[j, i, k, r].X > 0.5:
                        assign[(j, i)] = (k, r)

        # Global order by start time then machine then job/op
        op_records = [(T[j, i].X, assign[(j, i)][0], j, i, assign[(j, i)][1]) for (j, i) in O]
        op_records.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

        seq_jobs = [j for (_, _, j, i, _) in op_records]
        seq_machs = [k for (_, k, j, i, _) in op_records]

        # y_set: (j,i,l) if component l maintained after op (j,i)
        # Here, op (j,i) sits in slot (k,r) so we read y[k,l,r]
        y_set = set()
        yset2=[[[False  for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)] for l in range(max(data.nbComposants))]
        for (j, i) in O:
            k, r = assign[(j, i)]
            for l in L[k]:
                if y[k, l, r].X > 0.5:
                    y_set.add((j, i, l))
                    yset2[l][j][i] =True

        # t_matrix
        t_matrix = [[float(T[j, i].X) for i in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)]

        rank = [1] * len(seq_jobs)  # placeholder (kept for compatibility)

        #optsolution = [seq_jobs, seq_machs, y_set, t_matrix, rank]
        optsolution = [seq_jobs, seq_machs, yset2, t_matrix, rank]
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                ind=i+sum(self.data.nbOperationsParJob[j1] for j1 in range(j))
                mach=int(optsolution1[1][ind])
                #print(f"j={j+1}, i={i+1}, optsolution1[1][{ind}]={optsolution1[1][ind]}")
                #print("machine=",ind+1)
                machji=self.data.dureeOperations[mach][j][i] #sum(data.dureeOperations[j][i][k]*int(x_ijkn[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) 
                print(f"debut_{j+1}{i+1}={optsolution1[3][j][i]}-- machine = {mach+1} -- duree ={machji}")for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                ind=i+sum(self.data.nbOperationsParJob[j1] for j1 in range(j))
                mach=int(optsolution1[1][ind])
                #print(f"j={j+1}, i={i+1}, optsolution1[1][{ind}]={optsolution1[1][ind]}")
                #print("machine=",ind+1)
                machji=self.data.dureeOperations[mach][j][i] #sum(data.dureeOperations[j][i][k]*int(x_ijkn[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) 
                print(f"debut_{j+1}{i+1}={optsolution1[3][j][i]}-- machine = {mach+1} -- duree ={machji}")


        return optsolution, optCmax, cputime, nbrmaint, avgoq, qualpenal
if __name__ == "__main__": 
    n1=1
    n2=1
    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
    DATA = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    #print(repr(data))
    alphakl=0.2         # quality degradation rate
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
    Weights = [1.0,0.0,1.0]
    alphas  = [[alphakl for l in range(nbComposants[k])] for k in range(nbMachines)]
    qinit   = [1.0 for j in range(nbJobs)]  # Exemple de taux de qualité initiale
    qmin    = [aql for j in range(nbJobs)]   # Exemple de taux de qualité minimale acceptable
    
    model   = FJSP_Maintenance_Quality_complex_systems_model(DATA,alphas, aql,qinit,qmin,weights=Weights)
  
    
    optsolution1, optCmax1, cputime1, nbrmaint1, avgoq1, qualpenal1 = model.solve()
    
    print("***!!!!!!!!!! SOLVER FINISHED !!!!!")
    
    if optsolution1 == 0:
        print("Optimization failed (Infeasible or Unbounded). Skipping Gantt plotting.")
    else:
        print("data=",DATA)
        print("optsolution1=",optsolution1)
        print("weights=",Weights)
        Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost, NbMaint, AOQ, penality, feasability = completionTime(DATA, optsolution1, Weights)
        print("optCmax1=",optCmax1, " CMAX=",CMAX)
        print("nbrmaint1=",nbrmaint1," NbMaint=",NbMaint)
        print("avgoq1=",avgoq1, " AOQ=",AOQ)
        print("optsolution1=", optsolution1)
        
        k = 1
        save_JSON(DATA,optsolution1,f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json",Weights)
        result = lire_fichier_json(f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json")
        print("result:\n", result)
        plotGantt(result, f"Results/Gantts/MILP4testk{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showgantt=True)
        #plotDEGRAD(result, model.data,  f"Results/EHFs/MILP{n1}inst{n2}_figure_{k}",f"MILP-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showdegrad=True)
        plotEHF(result, DATA, f"Results/EHFs/MILP4{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showdegrad=True)
        
        print("optCmax1=", optCmax1," avgoq1=", avgoq1, " qualpenal1=",qualpenal1, " nbrmaint1=",nbrmaint1,  "CPUTime=",cputime1)              
        
        result2 = build_gantt_result_from_solution(DATA, optsolution1)
        print("result2:\n", result2)
        plotGantt2(result2, "myrun", f"Cmax={optCmax1:.1f}", True)
        
        plt.show()   
def Run_solver(data):
    model = FJSP_Maintenance_Quality_complex_systems__model(data)
    model.data=data
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=model.solve()
    return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1