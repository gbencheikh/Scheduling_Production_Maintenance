from utils import data
from utils import diagram
from utils import commun_functions
from utils import data

import random
import math
import matplotlib.pyplot as plt
from PIL import Image
import time 

import gurobipy as gp
from gurobipy import GRB
import os
from pprint import pprint
import pandas as pd
import plotly.express as px
import numpy as np
from urllib.request import urlopen
import webbrowser
import logging 
from collections import Counter
#now we will Create and configure logger 
logging.basicConfig(filename="std.log", format='%(asctime)s %(message)s', filemode='w') 
logger=logging.getLogger() 
global colors

class GurSol:
    def __init__(self, instance):
        # Simulated Annealing parameters
        self.inst = instance
        self.prt = instance.ProcTime
        self.mu = instance.mu
        self.Lambda = instance.lambdaPM
        self.LambdaQ = instance.lambdaQ
        self.LambdaC = instance.lambdaC
        self.pmt = instance.PM_time
        self.cmt = instance.CM_time
         
    
    def SolveIPQM_FJSP(self,MAINT,QUAL,ShowGurobiConsole):
        PMT=self.pmt
        CMT=self.cmt
        LAMBDA=self.Lambda
        LAMBDAQ=self.LambdaQ
        LAMBDAC=self.LambdaC
        MU=self.mu
        PRT=self.prt
                
        #NJ=len(PRT)
        #NM=max[mo[0] for _,job in enumerate(PRT) for _,oper in enumerate(job) for _,mo in enumerate(oper)]
        NOP=[len(job) for _,job in enumerate(PRT)]
        NOPmax=max(NOP)
        
        RandomSol=random.shuffle([(jid,mo[0]) for jid,job in enumerate(PRT) for opid,op in enumerate(job) for mo in random.sample(op,1)])
        NM,NJ,cmax,schedule,maint,ehf=commun_functions.evaluate(RandomSol,self.inst)
        
        NP=cmax      
        T = range(1,NP+1)
        OP = range(NOPmax) 
        MACH = range(NM)
        J=range(NJ)
        M=range(NM)

        model=gp.Model(name="model")
        y   = model.addVars(NJ, NOPmax, NM,       vtype=GRB.BINARY, name="Y") 
        x   = model.addVars(NJ, NOPmax, NM, NP+1, vtype=GRB.BINARY, name="X") 
        z   = model.addVars(NM, NP+1,               vtype=GRB.BINARY, name="Z") 
        zz  = model.addVars(NM, NP+1,               vtype=GRB.BINARY, name="ZZ") 
        s   = model.addVars(NJ, NOPmax,           vtype=GRB.INTEGER,name="S")
        cmax= model.addVar (1,                      vtype=GRB.INTEGER, name="Cmax")
        oq  = model.addVars(NJ,                     vtype=GRB.CONTINUOUS, name="OQ") 

        delta = model.addVars(NM, NP+1,       vtype=GRB.CONTINUOUS, name="DELTA") 
        delta_= model.addVars(NM, NP+1,       vtype=GRB.CONTINUOUS, name="DELTAbis")
        gamma = model.addVars(NJ, NM,   NP+1, vtype=GRB.CONTINUOUS, name="GAMMA")
        gamma_= model.addVars(NJ, NM,   NP+1, vtype=GRB.CONTINUOUS, name="GAMMAbis")
        I     = model.addVars(NM, NP+1,       vtype=GRB.BINARY,     name="I")
        ooc   = model.addVars(NM, NP+1,       vtype=GRB.BINARY,     name="OC") 

        for (j,i) in [(j,i) for j in J for i in range(NOP[j])]:
            model.addConstr(cmax   >= s[j,i] + sum(PRT[j][i][m]*y[j,i,m] for m in M if PRT[j][i][m]>0),                   name=f'CST1[{j},{i}]')
            model.addConstr(s[j,i] >= 0,                                                                                  name=f'CST300[{j},{i}]')
            
        for (j,i,m,t) in [(j,i,m,t) for j in J for i in range(NOP[j]) for m in M for t in T if PRT[j][i][m]>0]:
            model.addConstr(s[j,i] >= (t-1)*x[j,i,m,t] - PRT[j][i][m]*y[j,i,m],                                           name=f'CST301[{j},{i},{m},{t}]')
            model.addConstr(s[j,i] >=     t*x[j,i,m,t] - PRT[j][i][m]*y[j,i,m] - \
                            sum(tt*x[j,i,m,tt] for tt in range(t+1,NP+1)),                                                name=f'CST302[{j},{i},{m},{t}]')
        
        for (j,i) in [(j,i) for j in J for i in range(NOP[j])]:
            model.addConstr(s[j,i] <= sum(t*x[j,i,m,t]/PRT[j][i][m] for m in M for t in T if PRT[j][i][m]>0) - \
                            sum(y[j,i,m]*tt/PRT[j][i][m] for m in M for tt in range(1,PRT[j][i][m]+1) if PRT[j][i][m]>0), name=f'CST31[{j},{i}]')
        
        for (j,i) in [(j,i) for j in J for i in range(NOP[j]-1)]:
            model.addConstr(s[j,i+1]-s[j,i] >= sum(PRT[j][i][m]*y[j,i,m] for m in M if PRT[j][i][m]>0),                   name=f'CST32[{j},{i}]')
        
        for (j,t) in [(j,t) for j in J for t in T]:
            model.addConstr(sum(x[j,i,m,t] for i in range(NOP[j]) for m in M if PRT[j][i][m]>0) <= 1,                     name=f'CST33[{j},{i}]')
        
        for (j,i) in [(j,i) for j in J for i in range(NOP[j])]:                             
            model.addConstr(sum(y[j,i,m] for m in M if PRT[j][i][m]>0) == 1 ,                                             name=f'CST41[{j},{i}]')
        
        for (j,i,m,t) in [(j,i,m,t) for j in J for i in range(NOP[j]) for m in M for t in T if t>0 and t<NP]:
            model.addConstr(PRT[j][i][m]*(x[j,i,m,t]-x[j,i,m,t+1]) + sum(x[j,i,m,r] for r in T if r>=t+1) <= PRT[j][i][m],name=f'CST5[{j},{i},{m},{t}]')
        
        for (j,i,m) in [(j,i,m) for j in J for i in range(NOP[j]) for m in M]:
            model.addConstr(y[j,i,m]<=1 ,                                                                                 name=f'CST60[{j},{i},{m}]')
            model.addConstr(y[j,i,m]<=PRT[j][i][m],                                                                       name=f'CST61[{j},{i},{m}]')                
        
        for (m,t) in [(m,t) for m in M for t in T]:
            #print("m=%d , t=%d" % (m,t))
            model.addConstr(sum(x[j,i,m,t] for j in J for i in range(NOP[j]))<=1 ,                                        name=f'CST7[{m},{t}]')
        
        for (j,i,m) in [(j,i,m) for j in J for i in range(NOP[j]) for m in M]:   
            model.addConstr(sum(x[j,i,m,t] for t in T)==y[j,i,m]*PRT[j][i][m],                                            name=f'CST81[{j},{i},{m}]')
        
        for (j,i,m,t) in [(j,i,m,t) for j in J for i in range(NOP[j]) for m in M for t in T]:
            model.addConstr(x[j,i,m,t] <= y[j,i,m],                                                                       name=f'CST82[{j},{i},{m},{t}]')
        
        for m in M:
            model.addConstr(delta[m,0]  == 0,                                                                             name=f'CST900[{m}]')
            model.addConstr(delta_[m,0]  == 0,                                                                            name=f'CST901[{m}]')                
        
        for (m,t) in [(m,t) for m in M for t in T]:
            model.addConstr(delta[m,t]  == delta_[m,t] + sum(MU[m]*x[j,i,m,t] for j in J for i in range(NOP[j])),         name=f'CST91[{m},{t}]')                

        if MAINT==0:
            for (m,t) in [(m,t) for m in M for t in T]:
                model.addConstr(delta_[m,t] == delta[m,t-1] ,                                                             name=f'CST94[{m},{t}]')
                model.addConstr(z[m,t] == 0,                                                                              name=f'CST95[{m},{t}]')
            obj   = model.setObjective(cmax, gp.GRB.MINIMIZE)
        else:
            for (m,t) in [(m,t) for m in M for t in T  if t>=1]:
                model.addConstr(delta_[m,t] <= (1 - z[m,t-1])*(LAMBDA[m]+1),                                              name=f'CST93[{m},{t}]') 
                model.addConstr(delta_[m,t] >= delta[m,t-1] - z[m,t]*(LAMBDA[m]+1),                                       name=f'CST94[{m},{t}]')
                model.addConstr(delta_[m,t] <= delta[m,t-1] ,                                                             name=f'CST942[{m},{t}]')
            
            for (j,i,m,t) in [(j,i,m,t) for j in J for i in range(NOP[j]) for m in M for t in T]:
                model.addConstr(z[m,t]     + x[j,i,m,t]  <= 1,                                                            name=f'CST98[{j},{i},{m},{t}]') 
                model.addConstr(zz[m,t]    + x[j,i,m,t]  <= 1,                                                            name=f'CST99[{j},{i},{m},{t}]')
            for (m,t) in [(m,t) for m in M for t in T if t<NP]:
                model.addConstr(delta[m,t] - LAMBDA[m]   <= NP*zz[m,t],                                                   name=f'CST10[{m},{t}]')
            for (m,t,i) in [(m,t,i) for m in M for t in T for i in range(PMT) if t<=NP-PMT]:
                model.addConstr(z[m,t+i]   - zz[m,t]     >= 0,                                                            name=f'CST11[{m},{t},{i}]')
            for (m,t) in [(m,t) for m in M for t in T if t>PMT]:
                model.addConstr(sum(zz[m,k] for k in range(t-PMT+1,t+1)) == z[m,t],                                       name=f'CST12[{m},{t}]')
            
            if os.path.isfile('Results/bounds_'+InstanceFile+'.dat')==True:
                with open('Results/bounds_'+InstanceFile+'.dat', 'r') as f:
                    line   = f.readline().strip()
                    values = line.split()
                    model.addConstr(cmax>=values[0],                                                                      name='CSTCmaxLB')
                    model.addConstr(cmax<=values[1],                                                                      name='CSTCmaxUB')
            obj   = model.setObjective(cmax + sum(z[m,t] for m in M for t in T), gp.GRB.MINIMIZE)
        if MAINT==1 and QUAL==1:
            for (m,t) in [(m,t) for m in M for t in T]:    
                model.addConstr(delta[m,t] - LAMBDAQ   <= NP*zz[m,t],                                                     name=f'CST17[{m},{t}]')
            obj   = model.setObjective(cmax + sum(z[m,t] for m in M for t in T), gp.GRB.MINIMIZE)
        
        model.Params.LogToConsole = 1
        if ShowGurobiConsole==0:
            model.Params.LogToConsole = 0
        print("Resolving ...")
        deb=time.process_time() 
        model.optimize()
        cputime=time.process_time()-deb
        
        print("solver status=",model.status)
        if model.status==2:
            print("Solution found in %f seconds" % cputime)      
            objf=model.getVarByName(f"Cmax").X #model.getObjective()
            gap=model.MIPGap
            X={}
            Y={}
            ZZ={}
            DELTA={}
            start_time={}
            task_duration={}
            assigned_machine={}
            for j in J:
                for i in range(NOP[j]):
                    start_time[j,i]=model.getVarByName(f"S[{j},{i}]").X
                    for m in M:
                        for t in T:
                            X[j,i,m,t]=model.getVarByName(f"X[{j},{i},{m},{t}]").X
                        Y[j,i,m]=model.getVarByName(f"Y[{j},{i},{m}]").X
                        if Y[j,i,m]==1:
                            assigned_machine[j,i]=m
                    #print("j=%d i=%d assigned_machine=%d" %(j,i,assigned_machine[j,i]))
                    task_duration[j,i]=PRT[j][i][assigned_machine[j,i]]
            for m in M:
                for t in T:
                    DELTA[m,t]=model.getVarByName(f"DELTA[{m},{t}]").X
            nbrMC={}
            if MAINT==0:
                Cmax0=0.0
                for k in M:
                    tcmax=math.ceil(objf)
                    if model.getVarByName(f"DELTA[{k},{tcmax}]").X > Cmax0:
                        Cmax0=model.getVarByName(f"DELTA[{k},{tcmax}]").X
                    nbrMC[k]=math.ceil(model.getVarByName(f"DELTA[{k},{tcmax}]").X/LAMBDAC)
                Cmax00=objf + CMT*math.ceil(Cmax0/LAMBDAC)
                if QUAL==1:
                    Cmax00=objf+sum(PMT for j in J for i in range(NOP[j])) - 2*NM*PMT
                File_object = open(r"Results/bounds"+InstanceFile+".dat","w")
                File_object.write("%d %d" %(objf,Cmax00))
                File_object.close()
            else:
                for m in M:
                    for t in T:
                        ZZ[m,t]=model.getVarByName(f"ZZ[{m},{t}]").X
                Cmax00=objf
                if QUAL==0:
                    Cmax00=objf + sum(PMT for j in J for i in range(NOP[j])) - 2*NM*PMT
                    File_object = open(r"Results/bounds"+InstanceFile+".dat","w")
                    File_object.write("%d %d" %(objf,Cmax00))
                    File_object.close()
            return X, Y, ZZ, DELTA, objf, gap, cputime, start_time, task_duration, assigned_machine
        else:
            model.computeIIS()
            model.write('lpmodel.ilp')
            return 'infeas','infeas','infeas','infeas','infeas',cputime,'infeas','infeas','infeas'
            