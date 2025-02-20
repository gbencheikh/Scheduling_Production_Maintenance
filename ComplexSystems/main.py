from RecuitSimuleCS import *
from fonctions.data import Data
from fonctions.CommonFunctions import *

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 
from fonctions.diagram import *
from fonctions.Save_Read_JSON import *

import numpy as np
import pandas as pd

lambdaPM = [0.8]
mu = [0]
PM_time = [0]

n1=1 #numero d'instance Kacem
n2=1 #numero d'instance machine
nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k{n1}/k{n1}.txt")
_, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k{n1}/instance{n2}/instance.txt")

data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
print(repr(data))
rscs=RSCS(data)

tempInit=100
tempFin=0
coolRate=0.99
iters=30000
ResTest=[]
weights=[1.0,0.0,0.0]#0.7,0.2,0.1]
ResTest=[]
ALPHAKLs=[0.0]#,0.005,0.01, 0.05, 0.1, 1] # quality degradation rate
BETAKLs=[0.0]#, 0.005, 0.01, 0.05, 0.1,1] # degradation rate 
std_betakl=0.01
LAMBDAKLs=[0.0]#0.85,0.9,0.95,1]  # degradation threshold triggering PdM 
QJMINs=[0.0]#0.85,0.9,0.95,1] # acceptable quality level triggering quality penality ()

print("alphakl=",data.alpha_kl)
print("seuils=",data.seuils_degradation) 
print("degradation=",data.degradations)
print("degradations2=",data.degradations2)
print("AQL=",data.Qjmin)

y=True
if y: 
    kmax=len(QJMINs)+len(ALPHAKLs)*len(BETAKLs)*len(LAMBDAKLs)*len(QJMINs)
    k=0
    ResTest.append(["alphakl","Lambdakl","betakl","AQL","weights[0]","weights[1]","weights[2]","RSCmax", "RSnbrmaint", "RSavgoq","RSqualpenal","RScputime","MILPoptCmax", "MILPnbrmaint", "MILPavgoq","MILPqualpenal","MILPcputime"])
    """for qjmin in QJMINs:
        k+=1
        optsolution, optCmax, cputime,nbrmaint,avgoq,qualpenal=rscs.Run_RSCS(tempInit,tempFin,coolRate,iters,weights,False)
        save_JSON(data,optsolution,f"Results/testk{n1}inst{n2}.json",weights)
        result = lire_fichier_json(f"Results/testk{n1}inst{n2}.json")
        plotGantt(result, f"Results/Gantts/testk{n1}inst{n2}_figure_{k}",f"k{n1}inst{n2}-alpha0-lambdakl0-beta0-AQL{qjmin}", showgantt=False)
        #print([weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq, qualpenal,cputime])
        ResTest.append(["alpha0","lambdakl0","beta0",qjmin,weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq,qualpenal,cputime])
        print( f"{k}/{kmax} - \t alphak=alpha0 \t lambdakl=lambdakl0 \t beta=beta0 \t AQL={qjmin} \t optCmax={optCmax} \t nbrmaint={nbrmaint} \t avgoq={avgoq:.2f} \t qualpenal={qualpenal} \t cputime={cputime:.2f}")
    """
    for alphakl in ALPHAKLs: # quality degradation rate
        for qjmin in QJMINs: # acceptable quality level triggering quality penality ()
            for betakl in BETAKLs: # degradation rate
                for lambdakl in LAMBDAKLs: # degradation threshold triggering PdM
                    k+=1
                    data.alpha_kl = [[alphakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
                    x=float(np.round(max(0,np.random.normal(betakl, std_betakl, 1)[0]),3))
                    print(x)
                    data.degradations=[[[[x  for ido in range(data.nbOperationsParJob[j])]  for j in range(data.nbJobs) ] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
                    data.Qjmin = [qjmin for j in range(data.nbJobs)] 
                    #print(data.seuils_degradation)  
                    data.seuils_degradation = [[lambdakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)] 
                    #print(data.seuils_degradation)
                    optsolution, optCmax, cputime,nbrmaint,avgoq,qualpenal=rscs.Run_RSCS(tempInit,tempFin,coolRate,iters,weights,False)
                    save_JSON(data,optsolution,f"Results/RStestk{n1}inst{n2}_{k}.json",weights)
                    result = lire_fichier_json(f"Results/RStestk{n1}inst{n2}_{k}.json")
                    plotGantt(result, f"Results/Gantts/RStestk{n1}inst{n2}_figure_{k}",f"k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showgantt=True)
                    
                    """optsolution1, optCmax1, cputime1,nbrmaint1,avgoq1,qualpenal1=Run_solver(data,)
                    save_JSON(data,optsolution1,f"Results/MILPtestk{n1}inst{n2}_{k}.json",weights)
                    result = lire_fichier_json(f"Results/MILPtestk{n1}inst{n2}_{k}.json")
                    plotGantt(result, f"Results/Gantts/MILPtestk{n1}inst{n2}_figure_{k}",f"k{n1}inst{n2}-alpha{alphakl}-lambda{lambdakl}-beta{betakl}-AQL{qjmin}", showgantt=False)
                    
                    ResTest.append([alphakl,lambdakl,betakl,qjmin,weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq,qualpenal,cputime,optCmax1, nbrmaint1, avgoq1,qualpenal1,cputime1])
                    print( f"{k}/{kmax} - \t alphak={alphakl} \t lambdakl={lambdakl} \t betakl={betakl} \t AQL={qjmin} \t optCmax={optCmax} \t nbrmaint={nbrmaint} \t avgoq={avgoq:.2f} \t qualpenal={qualpenal} \t cputime={cputime:.2f}")
                    """
    df=pd.DataFrame(ResTest)
    df.to_excel(f"Results/ResOptWeightsk{n1}inst{n2}.xlsx", index=False, header=False)