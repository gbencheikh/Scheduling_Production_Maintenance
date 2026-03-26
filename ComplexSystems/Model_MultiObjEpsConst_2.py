# -*- coding: utf-8 -*-
"""
FJSP_EpsilonConstraint.py
=========================
Multi-objective optimization via the epsilon-constraint method.

Strategy
--------
  Primary objective  : minimize Cmax
  Constrained obj 1  : Mcount  <= eps1
  Constrained obj 2  : TotPena <= eps2

The class inherits from FJSP_Maintenance_Quality_complex_systems_model so it
reuses all variable/constraint building logic and only overrides the
objective + adds the two epsilon constraints.

Pareto-front generation
-----------------------
  generate_pareto_front(n_eps=10, ...)
    - Solves the single-objective problems (Mcount alone, TotPena alone) to
      anchor the epsilon ranges automatically.
    - Sweeps an n_eps × n_eps uniform grid over [eps1_min, eps1_max] ×
      [eps2_min, eps2_max].
    - Filters dominated solutions and returns the Pareto front.

Usage
-----
  from FJSP_EpsilonConstraint import FJSP_EpsilonConstraint

  solver = FJSP_EpsilonConstraint(DATA, alphas, aql, qinit, qmin)
  pareto = solver.generate_pareto_front(n_eps=8, time_limit=120, verbose=False)

  # pareto is a list of dicts:
  # { 'eps1': float, 'eps2': float,
  #   'Cmax': float, 'Mcount': float, 'TotPena': float,
  #   'solution': optsolution, 'cputime': float }

  solver.plot_pareto(pareto)               # 2-D and 3-D scatter plots (knee-point highlighted)
  knee = solver.find_knee_point(pareto)    # best compromise solution
  solver.export_gantt(knee, "Results/")    # Gantt chart for knee-point solution
  solver.save_pareto_csv(pareto, "pareto.csv")
"""

import time
import csv
import itertools
import numpy as np
import matplotlib.pyplot as plt
import gurobipy as gp
from gurobipy import GRB

# ---------------------------------------------------------------------------
# Local import — adjust path if needed
# ---------------------------------------------------------------------------
from Model11 import FJSP_Maintenance_Quality_complex_systems_model   # <-- your file


# ===========================================================================
class FJSP_EpsilonConstraint(FJSP_Maintenance_Quality_complex_systems_model):
    """
    Epsilon-constraint solver for the FJSP with maintenance and quality.

    Inherits all model-building logic from the base class.
    New public methods:
      solve_epsilon(eps1, eps2, ...)  -> single solve with epsilon constraints
      generate_pareto_front(n_eps, ...)  -> full Pareto sweep
      plot_pareto(pareto)
      save_pareto_csv(pareto, path)
    """

    # -----------------------------------------------------------------------
    # Single epsilon-constrained solve
    # -----------------------------------------------------------------------
    def solve_epsilon(self, eps1: float, eps2: float,
                      time_limit: float = 3600,
                      mip_gap: float = 0.01,
                      threads: int = 0,
                      verbose: bool = False):
        """
        Minimize Cmax subject to:
            Mcount  <= eps1
            TotPena <= eps2

        Parameters
        ----------
        eps1 : float  upper bound on number of maintenances
        eps2 : float  upper bound on total quality penalty
        time_limit, mip_gap, threads, verbose : Gurobi params

        Returns
        -------
        dict with keys:
            'feasible', 'Cmax', 'Mcount', 'TotPena',
            'solution', 'cputime', 'eps1', 'eps2'
        """
        data = self.data
        J = range(data.nbJobs)
        I = {j: range(data.nbOperationsParJob[j]) for j in J}
        K = range(data.nbMachines)
        L = {k: range(data.nbComposants[k]) for k in K}

        O = [(j, i) for j in J for i in I[j]]
        N = len(O)
        O_k = {k: [(j, i) for (j, i) in O if data.dureeOperations[k][j][i] > 0] for k in K}
        R = {k: range(len(O_k[k])) for k in K}

        # ---------- Bounds (same as base class) ----------
        Dmax_kl = {}
        for k in K:
            for l in L[k]:
                th = float(data.seuils_degradation[k][l])
                Dmax_kl[k, l] = max(1.0, 1.2 * th)

        LossSlotMax = {}
        for k in K:
            LossSlotMax[k] = float(sum(self.alpha_kl[k][l] * Dmax_kl[k, l] for l in L[k]))

        totP = sum(max(float(data.dureeOperations[k][j][i]) for k in K)
                   for (j, i) in O)
        maxMaintSum = sum(sum(float(data.dureeMaintenances[k][l]) for l in L[k]) for k in K)
        tmax = max(1.0, totP + N * maxMaintSum)

        # ---------- Gurobi model ----------
        m = gp.Model("FJSP_EpsConstraint")
        m.Params.OutputFlag = int(verbose)
        m.Params.TimeLimit = time_limit
        m.Params.MIPGap = mip_gap
        m.Params.Threads = threads

        # ---- Variables (identical to base class) ----
        a = {(j, i, k, r): m.addVar(vtype=GRB.BINARY)
             for k in K for r in R[k] for (j, i) in O_k[k]}

        S = {(k, r): m.addVar(lb=0.0, ub=tmax) for k in K for r in R[k]}
        T = {(j, i): m.addVar(lb=0.0, ub=tmax) for (j, i) in O}
        U = {(k, r): m.addVar(lb=0.0, ub=1.0) for k in K for r in R[k]}

        y = {(k, l, r): m.addVar(vtype=GRB.BINARY)
             for k in K for l in L[k] for r in R[k]}

        D_before = {(k, l, r): m.addVar(lb=0.0, ub=Dmax_kl[k, l])
                    for k in K for l in L[k] for r in R[k]}
        D_after  = {(k, l, r): m.addVar(lb=0.0, ub=Dmax_kl[k, l])
                    for k in K for l in L[k] for r in R[k]}
        w        = {(k, l, r): m.addVar(lb=0.0, ub=Dmax_kl[k, l])
                    for k in K for l in L[k] for r in R[k]}

        LossSlot = {(k, r): m.addVar(lb=0.0, ub=LossSlotMax[k])
                    for k in K for r in R[k]}
        qloss = {(j, i, k, r): m.addVar(lb=0.0, ub=LossSlotMax[k])
                 for k in K for r in R[k] for (j, i) in O_k[k]}
        LossOp = {(j, i): m.addVar(lb=0.0) for (j, i) in O}

        Qji = {(j, i): m.addVar(lb=0.0, ub=1.0) for (j, i) in O}
        ZQ  = {(j, i): m.addVar(vtype=GRB.BINARY) for (j, i) in O}
        Qj  = {j: m.addVar(lb=0.0, ub=1.0) for j in J}
        penal   = {j: m.addVar(lb=0.0, ub=1.0) for j in J}
        TotPena = m.addVar(lb=0.0)

        Cmax   = m.addVar(lb=0.0, ub=tmax)
        Mcount = m.addVar(lb=0.0)

        m.update()

        # ---- Constraints (copy from base class, variable references updated) ----

        # Occupancy
        for k in K:
            for r in R[k]:
                m.addConstr(U[k, r] == gp.quicksum(a[j, i, k, r] for (j, i) in O_k[k]))
                m.addConstr(U[k, r] <= 1.0)

        # Each op assigned once
        for (j, i) in O:
            m.addConstr(gp.quicksum(a[j, i, k, r]
                                    for k in K if (j, i) in O_k[k]
                                    for r in R[k]) == 1)

        # No holes
        for k in K:
            rk = list(R[k])
            for idx in range(len(rk) - 1):
                m.addConstr(U[k, rk[idx] + 1] <= U[k, rk[idx]])

        # Link T = sum a*S
        for (j, i) in O:
            m.addConstr(T[j, i] == gp.quicksum(a[j, i, k, r] * S[k, r]
                                               for k in K if (j, i) in O_k[k]
                                               for r in R[k]))

        # Job precedence
        for j in J:
            for i in list(I[j])[:-1]:
                m.addConstr(T[j, i + 1] >= T[j, i] +
                            gp.quicksum(a[j, i, k, r] * data.dureeOperations[k][j][i]
                                        for k in K if (j, i) in O_k[k] for r in R[k]))

        # Machine chain
        for k in K:
            rk = list(R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                Pkr   = gp.quicksum(a[j, i, k, r] * data.dureeOperations[k][j][i] for (j, i) in O_k[k])
                Mkr   = gp.quicksum(y[k, l, r] * data.dureeMaintenances[k][l] for l in L[k])
                m.addConstr(S[k, r + 1] >= S[k, r] + Pkr + Mkr)

        # Maintenance off on empty slots
        for k in K:
            for r in R[k]:
                for l in L[k]:
                    m.addConstr(y[k, l, r] <= U[k, r])

        # Degradation accumulation
        for k in K:
            for r in R[k]:
                for l in L[k]:
                    Inc = gp.quicksum(a[j, i, k, r] *
                                      (data.dureeOperations[k][j][i] * data.degradations[k][l][j][i])
                                      for (j, i) in O_k[k])
                    m.addConstr(D_after[k, l, r] == D_before[k, l, r] + Inc)

        # Init D_before
        for k in K:
            if not O_k[k]:
                continue
            for l in L[k]:
                m.addConstr(D_before[k, l, 0] == 0.0)

        # Reset propagation (McCormick for w = y * D_after)
        for k in K:
            rk = list(R[k])
            for idx in range(len(rk) - 1):
                r = rk[idx]
                for l in L[k]:
                    Dmax = Dmax_kl[k, l]
                    m.addConstr(D_before[k, l, r + 1] == D_after[k, l, r] - w[k, l, r])
                    m.addConstr(w[k, l, r] <= Dmax * y[k, l, r])
                    m.addConstr(w[k, l, r] <= D_after[k, l, r])
                    m.addConstr(w[k, l, r] >= D_after[k, l, r] - Dmax * (1 - y[k, l, r]))

        # Trigger maintenance if D_after > theta
        for k in K:
            for r in R[k]:
                for l in L[k]:
                    th    = float(data.seuils_degradation[k][l])
                    Mtrig = max(1e-6, Dmax_kl[k, l] - th)
                    m.addConstr(D_after[k, l, r] - th <= Mtrig * y[k, l, r])

        # Quality: LossSlot, qloss, LossOp
        for k in K:
            for r in R[k]:
                m.addConstr(LossSlot[k, r] == gp.quicksum(self.alpha_kl[k][l] * D_after[k, l, r]
                                                          for l in L[k]))
                m.addConstr(LossSlot[k, r] <= LossSlotMax[k] * U[k, r])

        for k in K:
            Mloss = LossSlotMax[k]
            for r in R[k]:
                for (j, i) in O_k[k]:
                    m.addConstr(qloss[j, i, k, r] <= LossSlot[k, r])
                    m.addConstr(qloss[j, i, k, r] <= Mloss * a[j, i, k, r])
                    m.addConstr(qloss[j, i, k, r] >= LossSlot[k, r] - Mloss * (1 - a[j, i, k, r]))
                    m.addConstr(qloss[j, i, k, r] >= 0.0)

        for (j, i) in O:
            m.addConstr(LossOp[j, i] == gp.quicksum(qloss[j, i, k, r]
                                                     for k in K if (j, i) in O_k[k]
                                                     for r in R[k]))

        # Quality recurrence
        M_Q = 1.0
        for j in J:
            expr0 = float(self.Qinitj[j]) - LossOp[j, 0]
            m.addConstr(-expr0 <= M_Q * (1 - ZQ[j, 0]))
            m.addConstr(expr0  <= M_Q * ZQ[j, 0])
            m.addConstr(Qji[j, 0] <= expr0 + M_Q * (1 - ZQ[j, 0]))
            m.addConstr(Qji[j, 0] >= expr0)
            m.addConstr(Qji[j, 0] <= M_Q * ZQ[j, 0])

            for i in list(I[j])[1:]:
                expri = Qji[j, i - 1] - LossOp[j, i]
                m.addConstr(-expri <= M_Q * (1 - ZQ[j, i]))
                m.addConstr(expri  <= M_Q * ZQ[j, i])
                m.addConstr(Qji[j, i] <= expri + M_Q * (1 - ZQ[j, i]))
                m.addConstr(Qji[j, i] >= expri)
                m.addConstr(Qji[j, i] <= M_Q * ZQ[j, i])

            last_i = data.nbOperationsParJob[j] - 1
            m.addConstr(Qj[j] == Qji[j, last_i])

        for j in J:
            m.addConstr(penal[j] >= float(self.Qjmin[j]) - Qj[j])
            m.addConstr(penal[j] >= 0.0)
        m.addConstr(TotPena == gp.quicksum(penal[j] for j in J))

        # Cmax and Mcount
        for j in J:
            last_i = data.nbOperationsParJob[j] - 1
            proc   = gp.quicksum(a[j, last_i, k, r] * data.dureeOperations[k][j][last_i]
                                 for k in K if (j, last_i) in O_k[k] for r in R[k])
            m.addConstr(Cmax >= T[j, last_i] + proc)

        m.addConstr(Mcount == gp.quicksum(y[k, l, r]
                                          for k in K for r in R[k] for l in L[k]))

        # ---------------------------------------------------------------
        # EPSILON CONSTRAINTS  <-- key addition vs base class
        # ---------------------------------------------------------------
        m.addConstr(Mcount  <= eps1, name="eps1_Mcount")
        m.addConstr(TotPena <= eps2, name="eps2_TotPena")

        # ---------------------------------------------------------------
        # Objective: minimize Cmax only
        # ---------------------------------------------------------------
        m.setObjective(Cmax, GRB.MINIMIZE)

        # Solve
        t0 = time.perf_counter()
        m.optimize()
        cpu = time.perf_counter() - t0

        # ---------- Infeasible ----------
        if m.Status in [GRB.INFEASIBLE, GRB.INF_OR_UNBD, GRB.CUTOFF]:
            return {'feasible': False, 'eps1': eps1, 'eps2': eps2, 'cputime': cpu}

        if m.SolCount == 0:
            return {'feasible': False, 'eps1': eps1, 'eps2': eps2, 'cputime': cpu}

        # ---------- Extract solution ----------
        assign = {}
        for k in K:
            for r in R[k]:
                for (j, i) in O_k[k]:
                    if a[j, i, k, r].X > 0.5:
                        assign[(j, i)] = (k, r)

        op_records = [(T[j, i].X, assign[(j, i)][0], j, i) for (j, i) in O]
        op_records.sort()
        seq_jobs  = [j for (_, _, j, i) in op_records]
        seq_machs = [k for (_, k, j, i) in op_records]

        y_set = set()
        yset2 = [[[False for i in range(data.nbOperationsParJob[j])]
                  for j in range(data.nbJobs)]
                 for _ in range(max(data.nbComposants))]
        for (j, i) in O:
            k, r = assign[(j, i)]
            for l in L[k]:
                if y[k, l, r].X > 0.5:
                    y_set.add((j, i, l))
                    yset2[l][j][i] = True

        t_matrix = [[float(T[j, i].X) for i in range(data.nbOperationsParJob[j])]
                    for j in range(data.nbJobs)]
        optsol   = [seq_jobs, seq_machs, yset2, t_matrix, [1] * len(seq_jobs)]

        return {
            'feasible':  True,
            'eps1':      eps1,
            'eps2':      eps2,
            'Cmax':      float(Cmax.X),
            'Mcount':    float(Mcount.X),
            'TotPena':   float(TotPena.X),
            'avgoq':     float(sum((1.0 - Qj[j].X) for j in J) / data.nbJobs),
            'solution':  optsol,
            'cputime':   cpu,
        }

    # -----------------------------------------------------------------------
    # Anchor solves: find natural bounds for eps1 and eps2
    # -----------------------------------------------------------------------
    def _compute_bounds(self, time_limit=600, verbose=False):
        """
        Solve two auxiliary problems to get anchor points:
          - Minimize Mcount  alone -> Mcount_min, Mcount when Cmax is free
          - Minimize TotPena alone -> TotPena_min
          - Maximize Mcount  alone -> Mcount_max (worst case, needed for upper bound)
          - Maximize TotPena alone -> TotPena_max
        We then sweep eps1 in [Mcount_min, Mcount_max]
                        eps2 in [TotPena_min, TotPena_max]
        """
        print("[Epsilon-Constraint] Computing anchor bounds...")

        bounds = {}
        for obj_name, weight_vec in [("Mcount",  (0.0, 1.0, 0.0)),
                                      ("TotPena", (0.0, 0.0, 1.0))]:
            self.weights = weight_vec
            sol, cmax, cpu, nmaint, aoq, qpen = self.solve(
                time_limit=time_limit, verbose=verbose)
            if sol == 0:
                raise RuntimeError(f"Anchor solve for {obj_name} failed (infeasible).")
            bounds[f"{obj_name}_min"] = nmaint if obj_name == "Mcount" else qpen
            print(f"  {obj_name}_min = {bounds[f'{obj_name}_min']:.4f}  (cpu={cpu:.1f}s)")

        # Upper bounds: optimize the other direction
        # Use the base class with weights (1,1,1) as a rough upper bound solver
        self.weights = (1.0, 1.0, 1.0)
        sol, cmax, cpu, nmaint, aoq, qpen = self.solve(
            time_limit=time_limit, verbose=verbose)
        if sol != 0:
            bounds["Mcount_max"]  = max(nmaint * 2, bounds["Mcount_min"] + 1)
            bounds["TotPena_max"] = max(qpen  * 2, bounds["TotPena_min"] + 0.1)
        else:
            # Fallback safe values
            data = self.data
            bounds["Mcount_max"]  = sum(data.nbComposants[k] * len(range(len(
                [(j, i) for j in range(data.nbJobs)
                 for i in range(data.nbOperationsParJob[j])
                 if data.dureeOperations[k][j][i] > 0]))) for k in range(data.nbMachines))
            bounds["TotPena_max"] = float(data.nbJobs)

        print(f"  Mcount  range : [{bounds['Mcount_min']:.2f}, {bounds['Mcount_max']:.2f}]")
        print(f"  TotPena range : [{bounds['TotPena_min']:.4f}, {bounds['TotPena_max']:.4f}]")
        return bounds

    # -----------------------------------------------------------------------
    # Main entry point: generate the full Pareto front
    # -----------------------------------------------------------------------
    def generate_pareto_front(self,
                              n_eps: int = 10,
                              eps1_range: tuple = None,
                              eps2_range: tuple = None,
                              time_limit: float = 300,
                              mip_gap: float = 0.02,
                              threads: int = 0,
                              verbose: bool = False,
                              anchor_time_limit: float = 600):
        """
        Sweep an n_eps × n_eps grid of (eps1, eps2) values.

        Parameters
        ----------
        n_eps           : number of epsilon levels per objective (grid = n_eps²)
        eps1_range      : (min, max) for Mcount  ; auto-computed if None
        eps2_range      : (min, max) for TotPena ; auto-computed if None
        time_limit      : Gurobi time limit per solve (seconds)
        mip_gap         : Gurobi MIP gap per solve
        threads         : 0 = auto
        verbose         : Gurobi console output
        anchor_time_limit : time limit for anchor bound computation

        Returns
        -------
        List of feasible result dicts, filtered to non-dominated solutions.
        """
        # --- Compute or use provided ranges ---
        if eps1_range is None or eps2_range is None:
            bounds = self._compute_bounds(time_limit=anchor_time_limit, verbose=verbose)
            eps1_range = eps1_range or (bounds["Mcount_min"],  bounds["Mcount_max"])
            eps2_range = eps2_range or (bounds["TotPena_min"], bounds["TotPena_max"])

        eps1_values = np.linspace(eps1_range[0], eps1_range[1], n_eps)
        eps2_values = np.linspace(eps2_range[0], eps2_range[1], n_eps)

        total = n_eps * n_eps
        print(f"\n[Epsilon-Constraint] Starting grid sweep: {n_eps}×{n_eps} = {total} solves")
        print(f"  eps1 (Mcount)  in [{eps1_range[0]:.2f}, {eps1_range[1]:.2f}]")
        print(f"  eps2 (TotPena) in [{eps2_range[0]:.4f}, {eps2_range[1]:.4f}]\n")

        all_results = []
        feasible_count = 0

        for idx, (e1, e2) in enumerate(itertools.product(eps1_values, eps2_values), 1):
            t0 = time.perf_counter()
            res = self.solve_epsilon(e1, e2, time_limit=time_limit,
                                     mip_gap=mip_gap, threads=threads, verbose=verbose)
            elapsed = time.perf_counter() - t0

            status = "OK " if res['feasible'] else "INF"
            if res['feasible']:
                feasible_count += 1
                print(f"  [{idx:3d}/{total}] eps1={e1:.2f} eps2={e2:.4f} -> "
                      f"Cmax={res['Cmax']:.2f} Maint={res['Mcount']:.0f} "
                      f"Pena={res['TotPena']:.4f}  [{elapsed:.1f}s] {status}")
                all_results.append(res)
            else:
                print(f"  [{idx:3d}/{total}] eps1={e1:.2f} eps2={e2:.4f} -> "
                      f"INFEASIBLE  [{elapsed:.1f}s]")

        print(f"\n[Epsilon-Constraint] Done. {feasible_count}/{total} feasible solves.")

        # --- Filter Pareto-non-dominated solutions ---
        pareto = self._filter_pareto(all_results)
        print(f"[Epsilon-Constraint] Pareto front: {len(pareto)} non-dominated solutions.\n")
        return pareto

    # -----------------------------------------------------------------------
    # Pareto filter
    # -----------------------------------------------------------------------
    @staticmethod
    def _filter_pareto(results):
        """Remove dominated solutions (minimize all three objectives)."""
        if not results:
            return []
        pts = [(r['Cmax'], r['Mcount'], r['TotPena'], r) for r in results]
        non_dom = []
        for i, (c1, m1, p1, r1) in enumerate(pts):
            dominated = False
            for j, (c2, m2, p2, _) in enumerate(pts):
                if i == j:
                    continue
                if c2 <= c1 and m2 <= m1 and p2 <= p1 and (c2 < c1 or m2 < m1 or p2 < p1):
                    dominated = True
                    break
            if not dominated:
                non_dom.append(r1)
        return non_dom

    # -----------------------------------------------------------------------
    # Knee-point detector
    # -----------------------------------------------------------------------
    def find_knee_point(self, pareto, weights=(1.0, 1.0, 1.0)):
        """
        Identify the knee point on the Pareto front — the solution offering
        the best overall compromise across all three objectives.

        Two methods are used and both results are returned:

        1. Normalised Weighted Distance (NWD) — default and recommended.
           Each objective is normalised to [0, 1] then the Euclidean distance
           to the ideal point (0, 0, 0) is minimised with optional weights.
           A solution close to the ideal in all dimensions = best compromise.

        2. Maximum Curvature (2-D projections).
           For each 2-D projection (Cmax/Mcount, Cmax/TotPena) the point
           with the largest angle formed by its two neighbours is selected
           (classic elbow/knee heuristic on sorted fronts).

        Parameters
        ----------
        pareto  : list of result dicts from generate_pareto_front()
        weights : (w_cmax, w_mcount, w_pena) — importance of each objective
                  in the NWD score. Default (1,1,1) = equal importance.

        Returns
        -------
        dict with keys:
            'nwd'       : best solution by NWD (recommended)
            'curv_cm'   : knee by curvature on Cmax vs Mcount projection
            'curv_cp'   : knee by curvature on Cmax vs TotPena projection
            'scores'    : list of (solution, nwd_score) sorted best-first
        """
        if not pareto:
            raise ValueError("Pareto front is empty.")

        Cmax_v   = np.array([r['Cmax']    for r in pareto])
        Mcount_v = np.array([r['Mcount']  for r in pareto])
        Pena_v   = np.array([r['TotPena'] for r in pareto])

        def _norm(v):
            lo, hi = v.min(), v.max()
            return (v - lo) / (hi - lo + 1e-12)

        Cn = _norm(Cmax_v)
        Mn = _norm(Mcount_v)
        Pn = _norm(Pena_v)

        w1, w2, w3 = weights
        scores = np.sqrt(w1 * Cn**2 + w2 * Mn**2 + w3 * Pn**2)
        ranked = sorted(zip(scores, pareto), key=lambda x: x[0])
        best_nwd = ranked[0][1]

        def _curvature_knee(x, y, solutions):
            """Return solution at max angle (knee) in a 2-D sorted front."""
            order   = np.argsort(x)
            xs, ys  = x[order], y[order]
            sols    = [solutions[i] for i in order]
            if len(xs) < 3:
                return sols[0]
            angles = []
            for i in range(1, len(xs) - 1):
                v1 = np.array([xs[i-1] - xs[i], ys[i-1] - ys[i]])
                v2 = np.array([xs[i+1] - xs[i], ys[i+1] - ys[i]])
                cos_a = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12)
                angles.append(np.arccos(np.clip(cos_a, -1, 1)))
            return sols[np.argmax(angles) + 1]

        knee_cm = _curvature_knee(_norm(Mcount_v), _norm(Cmax_v), pareto)
        knee_cp = _curvature_knee(_norm(Pena_v),   _norm(Cmax_v), pareto)

        print("\n[Knee-Point Detector] Results:")
        print(f"  NWD best     : Cmax={best_nwd['Cmax']:.2f}  "
              f"Mcount={best_nwd['Mcount']:.0f}  TotPena={best_nwd['TotPena']:.4f}")
        print(f"  Curv Cmax/M  : Cmax={knee_cm['Cmax']:.2f}  "
              f"Mcount={knee_cm['Mcount']:.0f}  TotPena={knee_cm['TotPena']:.4f}")
        print(f"  Curv Cmax/P  : Cmax={knee_cp['Cmax']:.2f}  "
              f"Mcount={knee_cp['Mcount']:.0f}  TotPena={knee_cp['TotPena']:.4f}")

        return {
            'nwd':      best_nwd,
            'curv_cm':  knee_cm,
            'curv_cp':  knee_cp,
            'scores':   [(sol, float(sc)) for sc, sol in ranked],
        }

    # -----------------------------------------------------------------------
    # Gantt export
    # -----------------------------------------------------------------------
    def export_gantt(self, solution_dict, output_dir="Results/",
                     label_suffix="", show=True):
        """
        Generate and save a Gantt chart for a given Pareto solution.

        Parameters
        ----------
        solution_dict : one result dict from the Pareto front
                        (must have key 'solution' = optsolution list)
        output_dir    : directory where PNG and JSON are saved
        label_suffix  : appended to the file/chart name for identification
        show          : whether to call plt.show() immediately

        The method calls your existing save_JSON, lire_fichier_json,
        plotGantt and plotGantt2 helpers so the output format is
        100 % compatible with the rest of your pipeline.

        Returns
        -------
        str : path of the saved Gantt PNG file
        """
        import os
        from fonctions.diagram import plotGantt, plotGantt2, build_gantt_result_from_solution
        from fonctions.Save_Read_JSON import save_JSON, lire_fichier_json

        if not solution_dict.get('feasible', False):
            print("[export_gantt] Solution is infeasible — nothing to plot.")
            return None

        optsolution = solution_dict['solution']
        cmax        = solution_dict['Cmax']
        mcount      = solution_dict['Mcount']
        pena        = solution_dict['TotPena']

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "JSONS"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "Gantts"), exist_ok=True)

        tag  = f"eps_Cmax{cmax:.1f}_M{mcount:.0f}_P{pena:.3f}"
        if label_suffix:
            tag += f"_{label_suffix}"

        json_path  = os.path.join(output_dir, "JSONS",  f"{tag}.json")
        gantt_path = os.path.join(output_dir, "Gantts", tag)
        gantt_path += f"/{tag}"
        # Save JSON (same format as your pipeline)
        weights_used = (1.0, 0.0, 0.0)   # epsilon-constraint: Cmax was the objective
        save_JSON(self.data, optsolution, json_path, weights_used)
        result = lire_fichier_json(json_path)

        # Chart title
        chart_title = (f"Epsilon-Constraint-Cmax={cmax:.1f}  "
                       f"Maint={mcount:.0f}  Pena={pena:.3f}")

        # Primary Gantt (your existing function)
        plotGantt(result, gantt_path, chart_title, showgantt=show)

        # Secondary Gantt with plotGantt2 (lighter format)
        result2 = build_gantt_result_from_solution(self.data, optsolution)
        plotGantt2(result2, tag, f"Cmax={cmax:.1f}", show)

        png_path = gantt_path + ".png"
        print(f"[export_gantt] Saved → {png_path}")
        return png_path

    def export_gantt_all(self, pareto, output_dir="Results/",
                         knee_result=None, show=False):
        """
        Export Gantt charts for every solution on the Pareto front.
        If knee_result is provided, the knee-point solutions get a
        special '_KNEE_NWD' / '_KNEE_CURV' suffix for easy identification.

        Parameters
        ----------
        pareto       : full Pareto front list
        output_dir   : root output directory
        knee_result  : dict returned by find_knee_point() (optional)
        show         : display each chart interactively (False = save only)
        """
        knee_ids = {}
        if knee_result:
            knee_ids[id(knee_result['nwd'])]     = "KNEE_NWD"
            knee_ids[id(knee_result['curv_cm'])] = "KNEE_CURV_CM"
            knee_ids[id(knee_result['curv_cp'])] = "KNEE_CURV_CP"

        print(f"\n[export_gantt_all] Exporting {len(pareto)} Gantt charts...")
        for i, sol in enumerate(pareto, 1):
            suffix = knee_ids.get(id(sol), f"sol{i:03d}")
            self.export_gantt(sol, output_dir=output_dir,
                              label_suffix=suffix, show=show)
        print("[export_gantt_all] Done.\n")

    # -----------------------------------------------------------------------
    # Visualization
    # -----------------------------------------------------------------------
    def plot_pareto(self, pareto, knee_result=None,
                    title="Pareto Front — FJSP Epsilon-Constraint"):
        """
        2-D projections + 3-D scatter of the Pareto front.
        If knee_result is provided (from find_knee_point()), the NWD knee
        point is highlighted with a red star on every subplot.

        Parameters
        ----------
        pareto      : list of result dicts
        knee_result : dict returned by find_knee_point() — optional
        title       : figure suptitle
        """
        if not pareto:
            print("No feasible solutions to plot.")
            return

        Cmax_v   = np.array([r['Cmax']    for r in pareto])
        Mcount_v = np.array([r['Mcount']  for r in pareto])
        Pena_v   = np.array([r['TotPena'] for r in pareto])

        # Knee coordinates (NWD)
        knee = knee_result['nwd'] if knee_result else None

        fig = plt.figure(figsize=(18, 5))
        fig.suptitle(title, fontsize=13, fontweight='bold')

        # ---- helper: add knee star ----
        def _add_knee(ax, kx, ky):
            if knee is not None:
                ax.scatter([kx], [ky], c='red', marker='*', s=280,
                           zorder=5, label='Knee (NWD)')
                ax.legend(fontsize=8)

        # 2D: Cmax vs Mcount
        ax1 = fig.add_subplot(1, 3, 1)
        ax1.scatter(Mcount_v, Cmax_v, c='steelblue', edgecolors='k', s=60, zorder=3)
        _add_knee(ax1, knee['Mcount'] if knee else None,
                       knee['Cmax']   if knee else None)
        ax1.set_xlabel("Mcount (nb maintenances)")
        ax1.set_ylabel("Cmax (makespan)")
        ax1.set_title("Cmax vs Mcount")
        ax1.grid(True, linestyle='--', alpha=0.5)

        # 2D: Cmax vs TotPena
        ax2 = fig.add_subplot(1, 3, 2)
        ax2.scatter(Pena_v, Cmax_v, c='tomato', edgecolors='k', s=60, zorder=3)
        _add_knee(ax2, knee['TotPena'] if knee else None,
                       knee['Cmax']    if knee else None)
        ax2.set_xlabel("TotPena (qualité)")
        ax2.set_ylabel("Cmax (makespan)")
        ax2.set_title("Cmax vs TotPena")
        ax2.grid(True, linestyle='--', alpha=0.5)

        # 3D
        ax3 = fig.add_subplot(1, 3, 3, projection='3d')
        sc = ax3.scatter(Mcount_v, Pena_v, Cmax_v,
                         c=Cmax_v, cmap='viridis', s=60, edgecolors='k', alpha=0.8)
        if knee:
            ax3.scatter([knee['Mcount']], [knee['TotPena']], [knee['Cmax']],
                        c='red', marker='*', s=300, zorder=5, label='Knee (NWD)')
            ax3.legend(fontsize=8)
        ax3.set_xlabel("Mcount")
        ax3.set_ylabel("TotPena")
        ax3.set_zlabel("Cmax")
        ax3.set_title("Front de Pareto 3D")
        fig.colorbar(sc, ax=ax3, shrink=0.5, label="Cmax")

        plt.tight_layout()
        plt.show()

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    @staticmethod
    def save_pareto_csv(pareto, filepath="pareto_front.csv"):
        """Save the Pareto front to a CSV file."""
        if not pareto:
            print("Nothing to save.")
            return
        fieldnames = ['eps1', 'eps2', 'Cmax', 'Mcount', 'TotPena', 'avgoq', 'cputime']
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in pareto:
                writer.writerow({k: r.get(k, '') for k in fieldnames})
        print(f"Pareto front saved to '{filepath}'  ({len(pareto)} solutions)")

    def solve_max_quality(self, epsilon_time=None, epsilon_maint=None, time_limit=3600):
        # ... (variables et contraintes d'ordonnancement inchangées) ...
    
        # 1. Contrainte Epsilon sur le Temps (Makespan)
        if epsilon_time is not None:
            m.addConstr(Cmax <= epsilon_time, name="limit_makespan")
    
        # 2. Contrainte Epsilon sur la Maintenance
        if epsilon_maint is not None:
            m.addConstr(Mcount <= epsilon_maint, name="limit_maint")
    
        # 3. Objectif : Maximiser la Qualité Moyenne
        # AOQ = (1/nbJobs) * sum(Qj)
        avg_quality = gp.quicksum(Qj[j] for j in J) / data.nbJobs
        m.setObjective(avg_quality, GRB.MAXIMIZE)
    
        m.Params.TimeLimit = time_limit
        m.optimize()
        
        # ... (extraction des résultats) ...
        return optsolution, optCmax, cputime, nbrmaint, m.objVal, qualpenal

# ===========================================================================
# Example usage
# ===========================================================================
if __name__ == "__main__":
    from fonctions.CommonFunctions import parse_degradations_file, parse_operations_file
    from fonctions.data import Data

    n1, n2 = 1, 1
    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = \
        parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = \
        parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")

    DATA = Data(nbJobs, nbMachines, nbComposants, seuils_degradation,
                dureeMaintenances, degradations, degradations2,
                nbOperationsParJob, dureeOperations, processingTimes)

    # Parameters
    alphakl   = 0.2
    betakl    = 0.15
    aql       = 0.8
    lambdakl  = 0.9
    dureemaint = 2

    DATA.alpha_kl       = [[alphakl for _ in range(nbComposants[k])] for k in range(nbMachines)]
    DATA.degradations   = [[[[betakl for _ in range(nbOperationsParJob[j])]
                              for j in range(nbJobs)]
                             for _ in range(nbComposants[k])]
                            for k in range(nbMachines)]
    DATA.Qjmin          = [aql for _ in range(nbJobs)]
    DATA.seuils_degradation = [[lambdakl for _ in range(nbComposants[k])] for k in range(nbMachines)]
    DATA.dureeMaintenances  = [[dureemaint for _ in range(nbComposants[k])] for k in range(nbMachines)]

    alphas = DATA.alpha_kl
    qinit  = [1.0 for _ in range(nbJobs)]
    qmin   = [aql for _ in range(nbJobs)]

    # -----------------------------------------------------------------------
    # Create solver and generate Pareto front
    # -----------------------------------------------------------------------
    solver = FJSP_EpsilonConstraint(
        DATA, alphas, aql, qinit, qmin,
        weights=(1.0, 0.0, 0.0)   # initial weights (overridden internally)
    )

    pareto = solver.generate_pareto_front(
        n_eps=8,             # 8×8 = 64 solves
        time_limit=120,      # 2 min per solve
        mip_gap=0.02,
        verbose=False
    )

    solver.plot_pareto(pareto)
    solver.save_pareto_csv(pareto, "Results/pareto_front.csv")

    # -----------------------------------------------------------------------
    # Knee-point: find the best compromise on the Pareto front
    # -----------------------------------------------------------------------
    knee = solver.find_knee_point(pareto, weights=(1.0, 1.0, 1.0))
    best = knee['nwd']   # recommended solution

    print(f"\n=== Knee-point (NWD) ===")
    print(f"  Cmax    = {best['Cmax']:.2f}")
    print(f"  Mcount  = {best['Mcount']:.0f}")
    print(f"  TotPena = {best['TotPena']:.4f}")
    print(f"  AvgOQ   = {best.get('avgoq', 'N/A')}")

    # Re-plot with knee highlighted
    solver.plot_pareto(pareto, knee_result=knee)

    # -----------------------------------------------------------------------
    # Export Gantt for the knee-point solution only
    # -----------------------------------------------------------------------
    solver.export_gantt(best, output_dir="Results/", label_suffix="KNEE_NWD", show=True)

    # --- OR export Gantt for every Pareto solution (show=False = save only) ---
    # solver.export_gantt_all(pareto, output_dir="Results/", knee_result=knee, show=False)