from fonctions.CommonFunctions import parse_degradations_file, parse_operations_file
from fonctions.colors import couleurMachines

# from my_module import create_gantt_chart
from mip import Model, xsum, maximize, minimize, BINARY
import numpy as np
import matplotlib.pyplot as plt
import json

inf= 999999
filename = 'k1'
instance = 'instance11'
nbJobs, nbMachines, nbOperationsParJob, dureeOperations = parse_operations_file(f"../TESTS/{filename}/{filename}.txt")
_, _, nbComposants, seuils_degradation, dureeMaintenances, degradations = parse_degradations_file(f"../TESTS/{filename}/{instance}/instance.txt")

alpha_kl = [[.01 for l in range(nbComposants[k])] for k in range(nbMachines)]
Qjmin = [0.8 for j in range(nbJobs)]
