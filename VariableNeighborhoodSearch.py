from utils import data
from utils import diagram
from utils import commun_functions
import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 

class VNS: 
    def __init__(self, kmax, maxTime, instance): 
         self.kmax = kmax
         self.maxTime = maxTime 
         self.instance = instance 

    def BestVoisin(self, x):
        best_voisin = x[0]
        bestCmax = commun_functions.evaluate(x[0], self.instance)[2]
        for _,v in enumerate(x):
            cmax = commun_functions.evaluate(v, self.instance)[2]
            if cmax < bestCmax:
                bestCmax = cmax 
                bestSol = v
        return best_voisin, bestCmax

    def ChangeVoisinage(self, x1, x2, k, nbrV):
        cmax1 = commun_functions.evaluate(x1)[2]
        cmax2 = commun_functions.evaluate(x2)[2]
        if cmax1 < cmax2:
            x1=x2
            k=1
            if nbrV>2:
                nbrV=nbrV-1
        else:
            k=k+1
            if nbrV<10: 
                nbrV=nbrV+1
        return x1,k,nbrV
    
    def BasicVNS(self):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < self.maxTime:
            k=1
            nbrV=1
            current_solution = commun_functions.GenererSolution(self.instance)   # Générer une solution aléatoire 
            while k < self.kmax:
                voisins = commun_functions.Voisinage(current_solution,k,nbrV,self.instance)        # Générer le voisinage de la solution  
                xx=[]
                for _,ii in enumerate(voisins):
                    xx.append(ii)
                best_neighbor, cmax2 = self.BestVoisin(xx)
                cmax_1 = commun_functions.evaluate(current_solution, self.instance)[2]
                cmax_2 = commun_functions.evaluate(best_neighbor, self.instance)[2]
                if cmax_2 < cmax_1:
                    current_solution = best_neighbor
                    k=1
                    if nbrV>2:
                        nbrV=nbrV-1
                else:
                    k=k+1
                    if nbrV<10: 
                        nbrV=nbrV+1
        return current_solution    
    
instancefilename='Instances/Kacem1.fjs'
ptimes=commun_functions.FJSInstanceReading(instancefilename)

data_instance = data.data()
data_instance.procTime(ptimes)

LargVmax = sum([1  for jid,job in enumerate(data_instance.ProcTime) for opid,op in enumerate(job) if len(op)>1])

kmax = LargVmax/2
maxTime = 30

VNS_instance = VNS(kmax,maxTime, data_instance)
best_solution = VNS_instance.BasicVNS()  
NM,NJ,cmax,schedule,maint,ehf = commun_functions.evaluate(best_solution,data_instance)

print("Schedule=", schedule)

fileName = f"results/simulation_{time.strftime('%H%M%S')}_{int(time.time())}.jpg"

Gantt = diagram.diagram(NM,NJ,data_instance.ProcTime,data_instance.mu,cmax,schedule,maint,ehf,fileName)

print(f"Production scedhuling: {schedule}")
print(f"Maintenance scedhuling: {maint}")

Gantt.plotEHF()
Gantt.plotGantt()

# Charger les images enregistrées
image_gantt = Image.open(Gantt.ganttsavefilename)
image_ehf = Image.open(Gantt.ehfplotsavefilename)

# Afficher les deux images dans une seule fenêtre
fig, ax = plt.subplots(1, 2, figsize=(10, 5))

ax[0].imshow(image_gantt)
ax[0].axis('off')
ax[0].set_title('Gantt Chart')

ax[1].imshow(image_ehf)
ax[1].axis('off')
ax[1].set_title('EHF Chart')

plt.show()