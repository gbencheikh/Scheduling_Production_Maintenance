from fonctions.CommonFunctions import parse_degradations_file, parse_operations_file
from fonctions.colors import couleurMachines
from fonctions.data import Data

# from my_module import create_gantt_chart
from mip import Model, xsum, maximize, minimize, BINARY
import numpy as np
import matplotlib.pyplot as plt
import json

class FJSP_Maintenance_Quality_complex_systems__model:
    """
    A class to .
    
    Attributes:
    -----------
    data: object 
    represent scheduling and maintenance data for a production system
    """
    def __init__(self, instancename, num_instance, n_max=3): 
        self.inf= 999999
        self.instancename = instancename
        self.n_max = n_max
        self.num_instance = num_instance
        
        nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"ComplexSystems/TESTS/{instancename}/{instancename}.txt")
        _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"ComplexSystems/TESTS/{instancename}/{num_instance}/instance.txt")
        self.data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
        
        self.alpha_kl = [[.01 for l in range(nbComposants[k])] for k in range(self.data.nbMachines)]
        self.AQL = 0.05
        self.Qjmin = [0.8 for j in range(self.data.nbJobs)]


    def solve(self):
        # variables :
        model = Model()
        maxComposants = max(self.data.nbComposants)
        D_max = t_max = M = 999
        Cmax = model.add_var()
        Mmax = model.add_var()
        x_ijkn = [[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        y_kln = [[[model.add_var(var_type=BINARY) for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        v_kn= [[model.add_var() for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        w = [[[[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for i_ in range(self.data.nbOperationsParJob[j_])] for j_ in range(self.data.nbJobs)] for m in range(self.data.nbMachines)] for n in range(self.n_max)]
        z = [[[[[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for i_ in range(self.data.nbOperationsParJob[j_])] for j_ in range(self.data.nbJobs)] for l in range(maxComposants)] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        d_kln = [[[model.add_var() for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        prod_y_d = [[[model.add_var() for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        prod_w_t = [[[[[[model.add_var() for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for i_ in range(self.data.nbOperationsParJob[j_])] for j_ in range(self.data.nbJobs)] for m in range(self.data.nbMachines)] for n in range(self.n_max)]
        D_kln = [[[model.add_var() for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        t_ij = [[model.add_var() for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)]
        Qinitj = [1.0 for j in range(self.data.nbJobs)]  # Exemple de taux de qualité initiale
        Qjmin = [0.8 for j in range(self.data.nbJobs)]   # Exemple de taux de qualité minimale acceptable
        alpha_kl = [[.01 for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)]  # Exemple de coefficients de détérioration de la qualité   
        prod_x_D = [[[[[model.add_var() for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]
        Qj = [model.add_var()  for j in range(self.data.nbJobs)]
        prod_x_y = [[[[[model.add_var(var_type=BINARY) for i in range(self.data.nbOperationsParJob[j])] for j in range(self.data.nbJobs)] for l in range(self.data.nbComposants[k])] for k in range(self.data.nbMachines)] for n in range(self.n_max)]

        # Contraintes : 
        # Calcul de la dégradation
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    model += d_kln[n][k][l] == xsum(x_ijkn[n][k][j][i] * self.data.degradations[k][l][j][i]
                                    for j in range(self.data.nbJobs)
                                    for i in range(self.data.nbOperationsParJob[j]))
                
            for k in range(self.data.nbMachines):
                    for l in range(self.data.nbComposants[k]):
                        model += D_kln[0][k][l] ==  d_kln[0][k][l]
            for n in range(self.n_max-1):
                for k in range(self.data.nbMachines):
                    for l in range(self.data.nbComposants[k]):
                        model += D_kln[n+1][k][l] == D_kln[n][k][l] - prod_y_d[n][k][l] + d_kln[n+1][k][l]

            ## prod_y_d[n-1][k][l] = y_kln[n-1][k][l]*D_kln[n-1][k][l]
            for n in range(self.n_max):
                for k in range(self.data.nbMachines):
                    for l in range(self.data.nbComposants[k]):
                        model += prod_y_d[n][k][l] >= 0
                        model += prod_y_d[n][k][l] - y_kln[n][k][l] * D_max <= 0
                        model += prod_y_d[n][k][l] - D_kln[n][k][l] <= 0
                        model += prod_y_d[n][k][l] - D_kln[n][k][l] + D_max - y_kln[n][k][l]*D_max >= 0

        #  Calcul de la déterioration de la qualité 
        for n in range(self.n_max) :
            if n != 0:
                for k in range(self.data.nbMachines) :
                    for l in range(self.data.nbComposants[k]) :
                        for j in range(self.data.nbJobs) :
                            for i in range(self.data.nbOperationsParJob[j]) :
                                model += prod_x_y[n][k][l][j][i] - x_ijkn[n][k][j][i] + y_kln[n-1][k][l] >= 0
                                model += prod_x_y[n][k][l][j][i] - (1/2)*x_ijkn[n][k][j][i] + (1/2)*y_kln[n-1][k][l] <= (1/2)
        for n in range(self.n_max):
            if n != 0:
                for k in range(self.data.nbMachines):
                    for l in range(self.data.nbComposants[k]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                model += prod_x_D[n][k][l][j][i] >= 0
                                model += prod_x_D[n][k][l][j][i] - D_max * prod_x_y[n][k][l][j][i] <= 0
                                model += prod_x_D[n][k][l][j][i] - D_kln[n-1][k][l] <= 0
                                model += prod_x_D[n][k][l][j][i] - D_kln[n-1][k][l] + D_max - prod_x_y[n][k][l][j][i]*D_max >= 0
            else:
                for k in range(self.data.nbMachines):
                    for l in range(self.data.nbComposants[k]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                model += prod_x_D[n][k][l][j][i] == 0

        for j in range(self.data.nbJobs):
            degradation_sum = xsum(prod_x_D[n][k][l][j][i]  * alpha_kl[k][l] 
                                for i in range(self.data.nbOperationsParJob[j]) 
                                for n in range(self.n_max) 
                                for k in range(self.data.nbMachines) 
                                for l in range(self.data.nbComposants[k]))
            model += Qj[j] == Qinitj[j] - degradation_sum


        ## CALCUL DE LA VARIABLE y
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for l in range(self.data.nbComposants[k]):
                    model += M*y_kln[n][k][l] - D_kln[n][k][l] + self.data.seuils_degradation[k][l]>= 0

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
                                model += w[n][k][j_][i_][j][i] - x_ijkn[n][k][j][i] - x_ijkn[n+1][k][j_][i_] >= -1
                                model += w[n][k][j_][i_][j][i] - 0.5*x_ijkn[n][k][j][i] - 0.5*x_ijkn[n+1][k][j_][i_] <= 0

        ## CALCUL DE LA VARIABLE z
        for n in range(self.n_max-1):
            for k in range(self.data.nbMachines):
                for j_ in range(self.data.nbJobs):
                    for i_ in range(self.data.nbOperationsParJob[j_]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                for l in range(self.data.nbComposants[k]):
                                    model +=  z[n][k][l][j_][i_][j][i] - w[n][k][j_][i_][j][i] - y_kln[n][k][l] >= -1
                                    model +=  z[n][k][l][j_][i_][j][i] - 0.5*w[n][k][j_][i_][j][i] - 0.5*y_kln[n][k][l] <= 0

        ## LINEARISATION DE w ET DE tij
        for n in range(self.n_max):
            for k in range(self.data.nbMachines):
                for j_ in range(self.data.nbJobs):
                    for i_ in range(self.data.nbOperationsParJob[j_]):
                        for j in range(self.data.nbJobs):
                            for i in range(self.data.nbOperationsParJob[j]):
                                model += prod_w_t[n][k][j_][i_][j][i] >= 0
                                model += prod_w_t[n][k][j_][i_][j][i] - w[n][k][j_][i_][j][i] * t_max <= 0
                                model += prod_w_t[n][k][j_][i_][j][i] - t_ij[j][i] <= 0
                                model += prod_w_t[n][k][j_][i_][j][i] - t_ij[j][i] + t_max - w[n][k][j_][i_][j][i]*t_max >= 0

        ## CONTRAINTES DE PRECEDENCE DES OPERATIONS
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j] - 1):
                    model += t_ij[j][i+1] >= t_ij[j][i] + xsum(x_ijkn[n][k][j][i] * self.data.dureeOperations[k][j][i]
                                                            for n in range(self.n_max)
                                                            for k in range(self.data.nbMachines))

        ## CONTRAINTES DE NON CHEVAUVHEMENT DES OPERATIONS SUR LES MACHINES
        for l in range(maxComposants):
            for j_ in range(self.data.nbJobs):
                for i_ in range(self.data.nbOperationsParJob[j_]):
                    model += t_ij[j_][i_] >=  xsum(prod_w_t[n][k][j_][i_][j][i] + w[n][k][j_][i_][j][i] * self.data.dureeOperations[k][j][i] +  z[n][k][l][j_][i_][j][i] * self.data.dureeMaintenances[k][l]
                                                for n in range(self.n_max)
                                                for k in range(self.data.nbMachines)
                                                for j in range(self.data.nbJobs)
                                                for i in range(self.data.nbOperationsParJob[j]))

        ## CONTRAINTES POUR IMPOSER QUE CHAQUE OPERATION SOIT ORDONNANCEE
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j]):
                model += xsum(x_ijkn[n][k][j][i] for n in range(self.n_max) for k in range(self.data.nbMachines)) == 1

        ## CONTRAINTES SUR LES INDCES n DES OPERATIONS DES MACHINES
        for k in range(self.data.nbMachines):
            for n in range(self.n_max-1):
                model += v_kn[n][k] >= v_kn[n+1][k]
                model += v_kn[n][k] <= 1

        ## CONTRAINTES DE QUALITE
        for j in range(self.data.nbJobs):
            model +=  xsum((1-Qj[j]) for j in range(self.data.nbJobs))/self.data.nbJobs <= self.AQL

        # Fonction objectif 
        for j in range(self.data.nbJobs):
            model += Cmax >= t_ij[j][self.data.nbOperationsParJob[j]-1] + xsum(x_ijkn[n][k][j][self.data.nbOperationsParJob[j]-1] * self.data.dureeOperations[k][j][self.data.nbOperationsParJob[j]-1] 
                                                                    for n in range(self.n_max) 
                                                                    for k in range(self.data.nbMachines))

        model += Mmax >= xsum(y_kln[n][k][l] for n in range(self.n_max) 
                            for k in range(self.data.nbMachines) 
                            for l in range(self.data.nbComposants[k]))
  
        model.objective = minimize(0.9*Cmax + 0.1*Mmax)
        model.optimize()

if __name__ == "__main__": 
    model = FJSP_Maintenance_Quality_complex_systems__model(instancename='k1', num_instance='instance01')
    model.solve()