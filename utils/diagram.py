import numpy
import matplotlib
import matplotlib.pyplot as plt
import math

class diagram:
    def __init__(self,NM,NJ,PMT,lamda,mu,cmax,schedule,maint,ehf,pngfname,showgantt,showehf):
        self.NM = NM
        self.NJ = NJ
        self.PMT = PMT
        self.lamda=lamda
        self.mu = mu
        self.cmax = cmax
        self.schedule = schedule
        self.maint = maint
        self.ehf = ehf
        self.ganttsavefilename="%s_pmt%d-lambda%0.2f-mu%0.2f_gantt.png" % (pngfname,PMT,lamda,mu)
        self.ehfplotsavefilename="%s_pmt%d-lambda%0.2f-mu%0.2f_ehf.png" % (pngfname,PMT,lamda,mu)
        self.mcolors = ['tab:red', 'tab:cyan', 'tab:green', 'tab:orange', 'tab:grey', 'yellow', 'tab:brown', 'magenta',
                'lime', 'tomato', 'tab:blue', 'red', 'cyan', 'green', 'blue','khaki','violet','gold','olivedrab','thisfle']
        self.showG=showgantt
        self.showEHF=showehf
        self.pngfname=pngfname
        
    def plotGantt(self):
        """ Cette fonction pour afficher le digramme de gantt d'une solution donnée """

        # Declaring a figure "gnt"
        fig, gnt = plt.subplots(figsize=(20, 10)) 
        gnttitle="schedule %s $\mu$=%0.2f PMT=%d" % (self.pngfname,self.mu,self.PMT)
        plt.title(gnttitle,fontsize=25 ) #MJGR
        gnt.minorticks_on()
        gnt.grid(which='major', linestyle='-', linewidth='0.5', color='grey')    # Customize the major grid
        gnt.grid(which='minor', linestyle=':', linewidth='0.5', color='grey')  # Customize the minor grid
        gnt.set_ylim(0, 10 * (1+self.NM))                       # Setting Y-axis limits
        gnt.set_xlim(0, self.cmax)                             # Setting X-axis limits
        gnt.set_xlabel('Time', fontsize=24, weight='bold')                      # Setting labels for x-axis and y-axis
        gnt.set_ylabel('Processors', fontsize=24, weight='bold')
        gnt.tick_params(labelsize=22)
        yticks = [] 
        setticks = []
        for m in range(self.NM):
            yticks.append(10 * (m + 1))
            setticks.append(10 * (m + 1))
        gnt.set_yticks(setticks) # Setting ticks on y-axis

        ylabels = []
        for m in range(self.NM):
            mach = 'M' + str(m+1)
            ylabels.append(mach)

        gnt.set_yticklabels(ylabels, fontsize=20) # Labelling tickes of y-axis
        
        gnt.grid(True, linewidth=0.5)
        for m in range(self.NM):
            a = []
            b = ()
            for tid,task in enumerate(self.schedule[m]):
                a.append((task[2], task[3]-task[2]))
                b = b + (self.mcolors[task[0]],)
                op = '$_{(%i,%i)}$' % (task[0], task[1])
                x = task[2] + 0.1
                y = yticks[m]
                gnt.text(x, y, op, fontsize=20, weight='bold')   
                gnt.broken_barh(a, (yticks[m]-2, 4), facecolors=b,label ='Job %i'%task[0])
            if len(self.maint[m])>0:
                for tid,mtask in enumerate(self.maint[m]):
                    a.append((mtask[0], self.PMT))
                    b = b + ('black',)
                gnt.broken_barh(a, (yticks[m]-2, 4), facecolors=b,label ='Maint')
        patches = []
        jobkeys =[]
        for j in range(self.NJ):
            jobkeys.append('Job %i'%j)
            patches.append(matplotlib.patches.Patch(color=self.mcolors[j])) 
        if sum([len(self.maint[m] ) for m in range(len(self.maint))])>0:
            print("/!\ some maintenance tasks are planned !")
            jobkeys.append('PdM')
            patches.append(matplotlib.patches.Patch(color='black')) 
        print(self.ganttsavefilename)
        plt.legend(handles=patches, labels=jobkeys, fontsize=15)
        fig.savefig(self.ganttsavefilename, bbox_inches='tight')
        if self.showG==0: plt.close(fig)

    def plotEHF(self):
        """ Cette fonction pour afficher l'évolution de la dégradation des machines """
        EHF=numpy.zeros((self.NM,self.cmax+1))
        for m in range(self.NM):
            MT = []
            for Mtask in self.maint[m]:
                print("MTask:",Mtask)
                MT.append(Mtask[0])
            for tid,task in enumerate(self.schedule[m]):
                if tid==0:
                    for t in range(task[2]+1):
                        EHF[m][t]=0
                for t in range(task[2]+1,task[3]+1):
                    if t <= self.cmax: 
                        EHF[m][t]=EHF[m][t-1]+self.mu
                if tid<len(self.schedule[m])-1 :
                    for t in range(task[3],self.schedule[m][tid+1][2]):
                        #EHF[m][t] = 0 if t in MT else EHF[m][t-1]
                        if t in MT: EHF[m][t] = 0  
                        else: EHF[m][t]=EHF[m][t-1]
                else:
                    if task[3]+1<=self.cmax:
                        for t in range(task[3]+1,self.cmax):
                            EHF[m][t]=EHF[m][t-1]      
        
        maxehf=max([max(ehf) for eid,ehf in enumerate(EHF)])
        # Declaring a figure "gnt"
        fig, gnt = plt.subplots(figsize=(20, 10)) 

        #plt.title("EHF"+self.pngfname,fontsize=25 ) #MJGR
        gnt.minorticks_on()
        gnt.grid(which='major', linestyle='-', linewidth='0.5', color='grey')    # Customize the major grid
        gnt.grid(which='minor', linestyle=':', linewidth='0.5', color='grey')  # Customize the minor grid
        gnt.set_ylim(0, 10*maxehf*(1+self.NM))                       # Setting Y-axis limits
        gnt.set_xlim(0, self.cmax + 5)                             # Setting X-axis limits
        gnt.set_xlabel('Time', fontsize=24, weight='bold')                      # Setting labels for x-axis and y-axis
        gnt.set_ylabel('Processors', fontsize=24, weight='bold')
        gnt.tick_params(labelsize=22)
        yticks = [] 
        setticks = []
        for m in range(self.NM):
            yticks.append(10*maxehf*(m+1))
            setticks.append(10*maxehf*(m+1))
        gnt.set_yticks(setticks) # Setting ticks on y-axis
        ylabels = []
        for m in range(self.NM):
            mach = 'M' + str(m+1)
            ylabels.append(mach)

        gnt.set_yticklabels(ylabels, fontsize=20) # Labelling tickes of y-axis
        
        gnt.grid(True, linewidth=0.5)
        for m in range(self.NM):
            plt.plot(0,0,"b^")
            for t in range(1,math.ceil(self.cmax)+1):
                plt.plot(t,10*maxehf*(m+1)+10*EHF[m][t],"b^")
                if t<self.cmax-1:
                    if EHF[m][t+1]<EHF[m][t]:
                        plt.text(t,10*maxehf*(m+1)+10*EHF[m][t]+0.5, r'%.2f' % EHF[m][t], fontsize=15)
                    if t>1 and EHF[m][t-1]<EHF[m][t] and EHF[m][t+1]==EHF[m][t] :
                        plt.text(t,10*maxehf*(m+1)+10*EHF[m][t]+0.5, r'%.2f' % EHF[m][t], fontsize=15)
        fig.savefig(self.ehfplotsavefilename)
        if self.showEHF==0:plt.close(fig)
    def plotEHF2(self):
        """ Cette fonction pour afficher l'évolution de la dégradation des machines """
        EHF = numpy.zeros((self.NM, self.cmax+1))
        for m in range(self.NM):
            MT = []
            for Mtask in self.maint[m]:
                # print("MTask:",Mtask)
                MT.append(Mtask[0])
            print(MT)
            for tid, task in enumerate(self.schedule[m]):
                if tid==0:
                    for t in range(task[2]+1):
                        EHF[m][t]=0
                for t in range(task[2]+1, task[3] + 1):
                    if t <= self.cmax:
                        EHF[m][t] = EHF[m][t - 1] + self.mu
                if tid < len(self.schedule[m]) - 1:
                    for t in range(task[3]+1, self.schedule[m][tid + 1][2]+1):
                        # EHF[m][t] = 0 if t in MT else EHF[m][t-1]
                        if t-1 in MT:
                            EHF[m][t] = 0
                        else:
                            EHF[m][t] = EHF[m][t - 1]
                else:
                    if task[3]  < self.cmax:
                        for t in range(task[3] + 1, self.cmax+1):
                            EHF[m][t] = EHF[m][t - 1]
        maxehf = max([max(ehf) for eid, ehf in enumerate(EHF)])
        # Declaring a figure "gnt"
        fig, ehf = plt.subplots(nrows=self.NM, ncols=1, figsize=(20, 15))
        plt.suptitle("EHF %s $\mu$=%0.2f PMT=%d" % (self.pngfname,self.mu,self.PMT),fontsize=25 )
        for m in range(self.NM):
            m0=self.NM-m-1
            mlabel='M%d' % (m0+1)
            #plt.subplot(self.NM,1,m)
            ehf[m].minorticks_on()
            ehf[m].grid(which='major', linestyle='-', linewidth='0.5', color='grey')  # Customize the major grid
            ehf[m].grid(which='minor', linestyle=':', linewidth='0.5', color='grey')  # Customize the minor grid
            ehf[m].set_ylim(-0.1, maxehf+0.1)  # Setting Y-axis limits
            ehf[m].set_xlim(0, self.cmax)  # Setting X-axis limits
            if m<self.NM-1: plt.setp(ehf[m].get_xticklabels(), visible=False)
            if m==self.NM-1:
                ehf[m].set_xlabel('Time', fontsize=20, weight='bold')  # Setting labels for x-axis and y-axis
            ehf[m].set_ylabel(mlabel, fontsize=20, weight='bold')
            ehf[m].tick_params(labelsize=22)
            ehf[m].plot(0, 0, "b^")
            for t in range(1, math.ceil(self.cmax)+1):
                ehf[m].plot(t, EHF[m0][t], "b^")
                if t < self.cmax - 1:
                    if EHF[m0][t + 1] < EHF[m0][t]:
                        ehf[m].text(t, EHF[m0][t] + 0.05, r'%.2f' % EHF[m0][t], fontsize=15)
                    if t > 1 and EHF[m0][t - 1] < EHF[m][t] and EHF[m0][t + 1] == EHF[m0][t]:
                        ehf[m].text(t, EHF[m0][t] + 0.05, r'%.2f' % EHF[m0][t], fontsize=15)
                else:
                    ehf[m].text(t, EHF[m0][t] + 0.05, r'%.2f' % EHF[m0][t], fontsize=15)
            ehf[m].plot(range(math.ceil(self.cmax)+1), [EHF[m0][t] for t in range(math.ceil(self.cmax)+1)],color="b",ls="--")
        fig.savefig(self.ehfplotsavefilename)
        if self.showEHF==0: plt.close(fig)
        return EHF