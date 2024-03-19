import numpy
import matplotlib
import matplotlib.pyplot as plt
import math

class diagram:
    def __init__(self,NM,NJ,PMT,mu,cmax,schedule,maint,ehf,pngfname):
        self.NM = NM
        self.NJ = NJ
        self.PMT = PMT
        self.mu = mu
        self.cmax = cmax
        self.schedule = schedule
        self.maint = maint
        self.ehf = ehf
        self.ganttsavefilename=pngfname+"_gantt.png"
        self.ehfplotsavefilename=pngfname+"_ehf.png"
        self.mcolors = ['tab:red', 'tab:cyan', 'tab:green', 'tab:orange', 'tab:grey', 'yellow', 'tab:brown', 'magenta',
                'lime', 'tomato', 'tab:blue', 'red', 'cyan', 'green', 'blue','khaki','violet','gold','olivedrab','thisfle']
        
    def plotGantt(self):
        """ Cette fonction pour afficher le digramme de gantt d'une solution donnée """

        # Declaring a figure "gnt"
        fig, gnt = plt.subplots(figsize=(20, 10)) 
        plt.title("Schedule",fontsize=25 ) #MJGR
        gnt.minorticks_on()
        gnt.grid(which='major', linestyle='-', linewidth='0.5', color='grey')    # Customize the major grid
        gnt.grid(which='minor', linestyle=':', linewidth='0.5', color='grey')  # Customize the minor grid
        gnt.set_ylim(0, 10 * (1+self.NM))                       # Setting Y-axis limits
        gnt.set_xlim(0, self.cmax + 5)                             # Setting X-axis limits
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
            jobkeys.append('PM')
            patches.append(matplotlib.patches.Patch(color='black')) 
        
        plt.legend(handles=patches, labels=jobkeys, fontsize=15)
        fig.savefig(self.ganttsavefilename, bbox_inches='tight')
        plt.close(fig)

    def plotEHF(self):
        """ Cette fonction pour afficher l'évolution de la dégradation des machines """
        EHF=numpy.zeros((self.NM,self.cmax))
        for m in range(self.NM):
            MT = []
            for Mtask in self.maint[m]:
                print("MTask:",Mtask)
                MT.append(Mtask[0])
            for tid,task in enumerate(self.schedule[m]):
                for t in range(task[2],task[3]+1):
                    if t < self.cmax: 
                        EHF[m][t]=EHF[m][t-1]+self.mu
                if tid<len(self.schedule[m])-1 :
                    for t in range(task[3],self.schedule[m][tid+1][2]):
                        #EHF[m][t] = 0 if t in MT else EHF[m][t-1]
                        if t in MT: EHF[m][t] = 0  
                        else: EHF[m][t]=EHF[m][t-1]
                else:
                    if task[3]+1<self.cmax:
                        for t in range(task[3]+1,self.cmax):
                            EHF[m][t]=EHF[m][t-1]      
        
        maxehf=max([max(ehf) for eid,ehf in enumerate(EHF)])
        # Declaring a figure "gnt"
        fig, gnt = plt.subplots(figsize=(20, 10)) 
        plt.title("EHF",fontsize=25 ) #MJGR
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
            for t in range(1,math.ceil(self.cmax)):
                plt.plot(t,10*maxehf*(m+1)+10*EHF[m][t],"b^")
                if t<self.cmax-1:
                    if EHF[m][t+1]<EHF[m][t]:
                        plt.text(t,10*maxehf*(m+1)+10*EHF[m][t]+0.5, r'%.2f' % EHF[m][t], fontsize=15)
                    if t>1 and EHF[m][t-1]<EHF[m][t] and EHF[m][t+1]==EHF[m][t] :
                        plt.text(t,10*maxehf*(m+1)+10*EHF[m][t]+0.5, r'%.2f' % EHF[m][t], fontsize=15)
        fig.savefig(self.ehfplotsavefilename)
        plt.close(fig)
    def plotEHF2(self):
        """ Cette fonction pour afficher l'évolution de la dégradation des machines """
        EHF = numpy.zeros((self.NM, self.cmax))
        for m in range(self.NM):
            MT = []
            for Mtask in self.maint[m]:
                # print("MTask:",Mtask)
                MT.append(Mtask[0])
            for tid, task in enumerate(self.schedule[m]):
                for t in range(task[2], task[3] + 1):
                    if t < self.cmax:
                        EHF[m][t] = EHF[m][t - 1] + self.mu
                if tid < len(self.schedule[m]) - 1:
                    for t in range(task[3], self.schedule[m][tid + 1][2]):
                        # EHF[m][t] = 0 if t in MT else EHF[m][t-1]
                        if t in MT:
                            EHF[m][t] = 0
                        else:
                            EHF[m][t] = EHF[m][t - 1]
                else:
                    if task[3] + 1 < self.cmax:
                        for t in range(task[3] + 1, self.cmax):
                            EHF[m][t] = EHF[m][t - 1]
        maxehf = max([max(ehf) for eid, ehf in enumerate(EHF)])
        # Declaring a figure "gnt"
        fig, ehf = plt.subplots(nrows=self.NM, ncols=1, figsize=(20, 20))
        for m in range(self.NM):
            m0=self.NM-m-1
            mlabel='M%d' % (m0+1)
            #plt.subplot(self.NM,1,m)
            ehf[m].minorticks_on()
            ehf[m].grid(which='major', linestyle='-', linewidth='0.5', color='grey')  # Customize the major grid
            ehf[m].grid(which='minor', linestyle=':', linewidth='0.5', color='grey')  # Customize the minor grid
            ehf[m].set_ylim(-0.1, maxehf+0.1)  # Setting Y-axis limits
            ehf[m].set_xlim(0, self.cmax + 1)  # Setting X-axis limits
            if m<self.NM-1: plt.setp(ehf[m].get_xticklabels(), visible=False)
            if m==self.NM-1:
                ehf[m].set_xlabel('Time', fontsize=20, weight='bold')  # Setting labels for x-axis and y-axis
            ehf[m].set_ylabel(mlabel, fontsize=20, weight='bold')
            ehf[m].tick_params(labelsize=22)

            for t in range(1, math.ceil(self.cmax)):
                ehf[m].plot(t, EHF[m0][t], "b^")
                if t < self.cmax - 1:
                    if EHF[m0][t + 1] < EHF[m0][t]:
                        ehf[m].text(t, EHF[m0][t] + 0.05, r'%.2f' % EHF[m0][t], fontsize=15)
                    if t > 1 and EHF[m0][t - 1] < EHF[m][t] and EHF[m0][t + 1] == EHF[m0][t]:
                        ehf[m].text(t, EHF[m0][t] + 0.05, r'%.2f' % EHF[m0][t], fontsize=15)
                else:
                    ehf[m].text(t, EHF[m0][t] + 0.05, r'%.2f' % EHF[m0][t], fontsize=15)
            ehf[m].plot(range(1, math.ceil(self.cmax)), [EHF[m0][t] for t in range(1, math.ceil(self.cmax))],color="b",ls="--")
        fig.savefig(self.ehfplotsavefilename)
        plt.close(fig)