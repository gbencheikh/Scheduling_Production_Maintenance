import random
import numpy as np
import math 

def FJSInstanceReading(filepath):
      proctimes=[]
      with open(filepath, 'r') as f:
            line = f.readline().strip()
            values = line.split()
            NJ=int(values[0])
            NM=int(values[1])
            NOPmax=0
            NOP=[]
            NBRM=[]
            PRT=[]
            proctimes=[]
            for j in range(NJ):
                  line = f.readline().strip()
                  values = line.split()
                  if int(values[0])>NOPmax:
                        NOPmax=int(values[0])
                  NOP.append(int(values[0]))
                  #print("NOP(",j,")=",NOP[j])
                  NBRM_jii=0
                  NBRM.append([])
                  PRT.append([])
                  proctimes.append([])
                  for i in range(NOP[j]):
                        NBRM[j].append(int(values[i+1+NBRM_jii*2]))
                        PRT[j].append([])
                        proctimes[j].append([])
                        #print("NBRM_ji=",NBRM[j][i])
                        for k in range(NM):
                              PRT[j][i].append(0)
                        for k in range(NBRM[j][i]):
                              M_ID_jik=int(values[i+2+2*k+NBRM_jii*2])-1
                              PRT_ji_m =int(values[i+3+2*k+NBRM_jii*2])
                              #print("j=",j,", i=",i,", M_ID_",j,i,k,"=",M_ID_jik,",PRT_ji_m=",PRT_ji_m)
                              PRT[j][i][M_ID_jik] = PRT_ji_m
                              proctimes[j][i].append((M_ID_jik,PRT_ji_m))
                        NBRM_jii=NBRM_jii+NBRM[j][i]    
      return proctimes

def read_instance(instancefilename):
    with open(instancefilename, 'r') as f:
        line = f.readline().strip()
        values = line.split()
        NM=int(values[0])
        NJ=int(values[1])
        NOPmax=0
        NOP=[]
        NBRM=[]
        PRT=[]
        MU=[]
        LAMBDA=[]
        for j in range(NJ):
            line = f.readline().strip()
            values = line.split()
            if int(values[0])>NOPmax:
                NOPmax=int(values[0])
            NOP.append(int(values[0]))
            #print("NOP(",j,")=",NOP[j])
            NBRM_jii=0
            NBRM.append([])
            PRT.append([])
            for i in range(NOP[j]):
                NBRM[j].append(int(values[i+1+NBRM_jii*2]))
                PRT[j].append([])
                #print("NBRM_ji=",NBRM[j][i])
                for k in range(NM):
                    PRT[j][i].append(0)
                for k in range(NBRM[j][i]):
                    M_ID_jik=int(values[i+2+2*k+NBRM_jii*2])-1
                    PRT_ji_m =int(values[i+3+2*k+NBRM_jii*2])
                    PRT[j][i][M_ID_jik] = PRT_ji_m
                NBRM_jii=NBRM_jii+NBRM[j][i]    
        line = f.readline().strip()
        for m in range(NM):
            line = f.readline().strip()
            values = line.split()
            MU.append(float(values[0]))
            LAMBDA.append(float(values[1]))
    f.close()
    sumpmax=0
    for j in range(NJ):
        for i in range(NOP[j]):
            pmax = 0.0
            for k in range(NM):
                if float(PRT[j][i][k]) > pmax:
                    pmax = PRT[j][i][k]
            sumpmax += pmax
    NP = math.ceil(sumpmax)
    
    return PRT

def evaluate(Solution_, data):
    """
    This function evaluates the objective value of 'Solution'.

    Args:
        Solution: the solution to be evaluated
        data: an object of type data that gathers all the data of the current instance

    Returns:
        NM: Number of machines
        NJ: Number of jobs
        cmax: the makespan
        schedule: list of tasks executed on each machine with their start and end dates
        maint: list of maintenance tasks scheduled for each machine
        ehf: the degradation status of each machine at each instant t
        uava: list of unavailability periods for each machine
    """

    solution = Solution_[:]
    NM = max([t[1] for tid, t in enumerate(solution)]) + 1
    NJ = max([t[0] for tid,t in enumerate(solution)]) + 1

    ehf=[0 for i in range(NM)]
    uava=[0 for i in range(NM)] 
    maint=[[],] 
    operid=[0 for j in range(NJ)]
    schedule=[[],]
    for m in range(NM): 
        maint.append([])
        schedule.append([])
    startime=0
    for tid, t in enumerate(solution):
        jobid=t[0]
        machineid=t[1]
        pt=0
        for jid,job in enumerate(data.ProcTime):
            if jid==jobid:
                for oid,oper in enumerate(job):
                    if oid==operid[jobid]:
                        for pid,p in enumerate(oper):
                            if p[0]==machineid:
                                pt=p[1]
        ehf[machineid]=round(ehf[machineid]+data.mu*pt,3)
        
        if len(schedule[machineid])>0:
            tstart=schedule[machineid][len(schedule[machineid])-1][3]
            if ehf[machineid]>data.lambdaPM:
                uava[machineid]=uava[machineid]+data.PM_time
                maint[machineid].append((tstart,uava[machineid]))
                ehf[machineid]=round(data.mu*pt,3)
                tstart=tstart+data.PM_time                
        else:
            tstart=0
        endtimeprevious=0
        if operid[jobid]>0:
            endtimeprevious=max([schedule[m][j][3] for m in range(NM) for j in range(len(schedule[m])) if schedule[m][j][0]==jobid and schedule[m][j][1]==operid[jobid]-1 ])
        if endtimeprevious>tstart:
            tstart=endtimeprevious
        endtime=tstart+pt                  
        schedule[machineid].append((jobid,operid[jobid],tstart,endtime))
        operid[jobid] += 1
        
    cmax=int(max([schedule[m][len(schedule[m])-1][3] for m in range(NM) if len(schedule[m])>0]))

    return NM,NJ,cmax,schedule,maint,ehf

def Voisinage(Solution_,LargV,NbrV,data): # trouver NbrV solutions voisines de Solution dans un voisinage de largeur LargV
    Solution = Solution_[:]
    voisins=[]
    while len(voisins)<NbrV:
        nbropersfound=0
        SelectOper = []
        while nbropersfound<LargV:
            nbropersfound=0
            SelectOper=np.sort(random.sample(range(len(Solution)),LargV))
            for tid,opid in enumerate(SelectOper):
                jobid=Solution[opid][0]
                machid=Solution[opid][1]
                operid=sum([Solution[i][0]==jobid for i in range(opid)])
                if len([omid[0] for id,omid in enumerate(data.ProcTime[jobid][operid]) if omid[0]!=machid])>0:
                    nbropersfound += 1
        voisin=Solution_[:]
        for tid,opid in enumerate(SelectOper):
            jobid=Solution[opid][0]
            machid=Solution[opid][1]
            operid=sum([Solution[i][0]==jobid for i in range(opid)])
            compmach=[omid[0] for omid in data.ProcTime[jobid][operid] if omid[0] != machid]
            if len(compmach)>0:
                selectmach=compmach[0]
                if len(compmach)>1 : 
                    selectmach=random.randint(0,len(compmach))
                listvoisin=list(voisin[opid])
                listvoisin[1]=compmach[0] #selectmach[0]
                voisin[opid]=tuple(listvoisin)
        if voisin!=Solution and voisin not in voisins:
            voisins.append(voisin)    
    return voisins

def Voisinage2(Solution,LargV,NbrV,PTimes): 
    """
    This function finds 'NbrV' neighboring solutions of 'Solution' in a neighborhood of width 'LargV'.

    Args:
        NbrV: number of neighboring solutions to return
        Solution: The solution in question
        LargV: the width of the neighborhood

    Returns:
        voisins: list of neighbors
    """


    voisins=[]
    while len(voisins)<NbrV:
        voisin=[]
        selected_opers_sample=random.sample(range(len(Solution)),k=LargV)
        selected_opers_sorted= sorted(selected_opers_sample)
        selected_opers_sample= sorted(selected_opers_sample)
        if LargV>1:
            while sum([selected_opers_sorted[i]==selected_opers_sample[i] for i in range(LargV)])>0:
                random.shuffle(selected_opers_sample)
        nbr=0
        for i,sol in enumerate(Solution):
            jobid=sol[0]
            machid0=sol[1]
            if nbr<LargV:
                if i==selected_opers_sorted[nbr]:
                    sol0=Solution[selected_opers_sample[nbr]]
                    voisin.append(sol0)
                    nbr=nbr+1
                else:
                    voisin.append(sol)
            else:
                voisin.append(sol)
        partvoisin=[]
        for i,sol in enumerate(voisin):
            partvoisin.append(sol)
            jid=sol[0]
            opid=sum([s[0]==jid for si,s in enumerate(partvoisin)])-1
            compmach=[om[0] for ji,job in enumerate(PTimes) for oi,o in enumerate(job) for omi,om in enumerate(o) if ji==jid and oi==opid]
            if sol[1] not in compmach:
                newm=random.choice(compmach)
                sol=(jid,newm)
            else:
                if len(compmach)>0:
                    newm=random.choice(compmach)
                    sol=(jid,newm)
        voisins.append(voisin)
    return voisins

def GenererSolution(data):
    """
    A function that generates a random solution.

    Args:
        data: an instance

    Returns:
        Solution: a randomly constructed solution.
    """

    Solution=[]
    opers=[]
    for i,job in enumerate(data.ProcTime):
        for o,op in enumerate(job):
            opers.append(i)
    random.shuffle(opers)
    for id,j in enumerate(opers):
        operid=sum([opers[i]==j for i in range(id)])
        compmach=[omid[0] for id,omid in enumerate(data.ProcTime[j][operid])]
        selectmach=compmach[0]
        if len(compmach)>1 : 
            selectmach=compmach[random.randint(0,len(compmach)-1)]
        Solution.append((j,selectmach))
    return Solution

def VoisinageAll(Solution, data):
    """ Cette fonction permet de générer toutes les solutions voisines d'un point 
    
    Args:
        Solution: The solution in question
        data: an instance

    Returns:
        voisins: list of neighbors
    
    """
    voisins=[]
    for id,i in enumerate(Solution):
        for jid,j in enumerate(Solution):
            if jid>id:
                voisin=Solution[:]
                jobid_i=i[0]
                opid_i=sum([Solution[k][0]==jobid_i for k in range(id)])
                mid_i=i[1]
                jobid_j=j[0]
                opid_j=sum([Solution[k][0]==jobid_j for k in range(jid)])
                mid_j=j[1]
                if jobid_i !=jobid_j or mid_i != mid_j:
                    op1=list(i)
                    op2=list(j)
                    temp=op1[0]
                    op1[0]=op2[0]
                    op2[0]=temp
                    voisin[id]=tuple(op1)
                    voisin[jid]=tuple(op2)
                    opid1=sum([voisin[k][0]==op1[0] for k in range(id)])
                    opid2=sum([voisin[k][0]==op2[0] for k in range(jid)])
                    compmach1=[om[0] for ji,job in enumerate(data.ProcTime) for oi,o in enumerate(job) for omi,om in enumerate(o) if ji==op1[0] and oi==opid1]
                    compmach2=[om[0] for ji,job in enumerate(data.ProcTime) for oi,o in enumerate(job) for omi,om in enumerate(o) if ji==op2[0] and oi==opid2]
                    
                    if op1[1] not in compmach1:
                        op1[1]= compmach1[0]
                        duree=10000
                        for _,m in enumerate(data.ProcTime[op1[0]][opid1]):
                            if m[1]<duree:
                                duree=m[1]
                                op1[1]=m[0]
                    if op2[1] not in compmach2:
                        op2[1]= compmach2[0]
                        duree=10000
                        for _,m in enumerate(data.ProcTime[op2[0]][opid2]):
                            if m[1]<duree:
                                duree=m[1]
                                op2[1]=m[0]
                    voisin[id]=tuple(op1)
                    voisin[jid]=tuple(op2)
                    voisins.append(voisin)
    return voisins