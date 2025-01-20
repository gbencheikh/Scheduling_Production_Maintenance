import numpy as np
import pandas as pd
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



# Define the L25 orthogonal array (25 rows, 3 columns for parameters)
l25_array = [
    [1, 1, 1],
    [1, 2, 2],
    [1, 3, 3],
    [1, 4, 4],
    [1, 5, 5],
    [2, 1, 2],
    [2, 2, 3],
    [2, 3, 4],
    [2, 4, 5],
    [2, 5, 1],
    [3, 1, 3],
    [3, 2, 4],
    [3, 3, 5],
    [3, 4, 1],
    [3, 5, 2],
    [4, 1, 4],
    [4, 2, 5],
    [4, 3, 1],
    [4, 4, 2],
    [4, 5, 3],
    [5, 1, 5],
    [5, 2, 1],
    [5, 3, 2],
    [5, 4, 3],
    [5, 5, 4]
]

# Convert to a Pandas DataFrame for better visualization
columns = ['Parameter 1', 'Parameter 2', 'Parameter 3']
df = pd.DataFrame(l25_array, columns=columns)

# Display the array
#print(df)

# Example: Assign specific levels to each parameter (optional)
parameter_1_levels = [0.1, 0.2, 0.5, 0.8, 0.9]
parameter_2_levels = parameter_1_levels
parameter_3_levels = parameter_1_levels

# Map numerical levels to actual values
df['Parameter 1'] = df['Parameter 1'].map(lambda x: parameter_1_levels[x-1])
df['Parameter 2'] = df['Parameter 2'].map(lambda x: parameter_2_levels[x-1])
df['Parameter 3'] = df['Parameter 3'].map(lambda x: parameter_3_levels[x-1])


# Normalize rows to sum to C
row_sums = df.sum(axis=1).values.reshape(-1, 1)
df1=round(df / row_sums,1)
df2=pd.DataFrame(df1.drop_duplicates().values, columns=columns)

# Display the mapped DataFrame
print("\nL25 Orthogonal Array with Mapped Levels:")
#print(df)
print(df2)



lambdaPM = [0.8]
mu = [0]
PM_time = [0]

nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"TESTS/k2/k2.txt")
_, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"TESTS/k2/instance01/instance.txt")


data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
#print(repr(data))


tempInit=100
tempFin=0
coolRate=0.99
iters=30000
ResTest=[]
print(len(df2))
print(df2)

rscs=RSCS(data)
for alphakl in [0.001,0.005,0.01]:
    for qjmin in [0.85,0.9,0.95]:
        data.alpha_kl = [[alphakl for l in range(data.nbComposants[k])] for k in range(data.nbMachines)]
        data.Qjmin = [qjmin for j in range(data.nbJobs)]
        for i in range(len(df2)):
            #print([df2['Parameter 1'][i],df2['Parameter 2'][i],df2['Parameter 3'][i]])
            weights=[df2['Parameter 1'][i],df2['Parameter 2'][i],df2['Parameter 3'][i]]
            optsolution, optCmax, cputime,nbrmaint,avgoq,qualpenal=rscs.Run_RSCS(tempInit,tempFin,coolRate,iters,weights,True)
            save_JSON(data,optsolution,"testk2inst1.json",weights)
            result = lire_fichier_json(f"testk2inst1.json")
            plotGantt(result, "testk2inst1_figure", showgantt=False)
            print([df2['Parameter 1'][i],df2['Parameter 2'][i],df2['Parameter 3'][i],optCmax, nbrmaint, avgoq, qualpenal,cputime])
            ResTest.append([alphakl,qjmin,df2['Parameter 1'][i],df2['Parameter 2'][i],df2['Parameter 3'][i],optCmax, nbrmaint, avgoq,qualpenal,cputime])
df=pd.DataFrame(ResTest)
df.to_excel('ResPlanExp.xlsx', index=False, header=False)