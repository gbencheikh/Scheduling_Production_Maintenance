from fonctions.CommonFunctions import parse_degradations_file, parse_operations_file
#from fonctions.colors import couleurMachines
from fonctions.data import Data
from fonctions.diagram import *
from fonctions.Save_Read_JSON import *

import numpy as np
import matplotlib.pyplot as plt
import time 

# Solveur 
import gurobipy as gp
from gurobipy import GRB, quicksum as qsum


class FJSP_Maintenance_Quality_complex_systems_model: 
    """
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

    def __init__(self, data, weights=(1.0, 0.0, 0.0)):
        self.data = data
        self.weights = weights

        # -------------------------
        # Sets
        # -------------------------
        self.J = range(self.data.nbJobs)     # set of jobs 
        self.I = {j: range(self.data.nbOperationsParJob[j]) for j in self.J}  # set of operations per job 
        self.K = range(self.data.nbMachines) # set of machines 
        self.L = {k: range(self.data.nbComposants[k]) for k in self.K} # set of components per machine 
        self.O = [(j, i) for j in self.J for i in self.I[j]]   # self of all operations
        self.N = len(self.O)
        self.O_k = {k: [(j, i) for (j, i) in self.O if self.data.dureeOperations[k][j][i] > 0] for k in self.K} # eligible operations per machine
        self.R = {k: range(len(self.O_k[k])) for k in self.K}  # positions per machine: Nk = number of eligible operations r = 0..Nk-1


    def bound_Dmax(self): 
        self.Dmax_kl = {}
        for k in self.K:
            for l in self.L[k]:
                th = float(data.seuils_degradation[k][l])
                self.Dmax_kl[k, l] = max(1.0, 1.2 * th)
        return self.Dmax_kl

    def bound_slot(self):
        ''' 
        LossSlot upper bound per machine/slot: sum_l alpha[k][l] * Dmax_kl[k,l]
        ''' 
        self.LossSlotMax = {}
        for k in self.K:
            self.LossSlotMax[k] = float(sum(self.data.alpha_kl[k][l] * self.Dmax_kl[k, l] for l in self.L[k]))
        return self.LossSlotMax
    
    def bound_roughTime(self):
        '''
        rough time bound
        '''
        totP = 0.0
        for (j, i) in self.O:
            maxp = 0.0
            for k in self.K:
                maxp = max(maxp, float(self.data.dureeOperations[k][j][i]))
            totP += maxp
        maxMaintSum = sum(sum(float(data.dureeMaintenances[k][l]) for l in self.L[k]) for k in self.K)
        self.tmax = max(1.0, totP + self.N * maxMaintSum)
        return self.tmax 

    def set_params(self, model, time_limit, mip_gap, threads): 
        model.Params.TimeLimit = time_limit
        model.Params.MIPGap = mip_gap
        model.Params.Threads = threads
        return model

    def set_variables(self, model): 
        '''
        Déclaration des variables 

        a[j,i,k,r] = 1 if op (j,i) on machine k at position r (only if eligible)
        S[k,r] = slot start times S[k,r]
        T[j,i] = operation start times 
        U[k,r] slot occupancy U[k,r]
        y[k,l,r] maintenance AFTER slot r for component l
        D_before[k,l,r] degradation before slot
        D_after[k,l,r] degradation after slot
        LossSlot[k,r] = sum_l alpha[k][l]*D_after[k,l,r]
        qloss[j,i,k,r] = a[j,i,k,r] * LossSlot[k,r]  (McCormick)
        LossOp[j,i] = sum_{k,r} qloss
        '''
        # a[j,i,k,r] = 1 if op (j,i) on machine k at position r (only if eligible)
        self.a = {}
        for k in self.K:
            for r in self.R[k]:
                for (j, i) in self.O_k[k]:
                    self.a[j, i, k, r] = model.addVar(vtype=GRB.BINARY, name=f"a[{j},{i},{k},{r}]")

        # Auxiliaire pour linéariser a[j,i,k,r] * S[k,r]
        self.z = {}
        for k in self.K:
            for r in self.R[k]:
                for (j, i) in self.O_k[k]:
                    self.z[j, i, k, r] = model.addVar(
                        lb=0.0, ub=self.tmax,
                        vtype=GRB.CONTINUOUS,
                        name=f"z[{j},{i},{k},{r}]"
                    )

        # slot start times S[k,r]
        self.S = {(k, r): model.addVar(lb=0.0, ub=self.tmax, vtype=GRB.CONTINUOUS, name=f"S[{k},{r}]") for k in self.K for r in self.R[k]}

        # operation start times T[j,i]
        self.T = {(j, i): model.addVar(lb=0.0, ub=self.tmax, vtype=GRB.CONTINUOUS, name=f"T[{j},{i}]") for (j, i) in self.O}

        # slot occupancy U[k,r]
        self.U = {(k, r): model.addVar(lb=0.0, ub=1.0, vtype=GRB.BINARY, name=f"U[{k},{r}]") for k in self.K for r in self.R[k]}

        # y[k,l,r] maintenance AFTER slot r for component l
        self.y = {(k, l, r): model.addVar(vtype=GRB.BINARY, name=f"y[{k},{l},{r}]") for k in self.K for l in self.L[k] for r in self.R[k]}

        # degradation before/after slot
        self.D_before = {(k, l, r): model.addVar(lb=0.0, ub=self.Dmax_kl[k, l], vtype=GRB.CONTINUOUS, name=f"Db[{k},{l},{r}]")
                    for k in self.K for l in self.L[k] for r in self.R[k]}
        self.D_after = {(k, l, r): model.addVar(lb=0.0, ub=self.Dmax_kl[k, l], vtype=GRB.CONTINUOUS, name=f"Da[{k},{l},{r}]")
                   for k in self.K for l in self.L[k] for r in self.R[k]}

        # w = y * D_after for reset linearization
        self.w = {(k, l, r): model.addVar(lb=0.0, ub=self.Dmax_kl[k, l], vtype=GRB.CONTINUOUS, name=f"w[{k},{l},{r}]") for k in self.K for l in self.L[k] for r in self.R[k]}

        # Quality: LossSlot[k,r] = sum_l alpha[k][l]*D_after[k,l,r]
        self.LossSlot = {(k, r): model.addVar(lb=0.0, ub=self.LossSlotMax[k], vtype=GRB.CONTINUOUS, name=f"LossSlot[{k},{r}]") for k in self.K for r in self.R[k]}

        # qloss[j,i,k,r] = a[j,i,k,r] * LossSlot[k,r]  (McCormick)
        self.qloss = {}
        for k in self.K:
            for r in self.R[k]:
                for (j, i) in self.O_k[k]:
                    self.qloss[j, i, k, r] = model.addVar(lb=0.0, ub=self.LossSlotMax[k], vtype=GRB.CONTINUOUS, name=f"qloss[{j},{i},{k},{r}]")

        # LossOp[j,i] = sum_{k,r} qloss
        self.LossOp = {(j, i): model.addVar(lb=0.0, ub=max(self.LossSlotMax.values()) if len(self.K) else 0.0,
                                  vtype=GRB.CONTINUOUS, name=f"LossOp[{j},{i}]") for (j, i) in self.O}

        # Quality evolution per op
        self.Qji = {(j, i): model.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"Q[{j},{i}]") for (j, i) in self.O}
        self.ZQ = {(j, i): model.addVar(vtype=GRB.BINARY, name=f"ZQ[{j},{i}]") for (j, i) in self.O}
        self.Qj = {j: model.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"Qj[{j}]") for j in self.J}

        self.penal = {j: model.addVar(lb=0.0, ub=1.0, vtype=GRB.CONTINUOUS, name=f"penal[{j}]") for j in self.J}
        self.TotPena = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="TotPena")

        # Objective auxiliaries
        self.Cmax = model.addVar(lb=0.0, ub=self.tmax, vtype=GRB.CONTINUOUS, name="Cmax")
        self.Mcount = model.addVar(lb=0.0, vtype=GRB.CONTINUOUS, name="Mcount")


    # -------------------------
    # Key constraints
    # -------------------------
    
    def const_Occupancy(self, model):
        # (1) Occupancy definition 
        for k in self.K:
            for r in self.R[k]:
                model.addConstr(self.U[k, r] == gp.quicksum(self.a[j, i, k, r] for (j, i) in self.O_k[k]), 
                                name=f"occ[{k},{r}]")
                model.addConstr(self.U[k, r] <= 1.0, name=f"occ_ub[{k},{r}]")

        return model

    def const_assignement(self, model):
        # (2) Each operation assigned exactly once
        for (j, i) in self.O:
            model.addConstr(gp.quicksum(self.a[j, i, k, r] for k in self.K if (j, i) in self.O_k[k] for r in self.R[k]) == 1,
                name=f"assign[{j},{i}]")
        return model
    
    def const_contig(self,model):
        # (3) No holes: U[k,r+1] <= U[k,r]
        for k in self.K:
            rk = list(self.R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                model.addConstr(self.U[k, r + 1] <= self.U[k, r], name=f"contig[{k},{r}]")
        return model
    
    def const_linkT(self,model):
        # (4) Link T[j,i] = sum a * S
        for k in self.K:
            for r in self.R[k]:
                for (j, i) in self.O_k[k]:
                    z = self.z[j, i, k, r]
                    a = self.a[j, i, k, r]
                    S = self.S[k, r]
                    M = self.tmax
                    # z <= S
                    model.addConstr(z <= S, name=f"zMc1[{j},{i},{k},{r}]")
                    # z <= M * a
                    model.addConstr(z <= M * a, name=f"zMc2[{j},{i},{k},{r}]")
                    # z >= S - M*(1-a)
                    model.addConstr(z >= S - M * (1 - a), name=f"zMc3[{j},{i},{k},{r}]")
                    # z >= 0
                    model.addConstr(z >= 0.0, name=f"zMc4[{j},{i},{k},{r}]")

        # T[j,i] = sum des z
        for (j, i) in self.O:
            model.addConstr(
                self.T[j, i] == gp.quicksum(
                    self.z[j, i, k, r]
                    for k in self.K if (j, i) in self.O_k[k]
                    for r in self.R[k]
                ),
                name=f"linkT[{j},{i}]"
            )
        return model
    
    def const_jobPrec(self,model):
        # (5) Job precedence
        for j in self.J:
            for i in list(self.I[j])[:-1]:
                model.addConstr(self.T[j, i + 1] >= self.T[j, i] + gp.quicksum(self.a[j, i, k, r] * self.data.dureeOperations[k][j][i]
                                                         for k in self.K if (j, i) in self.O_k[k]
                                                         for r in self.R[k]),
                    name=f"jobprec[{j},{i}]"
                )
        return model

    def const_chain(self,model):
        # (6) Machine chain with summed maintenance after slot
        for k in self.K:
            rk = list(self.R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                Pkr = gp.quicksum(self.a[j, i, k, r] * self.data.dureeOperations[k][j][i] for (j, i) in self.O_k[k])
                MaintKr = gp.quicksum(self.y[k, l, r] * self.data.dureeMaintenances[k][l] for l in self.L[k])
                model.addConstr(self.S[k, r + 1] >= self.S[k, r] + Pkr + MaintKr, name=f"chain[{k},{r}]")
        return model

    def const_y_off_emplty(self, model):
        # (7) Maintenance off on empty slots: y <= U
        for k in self.K:
            for r in self.R[k]:
                for l in self.L[k]:
                    model.addConstr(self.y[k, l, r] <= self.U[k, r], name=f"y_off_empty[{k},{l},{r}]")
        return model

    def const_degradation_acc(self, model):
        # (8) Degradation accumulation: D_after = D_before + sum a * (p*delta)
        for k in self.K:
            for r in self.R[k]:
                for l in self.L[k]:
                    Inc = gp.quicksum(
                        self.a[j, i, k, r] * (self.data.dureeOperations[k][j][i] * self.data.degradations[k][l][j][i])
                        for (j, i) in self.O_k[k]
                    )
                    model.addConstr(self.D_after[k, l, r] == self.D_before[k, l, r] + Inc, name=f"Dacc[{k},{l},{r}]")
        return model

    def const_Dinit(self, model):
        # (9) Initialize D_before at first slot = 0
        for k in self.K:
            if len(self.O_k[k]) == 0:
                continue
            for l in self.L[k]:
                model.addConstr(self.D_before[k, l, 0] == 0.0, name=f"Dinit[{k},{l}]")
        return model
    
    def const_w3(self, model): 
        # (10) Reset propagation: D_before[r+1] = D_after[r] - w, w = y * D_after
        for k in self.K:
            rk = list(self.R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                for l in self.L[k]:
                    model.addConstr(self.D_before[k, l, r + 1] == self.D_after[k, l, r] - self.w[k, l, r],
                                name=f"Dprop[{k},{l},{r}]")

                    Dmax = self.Dmax_kl[k, l]
                    model.addConstr(self.w[k, l, r] <= Dmax * self.y[k, l, r], name=f"w1[{k},{l},{r}]")
                    model.addConstr(self.w[k, l, r] <= self.D_after[k, l, r], name=f"w2[{k},{l},{r}]")
                    model.addConstr(self.w[k, l, r] >= self.D_after[k, l, r] - Dmax * (1 - self.y[k, l, r]),
                                name=f"w3[{k},{l},{r}]")
        return model        
                
    def const_trigger(self, model): 
        # (11) Trigger: if D_after > theta then y=1 (>=theta in MILP)
        for k in self.K:
            for r in self.R[k]:
                for l in self.L[k]:
                    th = float(self.data.seuils_degradation[k][l])
                    Mtrig = max(1e-6, self.Dmax_kl[k, l] - th)
                    model.addConstr(self.D_after[k, l, r] - th <= Mtrig * self.y[k, l, r], name=f"trigger[{k},{l},{r}]")
        return model

    def const_lossSlotEmpty(self, model):
        # (12) LossSlot[k,r] = sum_l alpha[k][l] * D_after[k,l,r]
        for k in self.K:
            for r in self.R[k]:
                model.addConstr(
                    self.LossSlot[k, r] == gp.quicksum(self.data.alpha_kl[k][l] * self.D_after[k, l, r] for l in self.L[k]),
                    name=f"lossSlotDef[{k},{r}]"
                )
                # Optional tightening: LossSlot <= LossSlotMax * U
                model.addConstr(self.LossSlot[k, r] <= self.LossSlotMax[k] * self.U[k, r], name=f"lossSlotEmpty[{k},{r}]")
        return model

    def const_ql(self, model):
        # (13) qloss[j,i,k,r] = a * LossSlot (McCormick, a is binary)
        for k in self.K:
            Mloss = self.LossSlotMax[k]
            for r in self.R[k]:
                for (j, i) in self.O_k[k]:
                    model.addConstr(self.qloss[j, i, k, r] <= self.LossSlot[k, r], name=f"ql1[{j},{i},{k},{r}]")
                    model.addConstr(self.qloss[j, i, k, r] <= Mloss * self.a[j, i, k, r], name=f"ql2[{j},{i},{k},{r}]")
                    model.addConstr(self.qloss[j, i, k, r] >= self.LossSlot[k, r] - Mloss * (1 - self.a[j, i, k, r]),
                                name=f"ql3[{j},{i},{k},{r}]")
                    model.addConstr(self.qloss[j, i, k, r] >= 0.0, name=f"ql4[{j},{i},{k},{r}]")
        return model

    def const_lossOp(self, model):
        # (14) LossOp[j,i] = sum_{k,r} qloss
        for (j, i) in self.O:
            model.addConstr(
                self.LossOp[j, i] == gp.quicksum(self.qloss[j, i, k, r] for k in self.K if (j, i) in self.O_k[k] for r in self.R[k]),
                name=f"LossOp[{j},{i}]")
        return model

    def const_Qj(self, model):
        # (15) Quality recurrence: Qji = max(0, prev - LossOp)
        # max(0, expr) linearization using ZQ (same pattern as your previous model)
        M_Q = 1.0  # quality is within [0,1], so a tight M is 1

        for j in self.J:
            # i = 0: Q[j,0] = max(0, Qinitj[j] - LossOp[j,0])
            expr0 = float(self.data.Qinitj[j]) - self.LossOp[j, 0]
            model.addConstr(-expr0 <= M_Q * (1 - self.ZQ[j, 0]), name=f"Q0_a[{j}]")  # expr0 >= 0 when ZQ=1
            model.addConstr(expr0 <= M_Q * self.ZQ[j, 0], name=f"Q0_b[{j}]")
            model.addConstr(self.Qji[j, 0] <= expr0 + M_Q * (1 - self.ZQ[j, 0]), name=f"Q0_c[{j}]")
            model.addConstr(self.Qji[j, 0] >= expr0, name=f"Q0_d[{j}]")
            model.addConstr(self.Qji[j, 0] <= M_Q * self.ZQ[j, 0], name=f"Q0_e[{j}]")

            for i in list(self.I[j])[1:]:
                expri = self.Qji[j, i - 1] - self.LossOp[j, i]
                model.addConstr(-expri <= M_Q * (1 - self.ZQ[j, i]), name=f"Qi_a[{j},{i}]")
                model.addConstr(expri <= M_Q * self.ZQ[j, i], name=f"Qi_b[{j},{i}]")
                model.addConstr(self.Qji[j, i] <= expri + M_Q * (1 - self.ZQ[j, i]), name=f"Qi_c[{j},{i}]")
                model.addConstr(self.Qji[j, i] >= expri, name=f"Qi_d[{j},{i}]")
                model.addConstr(self.Qji[j, i] <= M_Q * self.ZQ[j, i], name=f"Qi_e[{j},{i}]")

            last_i = self.data.nbOperationsParJob[j] - 1
            model.addConstr(self.Qj[j] == self.Qji[j, last_i], name=f"QjLink[{j}]")
        return model

    def const_TotPena(self, model):
        # (16) Penalties and TotPena
        for j in self.J:
            model.addConstr(self.penal[j] >= float(self.data.Qjmin[j]) - self.Qj[j], name=f"pen_a[{j}]")
            model.addConstr(self.penal[j] >= 0.0, name=f"pen_b[{j}]")
        model.addConstr(self.TotPena == gp.quicksum(self.penal[j] for j in self.J), name="TotPena")
        return model
    
    def const_Cmax(self, model):
        # (17) Cmax 
        for j in self.J:
            last_i = data.nbOperationsParJob[j] - 1
            proc_last = gp.quicksum(self.a[j, last_i, k, r] * self.data.dureeOperations[k][j][last_i]
                                    for k in self.K if (j, last_i) in self.O_k[k]
                                    for r in self.R[k])
            model.addConstr(self.Cmax >= self.T[j, last_i] + proc_last, name=f"Cmax[{j}]")
        return model

    def const_Mcount(self, model):
        # (18) Mcount 
        model.addConstr(self.Mcount == gp.quicksum(self.y[k, l, r] for k in self.K for r in self.R[k] for l in self.L[k]), name="Mcount")
        return model

    def obj(self, model): 
        lam1, lam2, lam3 = self.weights
        model.setObjective(lam1 * self.Cmax + lam2 * self.Mcount + lam3 * self.TotPena, GRB.MINIMIZE)
        return model

    def create_model(self, verbose= True): 
        model = gp.Model("FJSP_PositionBased_Prod_Maint_Quality_Dafter_GBH")
        if not verbose:
            model.Params.OutputFlag = 0

        self.bound_Dmax()
        self.bound_slot()
        self.bound_roughTime()
        
        self.set_variables(model)
        model.update()
        
        model = self.const_Occupancy(model)
        model = self.const_assignement(model)
        model = self.const_contig(model)
        model = self.const_linkT(model)
        model = self.const_jobPrec(model)
        model = self.const_chain(model)
        model = self.const_y_off_emplty(model)
        model = self.const_degradation_acc(model)
        model = self.const_Dinit(model)
        model = self.const_w3(model)
        model = self.const_trigger(model)
        model = self.const_lossSlotEmpty(model)
        model = self.const_ql(model)
        model = self.const_lossOp(model)
        model = self.const_Qj(model)
        model = self.const_TotPena(model)
        model = self.const_Cmax(model)
        model = self.const_Mcount(model)

        model = self.obj(model)
        
        return model

    def solve(self, time_limit=3600, mip_gap=0.01, threads=0, verbose=True, fileName="Model_GBH"):
        model = self.create_model()
        self.set_params(model, time_limit, mip_gap, threads)

        t0 = time.perf_counter()
        model.optimize()
        CPU = time.perf_counter() - t0
        
        print("***!!!!!!!!!! SOLVER FINISHED !!!!!")

        if model.Status in [GRB.INFEASIBLE, GRB.INF_OR_UNBD]:
            print("INFEASIBLE")
            return 
        
        Cmax_opt = float(self.Cmax.X)
        nbrmaint_opt = float(self.Mcount.X)
        qual_opt = float(sum(self.penal[j].X for j in self.J))
        avgoq_opt = float(sum((1.0 - self.Qj[j].X) for j in self.J) / self.data.nbJobs)

        if verbose:
            print(f"Z*={model.objVal:.6f}, Cmax={Cmax_opt:.3f}, Maint={nbrmaint_opt:.0f}, TotPena={qual_opt:.6f}, AvgOQ={avgoq_opt:.6f}")

        # Determine for each op (j,i): assigned (k,r), and T
        assign = {}  # (j,i) -> (k,r)
        for k in self.K:
            for r in self.R[k]:
                for (j, i) in self.O_k[k]:
                    if self.a[j, i, k, r].X > 0.5:
                        assign[(j, i)] = (k, r)

        print("assign", assign)

        # Global order by start time then machine then job/op
        op_records = [(self.T[j, i].X, assign[(j, i)][0], j, i, assign[(j, i)][1]) for (j, i) in self.O]
        op_records.sort(key=lambda x: (x[0], x[1], x[2], x[3]))

        seq_jobs = [j for (_, _, j, _, _) in op_records]
        seq_machs = [k for (_, k, _, _, _) in op_records]

        # y_set: (j,i,l) if component l maintained after op (j,i)
        # Here, op (j,i) sits in slot (k,r) so we read y[k,l,r]
        y_set = set()
        yset2=[[[False  for _ in range(data.nbOperationsParJob[j])] for j in range(data.nbJobs)] for _ in range(max(self.data.nbComposants))]
        for (j, i) in self.O:
            k, r = assign[(j, i)]
            for l in self.L[k]:
                if self.y[k, l, r].X > 0.5:
                    y_set.add((j, i, l))
                    yset2[l][j][i] =True

        # t_matrix
        t_matrix = [[float(self.T[j, i].X) for i in self.I[j]] for j in range(self.data.nbJobs)]

        rank = [1] * len(seq_jobs)  # placeholder (kept for compatibility)

        #optsolution = [seq_jobs, seq_machs, y_set, t_matrix, rank]
        optsolution = [seq_jobs, seq_machs, yset2, t_matrix, rank]
        
        for j in self.J:
            for i in self.I[j]:
                ind=i+sum(self.data.nbOperationsParJob[j1] for j1 in range(j))
                mach=int(optsolution[1][ind])
                machji=self.data.dureeOperations[mach][j][i] 
                print(f"debut_{j+1}{i+1}={optsolution[3][j][i]}-- machine = {mach+1} -- duree ={machji}") 
        if verbose == True: 
            for j in self.J:
                for i in self.I[j]:
                    ind=i+sum(self.data.nbOperationsParJob[j1] for j1 in range(j))
                    mach=int(optsolution[1][ind])
                    machji=self.data.dureeOperations[mach][j][i] 
                    print(f"debut_{j+1}{i+1}={optsolution[3][j][i]}-- machine = {mach+1} -- duree ={machji}") 

            print("\n=== DEBUG TRIGGER ===")
            for k in self.K:
                for r in self.R[k]:
                    for l in self.L[k]:
                        th = float(self.data.seuils_degradation[k][l])
                        da = self.D_after[k, l, r].X
                        yval = self.y[k, l, r].X
                        uval = self.U[k, r].X
                        if yval > 0.01 or da > 0.01:  # filtrer les lignes vides
                            print(f"  k={k} r={r} l={l} | U={uval:.2f} | D_after={da:.4f} | theta={th:.4f} | y={yval:.2f} | OK={da >= th * yval - 1e-6}")

            print("\n=== DEBUG PROPAGATION ===")
            for k in self.K:
                for l in self.L[k]:
                    th = float(self.data.seuils_degradation[k][l])
                    print(f"\n  Machine k={k}, composant l={l}, theta={th}")
                    for r in self.R[k]:
                        db = self.D_before[k, l, r].X
                        da = self.D_after[k, l, r].X
                        yv = self.y[k, l, r].X
                        wv = self.w[k, l, r].X
                        uv = self.U[k, r].X
                        print(f"    r={r} | U={uv:.2f} | D_before={db:.4f} | D_after={da:.4f} | y={yv:.2f} | w={wv:.4f} | reset_ok={abs(wv - yv*da) < 1e-3}")
        
        save_JSON(self.data,optsolution,fileName,self.weights)
        return optsolution, Cmax_opt, CPU, nbrmaint_opt, avgoq_opt, qual_opt

if __name__ == "__main__": 
    n1=1
    n2=1

    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
    data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    
    std_betakl=0.0      # standard deviation of degradation rate of componenets
    aql=0.25            # acceptable quality level triggering quality penality ()
    qinit=1.0
    lambdakl=0.7        # degradation threshold triggering PdM 
    dureemaint=1        # maintenance duration
    
    alphakl=0.0         # quality degradation rate
    betakl=0.1          # average degradation rate of componenets 

    lambdakl=0.7        # degradation threshold triggering PdM
    dureemaint=1        # maintenance duration

    data.set_fixed_alphakl(alphakl)
    data.set_fixed_degradation(betakl)
    data.set_fixed_Qjinit(qinit)
    data.set_fixed_Qjmin(aql)
    data.set_fixed_degradation_threshold(lambdakl)
    data.set_maintenance_duration(dureemaint)
    print("-----------------------------------")
    print(repr(data))

    Weights = [1.0,0.0,1.0]
    results_fileName = f"Results/JSONS/MILP_GBH_{n1}inst_{n2}.json"
    

    model = FJSP_Maintenance_Quality_complex_systems_model(data,weights=Weights)
    optsolution1, optCmax1, cputime1, nbrmaint1, avgoq1, qualpenal1 = model.solve(verbose=True, fileName= results_fileName)

    result = lire_fichier_json(results_fileName)
    afficher_fichier_json(result)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 6))
    plotGantt(result, f"Results/Gantts/MILP_GBH{n1}inst{n2}_Gantt",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showgantt=True, ax=ax1)
    plotEHF(result, data, f"Results/EHFs/MILP_GBH{n1}inst{n2}_EHF",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{aql}", showdegrad=True, ax=ax2)
    
    plt.tight_layout()
    plt.show()
    