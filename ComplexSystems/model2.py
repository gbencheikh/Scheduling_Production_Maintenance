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
    """
    A class to .
    
    Attributes:
    -----------
    data: object 
    represent scheduling and maintenance data for a production system
    """
    def __init__(self, n1, n2, n_max=3,wheights=[1.0,0.0,0.0]): 
        self.inf= 999999
        self.n_max = n_max
        self.wheights =wheights
        nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
        _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
        self.data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
        
        self.alpha_kl = [[.01 for l in range(nbComposants[k])] for k in range(self.data.nbMachines)]
        self.AQL = 0.8
        self.Qinitj = [1.0 for j in range(self.data.nbJobs)]  # Exemple de taux de qualité initiale
        self.Qjmin = [0.8 for j in range(self.data.nbJobs)]   # Exemple de taux de qualité minimale acceptable
        
    def solve(self):
        # variables :
        model = Model()
        maxComposants = max(self.data.nbComposants)
        Nj=self.data.nbJobs
        NM=self.data.nbMachines
        NOPj=[self.data.nbOperationsParJob[j] for j in range(Nj)]
        NOP=sum(NOPj)
        D_max = t_max = M = 999
        Cmax = model.add_var()
        Mmax = model.add_var()
        x_ikn    = [[[model.add_var(var_type=BINARY) for i in range(NOP)] for k in range(NM)] for n in range(self.n_max)]
        y_kln    = [[[model.add_var(var_type=BINARY) for l in range(self.data.nbComposants[k])] for k in range(NM)] for n in range(self.n_max)]
        v_kn     = [[model.add_var() for k in range(NM)] for n in range(self.n_max)]
        w        = [[[[model.add_var(var_type=BINARY) for i in range(NOP)] for i_ in range(NOP)] for m in range(NM)] for n in range(self.n_max)]
        z        = [[[[[model.add_var(var_type=BINARY) for i in range(NOP)] for i_ in range(NOP)] for l in range(maxComposants)] for k in range(NM)] for n in range(self.n_max)]
        d_kln    = [[[model.add_var() for l in range(self.data.nbComposants[k])] for k in range(NM)] for n in range(self.n_max)]
        prod_y_d = [[[model.add_var() for l in range(self.data.nbComposants[k])] for k in range(NM)] for n in range(self.n_max)]
        prod_w_t = [[[[model.add_var() for i in range(NOP)] for i_ in range(NOP)] for m in range(NM)] for n in range(self.n_max)]
        D_kln    = [[[model.add_var() for l in range(self.data.nbComposants[k])] for k in range(NM)] for n in range(self.n_max)]
        t_i      = [model.add_var() for i in range(NOP)]
        prod_x_D = [[[[model.add_var() for i in range(NOP)] for l in range(self.data.nbComposants[k])] for k in range(NM)] for n in range(self.n_max)]
        Qj       = [model.add_var()  for j in range(Nj)]
        prod_x_y = [[[[model.add_var(var_type=BINARY) for i in range(NOP)] for l in range(self.data.nbComposants[k])] for k in range(NM)] for n in range(self.n_max)]
        penal    = [model.add_var(var_type=BINARY)  for j in range(Nj)]
        # Contraintes : 
        # Calcul de la dégradation
        for n in range(self.n_max):
            for k in range(NM):
                for l in range(self.data.nbComposants[k]):
                    model += d_kln[n][k][l] == xsum(x_ikn[n][k][i+max(0,sum([NOPj[jj] for jj in range(j)]))] * self.data.degradations[k][l][j][i]
                                    for j in range(Nj)
                                    for i in range(NOPj[j]))
                
            for k in range(NM):
                    for l in range(self.data.nbComposants[k]):
                        model += D_kln[0][k][l] ==  d_kln[0][k][l]
            for n in range(self.n_max-1):
                for k in range(NM):
                    for l in range(self.data.nbComposants[k]):
                        model += D_kln[n+1][k][l] == D_kln[n][k][l] - prod_y_d[n][k][l] + d_kln[n+1][k][l]

            ## prod_y_d[n-1][k][l] = y_kln[n-1][k][l]*D_kln[n-1][k][l]
            for n in range(self.n_max):
                for k in range(NM):
                    for l in range(self.data.nbComposants[k]):
                        model += prod_y_d[n][k][l] >= 0
                        model += prod_y_d[n][k][l] - y_kln[n][k][l] * D_max <= 0
                        model += prod_y_d[n][k][l] - D_kln[n][k][l] <= 0
                        model += prod_y_d[n][k][l] - D_kln[n][k][l] + D_max - y_kln[n][k][l]*D_max >= 0

        #  Calcul de la déterioration de la qualité 
        for n in range(self.n_max):
            if n != 0:
                for k in range(NM) :
                    for l in range(self.data.nbComposants[k]) :
                        for i in range(NOP) :
                            model += prod_x_y[n][k][l][i] - x_ikn[n][k][i] + y_kln[n-1][k][l] >= 0
                            model += prod_x_y[n][k][l][i] - (1/2)*x_ikn[n][k][i] + (1/2)*y_kln[n-1][k][l] <= (1/2)
        for n in range(self.n_max):
            if n != 0:
                for k in range(NM):
                    for l in range(self.data.nbComposants[k]):
                        for i in range(NOP):
                            model += prod_x_D[n][k][l][i] >= 0
                            model += prod_x_D[n][k][l][i] - D_max * prod_x_y[n][k][l][i] <= 0
                            model += prod_x_D[n][k][l][i] - D_kln[n-1][k][l] <= 0
                            model += prod_x_D[n][k][l][i] - D_kln[n-1][k][l] + D_max - prod_x_y[n][k][l][i]*D_max >= 0
            else:
                for k in range(NM):
                    for l in range(self.data.nbComposants[k]):
                        for i in range(NOP):
                            model += prod_x_D[n][k][l][i] == 0

        for j in range(Nj):
            ifirst=max(0,sum([NOPj[j_] for j_ in range(j)]))
            ilast=sum([NOPj[j_] for j_ in range(j+1)])
            degradation_sum = xsum(prod_x_D[n][k][l][i]  * self.alpha_kl[k][l] 
                                for i in range(ifirst,ilast) 
                                for n in range(self.n_max) 
                                for k in range(NM) 
                                for l in range(self.data.nbComposants[k]))
            model += Qj[j] == self.Qinitj[j] - degradation_sum


        ## CALCUL DE LA VARIABLE y
        for n in range(self.n_max):
            for k in range(NM):
                for l in range(self.data.nbComposants[k]):
                    model += M*y_kln[n][k][l] - D_kln[n][k][l] + self.data.seuils_degradation[k][l]>= 0
                    model += y_kln[n][k][l] - M*D_kln[n][k][l]<= 0

        ## CALCUL DE LA VARIABLE v
        for n in range(self.n_max):
            for k in range(NM):
                model += v_kn[n][k] == xsum(x_ikn[n][k][i]  for i in range(NOP))

        ## CALCUL DE LA VARIABLE w
        for n in range(self.n_max-1):
            for k in range(NM):
                for i_ in range(NOP):
                    for i in range(NOP):
                        if i!=i_:
                            model +=   w[n][k][i_][i] - x_ikn[n][k][i_] - x_ikn[n+1][k][i] >= -1
                            model += 2*w[n][k][i_][i] - x_ikn[n][k][i_] - x_ikn[n+1][k][i] <= 0

        ## CALCUL DE LA VARIABLE z
        for n in range(self.n_max-1):
            for k in range(NM):
                for i_ in range(NOP):
                    for i in range(NOP):
                        for l in range(self.data.nbComposants[k]):
                            #model +=  z[n][k][l][j_][i_][j][i] - w[n][k][j_][i_][j][i] - y_kln[n][k][l] >= -1
                            #model +=  z[n][k][l][j_][i_][j][i] - 0.5*w[n][k][j_][i_][j][i] - 0.5*y_kln[n][k][l] <= 0
                            model +=    z[n][k][l][i_][i] - x_ikn[n][k][i_] - x_ikn[n+1][k][i] - y_kln[n][k][l] >= -2
                            model +=  3*z[n][k][l][i_][i] - x_ikn[n][k][i_] - x_ikn[n+1][k][i] - y_kln[n][k][l] <= 0

        ## LINEARISATION DE w ET DE tij
        for n in range(self.n_max):
            for k in range(NM):
                for i_ in range(NOP):
                    for i in range(NOP):
                        model += prod_w_t[n][k][i_][i] >= 0
                        model += prod_w_t[n][k][i_][i] - w[n][k][i_][i] * t_max <= 0
                        model += prod_w_t[n][k][i_][i] - t_i[i_] <= 0
                        model += prod_w_t[n][k][i_][i] - t_i[i_] + t_max - w[n][k][i_][i]*t_max >= 0

        ## CONTRAINTES DE PRECEDENCE DES OPERATIONS
        """for i in range(NOP - 1):
            jj=sum([sum([NOPj[jj] for jj in range(j)])<=i for j in range(Nj)])-1
            ii=i-sum([NOPj[jjj]  for jjj in range(sum([sum([NOPj[jj] for jj in range(j)])<=i for j in range(Nj)])-1)])
            model += t_i[i+1] >= t_i[i] + xsum(x_ikn[n][k][i] * self.data.dureeOperations[k][jj][ii]
                                                            for n in range(self.n_max)
                                                            for k in range(NM))
        """
        for j in range(self.data.nbJobs):
            for i in range(self.data.nbOperationsParJob[j] - 1):
                ii=i+sum([NOPj[j_] for j_ in range(j)])
                model += t_i[ii+1] >= t_i[ii] + xsum(x_ikn[n][k][ii] * self.data.dureeOperations[k][j][i]
                                                            for n in range(self.n_max)
                                                            for k in range(self.data.nbMachines))
        
        ## CONTRAINTES DE NON CHEVAUVHEMENT DES OPERATIONS SUR LES MACHINES
        for l in range(maxComposants):
            for i in range(NOP):
                model += t_i[i] >=  xsum(prod_w_t[n][k][i_][i] + w[n][k][i_][i] * self.data.dureeOperations[k][sum([sum([NOPj[jj] for jj in range(j)])<=i_ for j in range(Nj)])-1][i_-sum([NOPj[jjj]  for jjj in range(sum([sum([NOPj[jj] for jj in range(j)])<=i_ for j in range(Nj)])-1)])] +  z[n][k][l][i_][i] * self.data.dureeMaintenances[k][l]
                                                for n in range(self.n_max)
                                                for k in range(NM)
                                                for i_ in range(NOP))

        ## CONTRAINTES POUR IMPOSER QUE CHAQUE OPERATION SOIT ORDONNANCEE
        for i in range(NOP):
            model += xsum(x_ikn[n][k][i] for n in range(self.n_max) for k in range(NM)) == 1

        ## CONTRAINTES SUR LES INDCES n DES OPERATIONS DES MACHINES
        for k in range(NM):
            for n in range(self.n_max-1):
                model += v_kn[n][k] >= v_kn[n+1][k]
                model += v_kn[n][k] <= 1

        ## CONTRAINTES DE QUALITE
        #for j in range(Nj):
        #    model +=  xsum((1-Qj[j]) for j in range(Nj))/Nj <= self.AQL

        for j in range(Nj):
            model += penal[j] >= self.Qjmin[j] - Qj[j] 


        # Fonction objectif 
        for j in range(Nj):
            i=sum([NOPj[j_] for j_ in range(j+1)])-1
            model += Cmax >= t_i[i] + xsum(x_ikn[n][k][i] * self.data.dureeOperations[k][j][NOPj[j]-1] 
                                                                    for n in range(self.n_max) 
                                                                    for k in range(NM))
            
        model += Mmax == xsum(y_kln[n][k][l] for n in range(self.n_max) 
                            for k in range(NM) 
                            for l in range(self.data.nbComposants[k]))
  
        model.objective = minimize(Cmax)#self.wheights[0]*Cmax + self.wheights[1]*Mmax + self.wheights[2]*xsum(penal[j] for j in range(Nj)))
        t0=time.perf_counter()
        model.optimize()
        cputime1=time.perf_counter()-t0
        optCmax1=Cmax.x
        print("optCmax=",optCmax1)
        qualpenal1=sum(penal[j].x for j in range(Nj))
        print("qualpenal=",qualpenal1)
        nbrmaint1=Mmax.x
        print("nbrmaint=",nbrmaint1)

        print("operations=",[j for j in range(Nj) for i in range(NOPj[j])])
        print("assign_machine=",[int(sum((1+k)*x_ikn[n][k][i].x for n in range(self.n_max) for k in range(NM))-1) for i in range(NOP)])
        print("starting times=",[t_i[i].x for i in range(NOP)])
               
        optsolution1 = [
            [j for j in range(Nj) for i in range(NOPj[j])],
            [sum(k*int(x_ikn[n][k][i+sum([NOPj[jj] for jj in range(j)])].x) for n in range(self.n_max) for k in range(NM)) for j in range(Nj) for i in range(NOPj[j])],
            #[[[max([(int(x_ikn[n][k][j][i].x)*int(y_kln[n][k][l].x)) for n in range(self.n_max) for k in range(NM)])  for i in range(NOPj[j])] for j in range(Nj)] for l in range(max(self.data.nbComposants))]
            [[[0  for i in range(NOPj[j])] for j in range(Nj)] for l in range(max(self.data.nbComposants))],
            [[int(t_i[i+sum([NOPj[jj] for jj in range(j)])].x) for i in range(NOPj[j])] for j in range(Nj)]
        ]
        
        for j in range(Nj):
            for i in range(NOPj[j]):
                temp=False
                for n in range(self.n_max):
                    for k in range(NM):
                        for l in range(self.data.nbComposants[k]):
                            temp=temp or (x_ikn[n][k][i+sum([NOPj[jj] for jj in range(j)])].x and y_kln[n][k][l].x)
                    optsolution1[2][l][j][i]=int(temp)
        avgoq1=sum((1-Qj[j].x) for j in range(Nj))/Nj
        print("optsolution1=",optsolution1)
        return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1

if __name__ == "__main__": 
    n1=1
    n2=1
    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
    
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")
    data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    print(repr(data))
    alphakl=0.0    # quality degradation rate
    betakl=0.0         # average degradation rate of componenets 
    std_betakl=0.0     # standard deviation of degradation rate of componenets
    qjmin=0.0          # acceptable quality level triggering quality penality ()
    lambdakl=0.0       # degradation threshold triggering PdM 
    data.alpha_kl = [[alphakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    x=float(np.round(max(0,np.random.normal(betakl, std_betakl, 1)[0]),3))
    print(x)
    data.degradations=[[[[x  for ido in range(data.nbOperationsParJob[j])]  for j in range(data.nbJobs) ] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    data.Qjmin = [qjmin for j in range(data.nbJobs)] 
    #print(data.seuils_degradation)  
    data.seuils_degradation = [[lambdakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)] 

    model = FJSP_Maintenance_Quality_complex_systems__model(n1, n2)
    model.wheights=[1.0,0.0,0.0]
    model.n_max=3
    model.Qinitj = [1.0 for j in range(model.data.nbJobs)]  # Exemple de taux de qualité initiale
    model.Qjmin = [0.0 for j in range(model.data.nbJobs)]   # Exemple de taux de qualité minimale acceptable
    model.alpha_kl = [[alphakl for l in range(model.data.nbComposants[k])] for k in range(model.data.nbMachines)]  # Exemple de coefficients de détérioration de la qualité   
    model.AQL=0.0
    
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=model.solve()
    print("optsolution1=",optsolution1)
    k=1
    save_JSON(data,optsolution1,f"Results/MILPtestk{n1}inst{n2}_{k}.json",model.wheights)
    result = lire_fichier_json(f"Results/MILPtestk{n1}inst{n2}_{k}.json")
    plotGantt(result, f"Results/Gantts/MILPtestk{n1}inst{n2}_figure_{k}",f"k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showgantt=True)
    print("obj1=", optCmax1, "CPUTime=",cputime1)               

def Run_solver(data,n1,n2):
    model = FJSP_Maintenance_Quality_complex_systems__model(n1, n2)
    model.data=data
    optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=model.solve()
    return optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1
