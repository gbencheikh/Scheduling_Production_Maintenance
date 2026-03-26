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
        # variables :
        model = Model()
        maxComposants = max(self.data.nbComposants)
        D_max = max(sum(self.data.dureeOperations[k][j][i] * self.data.degradations[k][l][j][i]
                        for j in range(self.data.nbJobs)  
                        for i in range(self.data.nbOperationsParJob[j])
                        ) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k])
                    )
        t_max = sum(max(self.data.dureeOperations[k][j][i] 
                        for k in range(self.data.nbMachines)
                        ) 
                    for j in range(self.data.nbJobs)
                    for i in range(self.data.nbOperationsParJob[j]))
        M_E=max(1, D_max)
        
        Cmax = model.add_var()
        Mmax = model.add_var()
        TotPena=model.add_var()
        x_ijkn = [[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        y_kln = [[[model.add_var(var_type=BINARY) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        v_kn= [[model.add_var(var_type=BINARY) for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        w = [[[[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for i_ in range(self.data.nbOperationsParJob[j_])] for j_ in range(self.data.nbJobs)] for m in range(self.data.nbMachines)] for n in range(self.n_max)]
        z = [[[[[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for i_ in range(self.data.nbOperationsParJob[j_])] for j_ in range(self.data.nbJobs)] for l in range(maxComposants)] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
       # d_kln = [[[model.add_var(lb=0, ub=D_max) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        prod_y_d = [[[model.add_var(lb=0, ub=D_max) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        prod_w_t = [[[[[[model.add_var(lb=0, ub=t_max) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for i_ in range(self.data.nbOperationsParJob[j_])] for j_ in range(self.data.nbJobs)] for m in range(self.data.nbMachines)] for n in range(self.n_max)]
        D_kln = [[[model.add_var(lb=0, ub=D_max) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        t_ij = [[model.add_var(lb=0, ub=t_max) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)]
        prod_x_D = [[[[[model.add_var(lb=0, ub=D_max) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        Qj = [model.add_var(lb=0, ub=1)  for j in range(self.data.nbJobs)]
        Qji= [[model.add_var(lb=0, ub=1) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)]
        ZQj = [[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])]  for j in range(self.data.nbJobs)]
        #prod_x_y = [[[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        penal = [model.add_var(var_type=BINARY)  for j in range(self.data.nbJobs)]
        avgoq = model.add_var(lb=0, ub=1)
        E=[[[model.add_var(lb=0,ub=M_E) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        b=[[[model.add_var(var_type=BINARY) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        
        # Contraintes : 
        # Calcul de la dégradation
        """
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    model += d_kln[n][k][l] == xsum(x_ijkn[n][k][j][i]*self.data.dureeOperations[k][j][i] * self.data.degradations[k][l][j][i] 
                                                    for j in range(self.data.nbJobs) 
                                                    for i in range(self.data.nbOperationsParJob[j]))
                    
                    sumx=f"d_kln[{n}][{k}][{l}]="
                    for j in range(self.data.nbJobs):
                        for i in range(self.data.nbOperationsParJob[j]):
                            sumx+=f"x{n}{k}{j}{i}*{self.data.dureeOperations[k][j][i]}*{self.data.degradations[k][l][j][i]} + "
                    print(sumx)
                    """
        for k in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[k]):
                model += E[0][k][l] == xsum(x_ijkn[0][k][j][i]*self.data.dureeOperations[k][j][i]*self.data.degradations[k][l][j][i] 
                                                 for j in range(self.data.nbJobs) 
                                                 for i in range(self.data.nbOperationsParJob[j]))
                # D0 = min(1, E0) using the same “min” pattern
                model += D_kln[0][k][l] <= E[0][k][l]
                model += D_kln[0][k][l] >= E[0][k][l] - M_E * (1 - b[0][k][l])
                model += D_kln[0][k][l] <= 1
                model += D_kln[0][k][l] >= 1 - M_E * b[0][k][l]
                model += E[0][k][l] <= 1 + M_E * (1 - b[0][k][l])
                model += E[0][k][l] >= 1 - M_E * b[0][k][l]
                 
                for n in range(1,self.n_max):
                     #model += D_kln[n][k][l] == D_kln[n-1][k][l] - prod_y_d[n-1][k][l] + d_kln[n][k][l]
                     model += E[n][k][l] == D_kln[n-1][k][l] - prod_y_d[n-1][k][l] + xsum(x_ijkn[n][k][j][i]*self.data.dureeOperations[k][j][i]*self.data.degradations[k][l][j][i] 
                                                                                         for j in range(self.data.nbJobs) 
                                                                                         for i in range(self.data.nbOperationsParJob[j])) 
                for n in range(self.n_max):
                    # D ≤ E and D ≥ E when b=1  → D = E if E ≤ 1
                    model += D_kln[n][k][l] <= E[n][k][l]
                    model += D_kln[n][k][l] >= E[n][k][l] - M_E * (1 - b[n][k][l])

                    # D ≤ 1 and D ≥ 1 when b=0 → D = 1 if E ≥ 1
                    model += D_kln[n][k][l] <= 1
                    model += D_kln[n][k][l] >= 1 - M_E * b[n][k][l]

                    # Make b consistent with the side of the breakpoint at 1
                    model += E[n][k][l] <= 1 + M_E * (1 - b[n][k][l])
                    model += E[n][k][l] >= 1 - M_E * b[n][k][l]
        
                    model += prod_y_d[n][k][l] >= 0
                    model += prod_y_d[n][k][l] - y_kln[n][k][l] * D_max <= 0
                    model += prod_y_d[n][k][l] - D_kln[n][k][l] <= 0
                    model += prod_y_d[n][k][l] - D_kln[n][k][l] + D_max - y_kln[n][k][l]*D_max >= 0
        #  Calcul de la déterioration de la qualité 
        """
        for n in range(1,self.n_max):
            for k in range(self.data.nbMachines) :
                for l in range(self.data.nbComposants[k]) :
                    for j in range(self.data.nbJobs) :
                        for i in range(self.data.nbOperationsParJob[j]) :
                            model += prod_x_y[n][k][l][j][i] - x_ijkn[n][k][j][i] + y_kln[n-1][k][l] >= 0
                            model += 2*prod_x_y[n][k][l][j][i] - x_ijkn[n][k][j][i] + y_kln[n-1][k][l] <= 1
        
        # prod_x_D[n][k][l][j][i]=prod_x_y[n][k][l][j][i]*D_kln[n][k][l]
        
        for k in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[k]):
                for j in range(self.data.nbJobs):
                    for i in range(self.data.nbOperationsParJob[j]):
                        model += prod_x_D[0][k][l][j][i] == 0
        for n in range(1,self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    for j in range(self.data.nbJobs):
                        for i in range(self.data.nbOperationsParJob[j]):
                            model += prod_x_D[n][k][l][j][i] >= 0
                            model += prod_x_D[n][k][l][j][i] - D_max * prod_x_y[n][k][l][j][i] <= 0
                            model += prod_x_D[n][k][l][j][i] - D_kln[n-1][k][l] <= 0
                            model += prod_x_D[n][k][l][j][i] - D_kln[n-1][k][l] + D_max - prod_x_y[n][k][l][j][i]*D_max >= 0
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    for j in range(self.data.nbJobs):
                        for i in range(self.data.nbOperationsParJob[j]):
                            model += prod_x_D[n][k][l][j][i] >= 0
                            model += prod_x_D[n][k][l][j][i] - D_max * prod_x_y[n][k][l][j][i] <= 0
                            model += prod_x_D[n][k][l][j][i] - D_kln[n][k][l] <= 0
                            model += prod_x_D[n][k][l][j][i] - D_kln[n][k][l] + D_max - prod_x_y[n][k][l][j][i]*D_max >= 0
                            
        """
        # prod_x_D[n][k][l][j][i] = D_kln[n][k][l] if x_ijkn[n][k][j][i] = 1, 0 otherwise
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    for j in range(self.data.nbJobs):
                        for i in range(self.data.nbOperationsParJob[j]):
                            model += prod_x_D[n][k][l][j][i] >= 0
                            model += prod_x_D[n][k][l][j][i] - D_max * x_ijkn[n][k][j][i] <= 0
                            model += prod_x_D[n][k][l][j][i] - D_kln[n][k][l] <= 0
                            model += prod_x_D[n][k][l][j][i] - D_kln[n][k][l] + D_max - x_ijkn[n][k][j][i]*D_max >= 0                    
                                      
        bigM=1#sum(max([self.alpha_kl[k][l] for l in range(self.data.nbComposants[k])]) for k in range(self.data.nbMachines) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])  )
        print("bigM=",bigM)
        for j in range(self.data.nbJobs):
            degradation_sum0 = xsum(prod_x_D[n][k][l][j][0]  * self.alpha_kl[k][l] 
                                for n in range(self.n_max) 
                                for k in range(self.data.nbMachines) 
                                for l in range(self.data.nbComposants[k]))
            model += Qji[j][0] == self.Qinitj[j] - degradation_sum0
            """
            model += degradation_sum0 - self.Qinitj[j] <= bigM*(1-ZQj[j][0])
            model += self.Qinitj[j] - degradation_sum0 <= bigM*ZQj[j][0]
            model += Qji[j][0] <= self.Qinitj[j] - degradation_sum0 + bigM*(1 - ZQj[j][0])
            model += Qji[j][0] >= self.Qinitj[j] - degradation_sum0 
            model += Qji[j][0] <= bigM*ZQj[j][0]
            model += Qji[j][0] >= 0
            """
            for i in range(1,self.data.nbOperationsParJob[j]):
                degradation_sum_i = xsum(prod_x_D[n][k][l][j][i]  * self.alpha_kl[k][l] 
                                         for n in range(self.n_max) 
                                         for k in range(self.data.nbMachines) 
                                         for l in range(self.data.nbComposants[k]))
                
                model += Qji[j][i] == Qji[j][i-1] - degradation_sum_i
            
            """    
                model += degradation_sum_i - Qji[j][i-1] <= bigM*(1-ZQj[j][i])
                model += Qji[j][i-1] - degradation_sum_i <= bigM*ZQj[j][i]
                model += Qji[j][i] <= Qji[j][i-1] - degradation_sum_i + bigM*(1 - ZQj[j][i])
                model += Qji[j][i] >= Qji[j][i-1] - degradation_sum_i 
                model += Qji[j][i] <= bigM*ZQj[j][i]
                model += Qji[j][i] >= 0
            
            degradation_sum = xsum(prod_x_D[n][k][l][j][i]  * self.alpha_kl[k][l] 
                                for i in range(self.data.nbOperationsParJob[j]) 
                                for n in range(self.n_max) 
                                for k in range(self.data.nbMachines) 
                                for l in range(self.data.nbComposants[k]))
            
            for i in range(1,self.data.nbOperationsParJob[j]):
                model += Qji[j][i] >= Qji[j][i-1] -  xsum(prod_x_D[n][k][l][j][i]  * self.alpha_kl[k][l] 
                                                          for n in range(self.n_max) 
                                                          for k in range(self.data.nbMachines) 
                                                          for l in range(self.data.nbComposants[k])) 
                model += Qji[j][i] >= 0
            
            model += Qj[j] ==self.Qinitj[j] - degradation_sum
            
            model += degradation_sum - self.Qinitj[j] <= 2*(1-ZQj[j])
            model += self.Qinitj[j] - degradation_sum <= 2*ZQj[j]
            model += Qj[j] <= self.Qinitj[j] - degradation_sum + 2*(1 - ZQj[j])
            model += Qj[j] >= self.Qinitj[j] - degradation_sum 
            model += Qj[j] <= 2*ZQj[j]
            model += Qj[j] >= 0
            
            degradation_sum2 = xsum(prod_x_D[n][k][l][j][self.data.nbOperationsParJob[j]-1]  * self.alpha_kl[k][l]  
                                for n in range(self.n_max) 
                                for k in range(self.data.nbMachines) 
                                for l in range(self.data.nbComposants[k]))
            model += degradation_sum2 - self.Qinitj[j] <= 2*(1-ZQj[j])
            model += self.Qinitj[j] - degradation_sum2 <= 2*ZQj[j]
            model += Qji[j][self.data.nbOperationsParJob[j]-1] <= self.Qinitj[j] - degradation_sum2 + 2*(1 - ZQj[j])
            model += Qji[j][self.data.nbOperationsParJob[j]-1] >= self.Qinitj[j] - degradation_sum2 
            model += Qji[j][self.data.nbOperationsParJob[j]-1] <= 2*ZQj[j]
            model += Qji[j][self.data.nbOperationsParJob[j]-1] >= 0
            """
            model += Qj[j] == Qji[j][self.data.nbOperationsParJob[j]-1]
            
        ## CALCUL DE LA VARIABLE y
        eps = 1e-4
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    model += D_max*y_kln[n][k][l] >= D_kln[n][k][l] - self.data.seuils_degradation[k][l]
                    #model += y_kln[n][k][l]   <= D_kln[n][k][l]
                    #model += D_kln[n][k][l] <= self.data.seuils_degradation[k][l] + D_max * y_kln[n][k][l]
                    #model += D_kln[n][k][l] >= self.data.seuils_degradation[k][l] + eps - D_max * (1 - y_kln[n][k][l])
        ## CALCUL DE LA VARIABLE v
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                model += v_kn[n][k] == xsum(x_ijkn[n][k][j][i] 
                                            for j in range(self.data.nbJobs)
                                            for i in range(self.data.nbOperationsParJob[j]))
        ## CALCUL DE LA VARIABLE w
        for n in range(self.n_max-1):
            for k in range(self.data.nbMachines):
                for j_ in range(self.data.nbJobs):
                    for i_ in range(self.data.nbOperationsParJob[j_]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                model +=   w[n][k][j_][i_][j][i] - x_ijkn[n][k][j_][i_] - x_ijkn[n+1][k][j][i] >= -1
                                #model += 2*w[n][k][j_][i_][j][i] - x_ijkn[n][k][j_][i_] - x_ijkn[n+1][k][j][i] <= 0
                                model += w[n][k][j_][i_][j][i] <= x_ijkn[n][k][j_][i_]
                                model += w[n][k][j_][i_][j][i] <= x_ijkn[n+1][k][j][i]
        ## CALCUL DE LA VARIABLE z
        for n in range(self.n_max-1):
            for k in range(self.data.nbMachines):
                for j_ in range(self.data.nbJobs):
                    for i_ in range(self.data.nbOperationsParJob[j_]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                for l in range(self.data.nbComposants[k]):
                                    #model +=  z[n][k][l][j_][i_][j][i] - w[n][k][j_][i_][j][i] - y_kln[n][k][l] >= -1
                                    #model +=  z[n][k][l][j_][i_][j][i] - 0.5*w[n][k][j_][i_][j][i] - 0.5*y_kln[n][k][l] <= 0
                                    model +=    z[n][k][l][j_][i_][j][i] - x_ijkn[n][k][j_][i_] - x_ijkn[n+1][k][j][i] - y_kln[n][k][l] >= -2
                                    #model +=  3*z[n][k][l][j_][i_][j][i] - x_ijkn[n][k][j_][i_] - x_ijkn[n+1][k][j][i] - y_kln[n][k][l] <= 0
                                    model +=  z[n][k][l][j_][i_][j][i] <= x_ijkn[n][k][j_][i_]
                                    model +=  z[n][k][l][j_][i_][j][i] <= x_ijkn[n+1][k][j][i] 
                                    model +=  z[n][k][l][j_][i_][j][i] <= y_kln[n][k][l]
        ## LINEARISATION DE w ET DE tij => w_nktj'i'ji*t_j'i'=t_j'i' if w_nkj'i'ji=1, 0 otherwise 
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for j_ in range(self.data.nbJobs):
                    for i_ in range(self.data.nbOperationsParJob[j_]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                model += prod_w_t[n][k][j_][i_][j][i] >= 0
                                model += prod_w_t[n][k][j_][i_][j][i] - w[n][k][j_][i_][j][i] * t_max <= 0
                                model += prod_w_t[n][k][j_][i_][j][i] - t_ij[j_][i_] <= 0
                                model += prod_w_t[n][k][j_][i_][j][i] - t_ij[j_][i_] + t_max - w[n][k][j_][i_][j][i]*t_max >= 0
                                for l in range(self.data.nbComposants[k]):
                                    model += t_ij[j][i] >= prod_w_t[n][k][j_][i_][j][i] + w[n][k][j_][i_][j][i] * self.data.dureeOperations[k][j_][i_] + z[n][k][l][j_][i_][j][i] * self.data.dureeMaintenances[k][l]
                                
                                
        ## CONTRAINTES DE PRECEDENCE DES OPERATIONS
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j] - 1):
                model += t_ij[j][i+1] >= t_ij[j][i] + xsum(x_ijkn[n][k][j][i] * self.data.dureeOperations[k][j][i]
                                                            for n in range(self.n_max)
                                                            for k in range(self.data.nbMachines))
        ## CONTRAINTES DE NON CHEVAUVHEMENT DES OPERATIONS SUR LES MACHINES
        
        """
        for l in range(maxComposants):
            for j in range(self.data.nbJobs):
                for i in range(self.data.nbOperationsParJob[j]):
                    LBtij=0
                    LBtij+=xsum(prod_w_t[n][k][j_][i_][j][i] + w[n][k][j_][i_][j][i] * self.data.dureeOperations[k][j_][i_] + z[n][k][l][j_][i_][j][i] * self.data.dureeMaintenances[k][l]
                                for n in range(self.n_max)
                                for k in range(self.data.nbMachines)
                                for j_ in range(self.data.nbJobs)
                                for i_ in range(self.data.nbOperationsParJob[j_]) if l<self.data.nbComposants[k])
                    model += t_ij[j][i] >= LBtij 
        
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                model += t_ij[j][i] >= xsum(prod_w_t[n][k][j_][i_][j][i] + w[n][k][j_][i_][j][i] * self.data.dureeOperations[k][j_][i_] 
                                            for n in range(self.n_max) 
                                            for k in range(self.data.nbMachines) 
                                            for j_ in range(self.data.nbJobs) 
                                            for i_ in range(self.data.nbOperationsParJob[j_])
                                            ) + xsum(z[n][k][l][j_][i_][j][i] * self.data.dureeMaintenances[k][l] 
                                                     for n in range(self.n_max)                                                                                        
                                                     for k in range(self.data.nbMachines) 
                                                     for l in range(self.data.nbComposants[k])
                                                     for j_ in range(self.data.nbJobs)
                                                     for i_ in range(self.data.nbOperationsParJob[j_]))
         """                                            
        ## CONTRAINTES POUR IMPOSER QUE CHAQUE OPERATION SOIT ORDONNANCEE
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                model += xsum(x_ijkn[n][k][j][i] for n in range(self.n_max) for k in range(self.data.nbMachines)) == 1
        ## CONTRAINTES SUR LES INDCES n DES OPERATIONS DES MACHINES
        for k in range(self.data.nbMachines):
            for n in range(self.n_max-1):
                model += v_kn[n][k] >= v_kn[n+1][k]
                model += v_kn[n][k] <= 1
            for n in range(self.n_max):
                model += xsum(x_ijkn[n][k][j][i]  for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])) == v_kn[n][k]
        ## CONTRAINTES DE QUALITE
        #for j in range(self.data.nbJobs):
        #    model +=  xsum((1-Qj[j]) for j in range(self.data.nbJobs))/self.data.nbJobs <= self.AQL
        for j in range(self.data.nbJobs):
            model += penal[j] >= self.Qjmin[j] - Qj[j] 
            model += penal[j] >= 0
            model += penal[j] <= 1
        # Fonction objectif 
        for j in range(self.data.nbJobs):
            model += Cmax >= t_ij[j][self.data.nbOperationsParJob[j]-1] + xsum(x_ijkn[n][k][j][self.data.nbOperationsParJob[j]-1] * self.data.dureeOperations[k][j][self.data.nbOperationsParJob[j]-1] 
                                                                    for n in range(self.n_max) 
                                                                    for k in range(self.data.nbMachines))
        model += Mmax == xsum(y_kln[n][k][l] for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k]))
        model += TotPena == xsum(penal[j] for j in range(self.data.nbJobs))
        model += avgoq ==  xsum((1-Qj[j]) for j in range(self.data.nbJobs))/self.data.nbJobs
        #model.objective = minimize(Cmax+Mmax)
        model.objective = minimize(self.wheights[0]*Cmax + self.wheights[1]*Mmax + self.wheights[2]*avgoq) #TotPena
        t0=time.perf_counter()
        model.optimize()
        cputime1=time.perf_counter()-t0
        optCmax1=Cmax.x
        #print("optCmax=",optCmax1)
        qualpenal1=sum(penal[j].x for j in range(self.data.nbJobs))
        #print("qualpenal=",qualpenal1)
        nbrmaint1=Mmax.x
        #print("nbrmaint=",nbrmaint1)

        #print("operations=",[j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])])
        #print("assign_machine=",[int(sum((1+k)*x_ijkn[n][k][j][i].x for n in range(self.n_max) for k in range(self.data.nbMachines))-1) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])])
        #print("starting times=",[t_ij[j][i].x for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])])
        
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                degradation_sumi = sum(prod_x_D[n][k][l][j][i].x * self.alpha_kl[k][l] 
                                       for n in range(self.n_max) 
                                       for k in range(self.data.nbMachines) 
                                       for l in range(self.data.nbComposants[k]))
                aa=[(k,n) for n in range(self.n_max) for k in range(self.data.nbMachines) if x_ijkn[n][k][j][i].x]
                bb=[D_kln[n][k][l].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k]) if x_ijkn[n][k][j][i].x]
                print(f"j={j} i={i} x={aa} D={bb} degradation_sum{i} {degradation_sumi}")
        
        #for k in range(self.data.nbMachines):
        #    for n in range(self.n_max):
                Dkln=[D_kln[n][k][l].x for l in range(self.data.nbComposants[k])]
                #dkln=[d_kln[n][k][l].x for l in range(self.data.nbComposants[k])]
                #print("degration components of M",k,":", Dkln, "Vs ", dkln, " egaux?=",Dkln==dkln)
        
        optsolution1 = [
            [j for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            [sum(k*int(x_ijkn[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])],
            #[[[max([(int(x_ijkn[n][k][j][i].x)*int(y_kln[n][k][l].x)) for n in range(self.n_max) for k in range(self.data.nbMachines)])  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))]
            [[[False  for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(max(self.data.nbComposants))],
            [[int(t_ij[j][i].x) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)],
            [sum(n*int(x_ijkn[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines)) for j in range(self.data.nbJobs) for i in range(self.data.nbOperationsParJob[j])]
        ]
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                mach=sum(k*int(x_ijkn[n][k][j][i].x) for n in range(self.n_max) for k in range(self.data.nbMachines))
                rank=sum(n*int(x_ijkn[n][mach][j][i].x) for n in range(self.n_max))
                maxdeg=max([D_kln[rank][mach][l].x for l in range(self.data.nbComposants[mach])] )
                stime=int(t_ij[j][i].x)
                ptime=sum([int(x_ijkn[n][k][j][i].x) * self.data.dureeOperations[k][j][i]  for n in range(self.n_max)  for k in range(self.data.nbMachines)])
                maintafter=False
                for l in range(self.data.nbComposants[mach]):
                    if y_kln[rank][mach][l].x:
                        maintafter=True
                        break
                #print("O_%d,%d : machine=%d  start=%d end=%d rank=%d max_machDeg=%.2f maintAfter=%s" % (j+1,i+1,mach+1,stime,stime+ptime,rank, maxdeg,maintafter))
                
        for k in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[k]):
                for j in range(self.data.nbJobs):
                    #temp=False
                    for i in range(self.data.nbOperationsParJob[j]):
                        for n in range(self.n_max):
                            temp=(x_ijkn[n][k][j][i].x and y_kln[n][k][l].x)
                            if temp==True:
                                optsolution1[2][l][j][i] =True
                                #print("break 1 -->", " on machine=",k+1 , "component =",l+1, " job ",j+1," operation ",i+1, " n=",n+1)
                                break
        avgoq1=sum((1-Qj[j].x) for j in range(self.data.nbJobs))/self.data.nbJobs
        #for k in range(self.data.nbMachines):
        #    print([["{:.2f}".format(D_kln[n][k][l].x) for l in range(self.data.nbComposants[k]) ] for n in range(self.n_max)])
        
        for j in range(self.data.nbJobs):
            plt.plot([Qji[j][i].x for i in range(self.data.nbOperationsParJob[j])])
            plt.title(f"Qj evolution of job {j}",fontsize=15)
            plt.show()
            print([Qji[j][i].x for i in range(self.data.nbOperationsParJob[j])])
            print([max(prod_x_D[n][k][l][j][i].x for n in range(self.n_max) for k in range(self.data.nbMachines) for l in range(self.data.nbComposants[k])) for i in range(self.data.nbOperationsParJob[j])])
        plt.plot([Qj[j].x for j in range(self.data.nbJobs)])
        plt.title(f"Qj of jobs",fontsize=15)
        plt.show()
        """
        for mach in range(self.data.nbMachines):
            for l in range(self.data.nbComposants[mach]):
                y0=[0]
                y=[0]
                for rank in range(self.n_max):
                    y0.append(y_kln[rank][mach][l].x)
                    y.append(D_kln[rank][mach][l].x)
                plt.plot(y)
                #plt.plot(y0)
            plt.show()
        """
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
    model.wheights = [0.0,0.0,1.0]
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
