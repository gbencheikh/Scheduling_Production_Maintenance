# -*- coding: utf-8 -*-
"""
Created on Wed Nov  5 16:37:08 2025

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

class FJSP_Maintenance_Quality_complex_systems__model:
    def __init__(self, datas, n_max=3,wheights=[1.0,0.0,0.0]): 
        self.inf= 999999
        self.n_max = n_max
        self.wheights =wheights
        self.data = datas
        self.alpha_kl = [[.01 for l in range(datas.nbComposants[k])] for k in range(self.data.nbMachines)]
        self.AQL = 0.8
        self.Qinitj = [1.0 for j in range(self.data.nbJobs)]  # Exemple de taux de qualité initiale
        self.Qjmin = [0.8 for j in range(self.data.nbJobs)]   # Exemple de taux de qualité minimale acceptable
        
    def solve(self):
        data = self.data
        J = data.nbJobs
        K = data.nbMachines
        N = self.n_max
        O_j = data.nbOperationsParJob  # liste longueur J
        L_k = data.nbComposants        # liste longueur K
    
        # --- Bornes serrées -----------------------------------------------------
        # Dmax_kl[k][l] : dégradation cumulable max (sans maintenance) sur (k,l)
        Dmax_kl = [
            [
                sum(data.dureeOperations[k][j][i] * data.degradations[k][l][j][i]  for j in range(J)  for i in range(O_j[j]))
                for l in range(L_k[k])
            ]
            for k in range(K)
        ]
    
        # M_Ekl[k][l] : Big-M local pour E vs 1
        M_Ekl = [[max(1.0, Dmax_kl[k][l]) for l in range(L_k[k])] for k in range(K)]
    
        # t_max (borne sur les dates de début) : somme, par job, du max_k p[k][j][i]
        tmax_j = [
            sum(max(data.dureeOperations[k][j][i] for k in range(K)) for i in range(O_j[j]))
            for j in range(J)
        ]
        t_max = sum(tmax_j)
    
        # --- Modèle -------------------------------------------------------------
        model = Model(solver_name=GRB)
    
        # --- Variables ----------------------------------------------------------
        # x[n][k][j][i] = 1 si (j,i) est planifiée au slot n sur machine k
        x = []
        for n in range(N):
            x_n = []
            for k in range(K):
                x_nk = [
                    [model.add_var(var_type=BINARY) for _i in range(O_j[j])] for j in range(J)
                ]
                x_n.append(x_nk)
            x.append(x_n)
    
        # v[n][k] = 1 si le slot n de la machine k est utilisé par une opération
        v = [[model.add_var(var_type=BINARY) for k in range(K)] for n in range(N)]
    
        # w[n][k][j_][i_][j][i] = 1 si (j_,i_) au slot n de k est suivie de (j,i) au slot n+1 de k
        w = []
        for n in range(N-1):
            w_n = []
            for k in range(K):
                w_nk = []
                for j_ in range(J):
                    w_nkj_ = []
                    for i_ in range(O_j[j_]):
                        w_nkj_i_ = []
                        for j in range(J):
                            w_nkj_i_j = [model.add_var(var_type=BINARY) for i in range(O_j[j])]
                            w_nkj_i_.append(w_nkj_i_j)
                        w_nkj_.append(w_nkj_i_)
                    w_nk.append(w_nkj_)
                w_n.append(w_nk)
            w.append(w_n)
    
        # y[n][k][l] = 1 si un entretien du composant l est réalisé sur k entre les slots n et n+1
        y = [
            [
                [model.add_var(var_type=BINARY) for l in range(L_k[k])] for k in range(K)
            ]
            for _n in range(N)
        ]
    
        # z = AND(w,y) pour compter le temps d'entretien sur les transitions
        z = []
        for n in range(N-1):
            z_n = []
            for k in range(K):
                z_nk = []
                for l in range(L_k[k]):
                    z_nkl = []
                    for j_ in range(J):
                        z_nklj_ = []
                        for i_ in range(O_j[j_]):
                            z_nklj_i_ = []
                            for j in range(J):
                                z_nklj_i_j = [model.add_var(var_type=BINARY) for i in range(O_j[j])]
                                z_nklj_i_.append(z_nklj_i_j)
                            z_nklj_.append(z_nklj_i_)
                        z_nkl.append(z_nklj_)
                    z_nk.append(z_nkl)
                z_n.append(z_nk)
            z.append(z_n)
    
        # Dates de début t[j][i]
        t = [[model.add_var(lb=0, ub=t_max) for i in range(O_j[j])] for j in range(J)]
    
        # Linéarisation prod_w_t = w * t(j',i')
        prod_w_t = []
        for n in range(N-1):
            pwt_n = []
            for k in range(K):
                pwt_nk = []
                for j_ in range(J):
                    pwt_nkj_ = []
                    for i_ in range(O_j[j_]):
                        pwt_nkj_i_ = []
                        for j in range(J):
                            pwt_nkj_i_j = [model.add_var(lb=0, ub=t_max) for i in range(O_j[j])]
                            pwt_nkj_i_.append(pwt_nkj_i_j)
                        pwt_nkj_.append(pwt_nkj_i_)
                    pwt_nk.append(pwt_nkj_)
                pwt_n.append(pwt_nk)
            prod_w_t.append(pwt_n)
    
        # E[n][k][l] et D[n][k][l] (D = min(E,1)) et binaire b[n][k][l]
        E = [
            [
                [model.add_var(lb=0, ub=M_Ekl[k][l]) for l in range(L_k[k])] for k in range(K)
            ]
            for _n in range(N)
        ]
        D = [
            [
                [model.add_var(lb=0, ub=1.0) for l in range(L_k[k])] for k in range(K)
            ]
            for _n in range(N)
        ]
        b = [
            [
                [model.add_var(var_type=BINARY) for l in range(L_k[k])] for k in range(K)
            ]
            for _n in range(N)
        ]
    
        # prod_y_d[n][k][l] = y[n][k][l] * D[n][k][l] (utilisé dans la récurrence de E)
        prod_y_d = [
            [
                [model.add_var(lb=0, ub=Dmax_kl[k][l]) for l in range(L_k[k])] for k in range(K)
            ]
            for _n in range(N-1)
        ]
    
        # prod_x_D[n][k][l][j][i] = x[n][k][j][i] * D[n][k][l]
        prod_x_D = []
        for n in range(N):
            pxD_n = []
            for k in range(K):
                pxD_nk = []
                for l in range(L_k[k]):
                    pxD_nkl = []
                    for j in range(J):
                        pxD_nklj = [model.add_var(lb=0, ub=1.0) for i in range(O_j[j])]
                        pxD_nkl.append(pxD_nklj)
                    pxD_nk.append(pxD_nkl)
                pxD_n.append(pxD_nk)
            prod_x_D.append(pxD_n)
    
        # Qualité
        Qji = [[model.add_var(lb=0, ub=1.0) for i in range(O_j[j])] for j in range(J)]
        Qj  = [model.add_var(lb=0, ub=1.0) for _j in range(J)]
        penal = [model.add_var(var_type=BINARY) for _j in range(J)]
    
        # Indicateurs objectifs
        Cmax   = model.add_var(lb=0)
        Mcount = model.add_var(lb=0)  # somme des y
        TotPena = model.add_var(lb=0)
        avgoq  = model.add_var(lb=0, ub=1.0)
    
        # --- Contraintes --------------------------------------------------------
        # (1) Calcul de E par récurrence
        for k in range(K):
            for l in range(L_k[k]):
                # n = 0
                model += E[0][k][l] == xsum(
                    x[0][k][j][i] * data.dureeOperations[k][j][i] * data.degradations[k][l][j][i]
                    for j in range(J) for i in range(O_j[j])
                )
                # n >= 1
                for n in range(1, N):
                    model += E[n][k][l] == (
                        D[n-1][k][l]
                        - (prod_y_d[n-1][k][l] if n-1 < N-1 else 0)
                        + xsum(
                            x[n][k][j][i] * data.dureeOperations[k][j][i] * data.degradations[k][l][j][i]
                            for j in range(J) for i in range(O_j[j])
                        )
                    )
    
        # (2) D = min(E, 1) via b et M_Ekl
        for n in range(N):
            for k in range(K):
                for l in range(L_k[k]):
                    M = M_Ekl[k][l]
                    model += D[n][k][l] <= E[n][k][l]
                    model += D[n][k][l] >= E[n][k][l] - M * (1 - b[n][k][l])
                    model += D[n][k][l] <= 1
                    model += D[n][k][l] >= 1 - M * b[n][k][l]
                    model += E[n][k][l] <= 1 + M * (1 - b[n][k][l])
                    model += E[n][k][l] >= 1 - M * b[n][k][l]
    
        # (3) McCormick : prod_y_d = y * D (n in 0..N-2)
        for n in range(N-1):
            for k in range(K):
                for l in range(L_k[k]):
                    M = Dmax_kl[k][l]
                    model += prod_y_d[n][k][l] >= 0
                    model += prod_y_d[n][k][l] <= D[n][k][l]
                    model += prod_y_d[n][k][l] <= y[n][k][l] * M
                    model += prod_y_d[n][k][l] >= D[n][k][l] - (1 - y[n][k][l]) * M
    
        # (4) McCormick : prod_x_D = x * D
        for n in range(N):
            for k in range(K):
                for l in range(L_k[k]):
                    for j in range(J):
                        for i in range(O_j[j]):
                            model += prod_x_D[n][k][l][j][i] >= 0
                            model += prod_x_D[n][k][l][j][i] <= D[n][k][l]
                            model += prod_x_D[n][k][l][j][i] <= x[n][k][j][i]
                            model += prod_x_D[n][k][l][j][i] >= D[n][k][l] - (1 - x[n][k][j][i])
    
        # (5) Qualité par job (Qji puis Qj)
        for j in range(J):
            # i = 0
            model += Qji[j][0] == self.Qinitj[j] - xsum(
                prod_x_D[n][k][l][j][0] * self.alpha_kl[k][l]
                for n in range(N) for k in range(K) for l in range(L_k[k])
            )
            # i > 0
            for i in range(1, O_j[j]):
                model += Qji[j][i] == Qji[j][i-1] - xsum(
                    prod_x_D[n][k][l][j][i] * self.alpha_kl[k][l]
                    for n in range(N) for k in range(K) for l in range(L_k[k])
                )
            model += Qj[j] == Qji[j][O_j[j]-1]
    
        # (6) y déclenché quand D dépasse le seuil, et y lié aux transitions
        for n in range(N-1):
            for k in range(K):
                # seuil -> possibilité d'entretien
                for l in range(L_k[k]):
                    # si D - seuil > 0 alors y doit pouvoir être 1 (binaire contraint par l'inégalité)
                    model += y[n][k][l] * max(1.0, Dmax_kl[k][l]) >= D[n][k][l] - data.seuils_degradation[k][l]
    
                # y possible seulement s'il existe une transition
                trans_nk = xsum(
                    w[n][k][j_][i_][j][i]
                    for j_ in range(J) for i_ in range(O_j[j_])
                    for j in range(J)  for i  in range(O_j[j])
                )
                for l in range(L_k[k]):
                    model += y[n][k][l] <= trans_nk
    
                # Option : au plus un composant entretenu par transition (dé-commentez si souhaité)
                # model += xsum(y[n][k][l] for l in range(L_k[k])) <= 1
    
        # (7) Définition de w = AND(x_n, x_{n+1})
        for n in range(N-1):
            for k in range(K):
                for j_ in range(J):
                    for i_ in range(O_j[j_]):
                        for j in range(J):
                            for i in range(O_j[j]):
                                model += w[n][k][j_][i_][j][i] <= x[n][k][j_][i_]
                                model += w[n][k][j_][i_][j][i] <= x[n+1][k][j][i]
                                model += w[n][k][j_][i_][j][i] >= x[n][k][j_][i_] + x[n+1][k][j][i] - 1
    
        # (8) z = AND(w, y) (pour compter le temps d'entretien)
        for n in range(N-1):
            for k in range(K):
                for l in range(L_k[k]):
                    for j_ in range(J):
                        for i_ in range(O_j[j_]):
                            for j in range(J):
                                for i in range(O_j[j]):
                                    model += z[n][k][l][j_][i_][j][i] <= w[n][k][j_][i_][j][i]
                                    model += z[n][k][l][j_][i_][j][i] <= y[n][k][l]
                                    model += z[n][k][l][j_][i_][j][i] >= w[n][k][j_][i_][j][i] + y[n][k][l] - 1
    
        # (9) Linéarisation prod_w_t = w * t(j',i')
        for n in range(N-1):
            for k in range(K):
                for j_ in range(J):
                    for i_ in range(O_j[j_]):
                        for j in range(J):
                            for i in range(O_j[j]):
                                model += prod_w_t[n][k][j_][i_][j][i] >= 0
                                model += prod_w_t[n][k][j_][i_][j][i] <= w[n][k][j_][i_][j][i] * t_max
                                model += prod_w_t[n][k][j_][i_][j][i] <= t[j_][i_]
                                model += prod_w_t[n][k][j_][i_][j][i] >= t[j_][i_] - (1 - w[n][k][j_][i_][j][i]) * t_max
    
        # (10) Précédence inter-slots sur chaque machine (avec entretien agrégé via z)
        for n in range(N-1):
            for k in range(K):
                for j_ in range(J):
                    for i_ in range(O_j[j_]):
                        for j in range(J):
                            for i in range(O_j[j]):
                                maint_time = xsum(
                                    z[n][k][l][j_][i_][j][i] * data.dureeMaintenances[k][l]
                                    for l in range(L_k[k])
                                )
                                model += t[j][i] >= (
                                    prod_w_t[n][k][j_][i_][j][i]
                                    + w[n][k][j_][i_][j][i] * data.dureeOperations[k][j_][i_]
                                    + maint_time
                                )
    
        # (11) Précédence intra-job
        for j in range(J):
            for i in range(O_j[j] - 1):
                model += t[j][i+1] >= t[j][i] + xsum(
                    x[n][k][j][i] * data.dureeOperations[k][j][i]
                    for n in range(N) for k in range(K)
                )
    
        # (12) Affectation : chaque (j,i) planifiée exactement une fois
        for j in range(J):
            for i in range(O_j[j]):
                model += xsum(x[n][k][j][i] for n in range(N) for k in range(K)) == 1
    
        # (13) Cohérence v[n][k] et monotonie des slots
        for k in range(K):
            for n in range(N-1):
                model += v[n][k] >= v[n+1][k]
            for n in range(N):
                model += xsum(x[n][k][j][i] for j in range(J) for i in range(O_j[j])) == v[n][k]
    
        # (14) Indicateurs objectifs
        # Cmax
        for j in range(J):
            last_i = O_j[j] - 1
            model += Cmax >= t[j][last_i] + xsum(
                x[n][k][j][last_i] * data.dureeOperations[k][j][last_i]
                for n in range(N) for k in range(K)
            )
        # Nombre total d'entretiens
        model += Mcount == xsum(y[n][k][l] for n in range(N-1) for k in range(K) for l in range(L_k[k]))
        # Pénalité qualité / moyenne de défauts
        model += TotPena == xsum(penal[j] for j in range(J))
        model += avgoq == xsum((1 - Qj[j]) for j in range(J)) / J
    
        # Activation de penal si Qj < Qjmin (binaire -> 1 quand l'écart est positif)
        for j in range(J):
            model += penal[j] >= self.Qjmin[j] - Qj[j]
            model += penal[j] <= 1  # bornage explicite
    
        # --- Objectif -----------------------------------------------------------
        # Si self.wheights a 3 éléments : (Cmax, Mcount, avgoq)
        # Si 4 éléments : ajoutez TotPena
        wts = self.wheights
        expr = wts[0] * Cmax + wts[1] * Mcount + wts[2] * avgoq
        if len(wts) >= 4:
            expr += wts[3] * TotPena
        model.objective = minimize(expr)    
        
        
        t0 = time.perf_counter()
        model.optimize()
        cputime1 = time.perf_counter()-t0
        optCmax1 = Cmax.x
        qualpenal1 = sum(penal[j].x for j in range(self.data.nbJobs))
        nbrmaint1  = Mcount.x

        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                degradation_sumi = sum(prod_x_D[n][k][l][j][i].x * self.alpha_kl[k][l] for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k]))
                aa=[(k,n) for n in range(self.n_max) for k in range(self.data.nbMachines) if x[n][k][j][i].x]
                bb=[D[n][k][l].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k]) if x[n][k][j][i].x]
                print(f"j={j} i={i} x={aa} D={bb} degradation_sum{i} {degradation_sumi}")
                Dkln=[D[n][k][l].x for l in range(self.data.nbComposants[k])]
        
        optsolution1 = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [sum(k*int(x[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            #[[[max([(int(x[n][k][j][i].x)*int(y[n][k][l].x)) for n in range(self.n_max) for k in range(self.data.nbMachines)])  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))]
            [[[False  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))],
            [[int(t[j][i].x) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)],
            [sum(n*int(x[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])]
        ]
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                mach=sum(k*int(x[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines))
                rank=sum(n*int(x[n][mach][j][i].x) for n in range(self.n_max))
                maxdeg=max([D[rank][mach][l].x for l in range(self.data.nbComposants[mach])] )
                stime=int(t[j][i].x)
                ptime=sum([int(x[n][k][j][i].x) * self.data.dureeOperations[k][j][i]  for n in range(self.n_max)  for k in range(self.data.nbMachines)])
                maintafter=False
                for l in range(self.data.nbComposants[mach]):
                    if y[rank][mach][l].x:
                        maintafter=True
                        break
                print("O_%d,%d : machine=%d  start=%d end=%d rank=%d max_machDeg=%.2f maintAfter=%s" % (j+1,i+1,mach+1,stime,stime+ptime,rank, maxdeg,maintafter))
                
        for k in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[k]):
                for j in range(self.data.nbJobs):
                    #temp=False
                    for i in range(self.data.nbOperationsParJob[j]):
                        for n in range(self.n_max):
                            temp=(x[n][k][j][i].x and y[n][k][l].x)
                            if temp==True:
                                optsolution1[2][l][j][i] =True
                                #print("break 1 -->", " on machine=",k+1 , "component =",l+1, " job ",j+1," operation ",i+1, " n=",n+1)
                                break
        avgoq1=sum((1-Qj[j].x) for j in range(self.data.nbJobs))/self.data.nbJobs
        #for k in range(self.data.nbMachines):
        #    print([["{:.2f}".format(D[n][k][l].x) for l in range(self.data.nbComposants[k]) ] for n in range(self.n_max)])
        
        for j in range(self.data.nbJobs):
            plt.plot([Qji[j][i].x for i in range(self.data.nbOperationsParJob[j])])
            plt.title(f"Qj evolution of job {j}",fontsize=15)
            plt.show()
            print([Qji[j][i].x for i in range(self.data.nbOperationsParJob[j])])
            print([max(prod_x_D[n][k][l][j][i].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k])) for i in range(self.data.nbOperationsParJob[j])])
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
    alphakl=0.3         # quality degradation rate
    betakl=0.1          # average degradation rate of componenets 
    std_betakl=0.0      # standard deviation of degradation rate of componenets
    qjmin=0.9          # acceptable quality level triggering quality penality ()
    lambdakl=1.0        # degradation threshold triggering PdM 
    dureemaint=1        # maintenance duration
    

    DATA.alpha_kl = [[alphakl for l in range(nbComposants[k])] for k in range(nbMachines)]
    x=betakl #float(np.round(max(0,np.random.normal(betakl, std_betakl, 1)[0]),3))
    #print(x)
    DATA.degradations=[[[[x  for ido in range(nbOperationsParJob[j])]  for j in range(nbJobs) ] for l in range(nbComposants[k])] for k in range(nbMachines)]
    DATA.Qjmin = [qjmin for j in range(nbJobs)] 
    #print(DATA.seuils_degradation)  
    DATA.seuils_degradation = [[lambdakl for l in range(nbComposants[k])] for k in range(nbMachines)] 
    DATA.dureeMaintenances = [[dureemaint for l in range(nbComposants[k])] for k in range(nbMachines)]
     
    model = FJSP_Maintenance_Quality_complex_systems__model(DATA)
    #model.wheights = [0.7,0.2,0.1]
    model.wheights = [1.0,1.0,0.0]
    model.n_max = 4
    model.Qinitj = [1.0 for j in range(nbJobs)]  # Exemple de taux de qualité initiale
    model.Qjmin = [qjmin for j in range(nbJobs)]   # Exemple de taux de qualité minimale acceptable
    model.alpha_kl = [[alphakl for l in range(nbComposants[k])] for k in range(nbMachines)]  # Exemple de coefficients de détérioration de la qualité   
    model.AQL = qjmin
    model.data = DATA
    
    optsolution1, optCmax1, cputime1, nbrmaint1, avgoq1, qualpenal1 = model.solve()
    #print(optsolution1)

    Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost,NbMaint,AOQ,penality = completionTime_previous(DATA, optsolution1, model.wheights)
    #Tij, Cij, CMAX, DEG, Ykl, i_s, OQj, TotCost,NbMaint,AOQ,penality,feasability = completionTime(model.data, optsolution1, model.wheights)
    
    print("optCmax1=",optCmax1, " CMAX=",CMAX)
    print("nbrmaint1=",nbrmaint1," NbMaint=",NbMaint)
    print("avgoq1=",avgoq1, " AOQ=",AOQ)
    #print("optsolution1=",optsolution1)
    k=1
    save_JSON(model.data,optsolution1,f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json",model.wheights)
    result = lire_fichier_json(f"Results/JSONS/MILP4testk{n1}inst{n2}_{k}.json")
    plotGantt(result, f"Results/Gantts/MILP4testk{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showgantt=True)
    #plotDEGRAD(result, model.data,  f"Results/EHFs/MILP{n1}inst{n2}_figure_{k}",f"MILP-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showdegrad=True)
    plotEHF(   result, model.data,  f"Results/EHFs/MILP4{n1}inst{n2}_figure_{k}",f"MILP4-k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showdegrad=True)
    
    #print("optCmax1=", optCmax1," avgoq1=", avgoq1, " qualpenal1=",qualpenal1, " nbrmaint1=",nbrmaint1,  "CPUTime=",cputime1)              
   
    plt.show()   
def Run_solver(data):
    model = FJSP_Maintenance_Quality_complex_systems__model(data)
    model.data=data
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=model.solve()
    return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1
