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
#print(repr(data))
rscs=RSCS(data)

tempInit=100
tempFin=0
coolRate=0.99
iters=30000
ResTest=[]
weights=[0.7,0.2,0.1]
ResTest=[]

for qjmin in [0.85,0.9,0.95]:
    optsolution, optCmax, cputime,nbrmaint,avgoq,qualpenal=rscs.Run_RSCS(tempInit,tempFin,coolRate,iters,weights,False)
    save_JSON(data,optsolution,f"Results/testk{n1}inst{n2}.json",weights)
    result = lire_fichier_json(f"Results/testk{n1}inst{n2}.json")
    plotGantt(result, f"Results/testk{n1}inst{n2}_figure",f"k{n1}inst{n2}-alpha0-AQL{qjmin}", showgantt=False)
    print([weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq, qualpenal,cputime])
    ResTest.append(["Nan",qjmin,"Nan","Nan",weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq,qualpenal,cputime])

for alphakl in [0.00,0.005,0.01]:
    for qjmin in [0.85,0.9,0.95]:
        for betakl in [0.0, 0.005, 0.01]:
            for lambdakl in [0.85,0.9,0.95,1]:
                print(f"alphak={alphakl} qjmin={qjmin} lambdakl={lambdakl}")
                data.alpha_kl = [[alphakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
                data.degradations=[[[[betakl  for ido in range(data.nbOperationsParJob[j])]  for j in range(data.nbJobs) ] for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
                data.Qjmin = [qjmin for j in range(data.nbJobs)]    
                data.seuils_degradation = [[lambdakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]    
                optsolution, optCmax, cputime,nbrmaint,avgoq,qualpenal=rscs.Run_RSCS(tempInit,tempFin,coolRate,iters,weights,False)
                save_JSON(data,optsolution,f"Results/testk{n1}inst{n2}.json",weights)
                result = lire_fichier_json(f"Results/testk{n1}inst{n2}.json")
                plotGantt(result, f"Results/testk{n1}inst{n2}_figure",f"k{n1}inst{n2}-alpha{alphakl}-AQL{qjmin}", showgantt=False)
                print([weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq, qualpenal,cputime])
                ResTest.append([alphakl,qjmin,betakl,lambdakl,weights[0],weights[1],weights[2],optCmax, nbrmaint, avgoq,qualpenal,cputime])
df=pd.DataFrame(ResTest)
df.to_excel(f"Results/ResOptWeightsk{n1}inst{n2}.xlsx", index=False, header=False)