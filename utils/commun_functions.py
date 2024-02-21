import random
import numpy as np

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

def evaluate(Solution_, data):
    solution = Solution_[:]
    """ Cette fonction pour évaluer les solutions """
    NM = max([t[1] for tid, t in enumerate(solution)]) + 1
    NJ = max([t[0] for tid,t in enumerate(solution)]) + 1

    ehf=[0 for i in range(NM)]
    uava=[0 for i in range(NM)] #total unavailability duration
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

def GenererSolution(data):
    sol=[]
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
        sol.append((j,selectmach))
    return sol