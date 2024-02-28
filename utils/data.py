class data:
    def __init__(self):
        self.lambdaC=0.99 # Degradtion threshold of Corrective Maintenance  
        self.lambdaQ=0.8  # Degradation threshold of Quality maintenance
        self.lambdaPM=0.99 # Degradation threshold of Preventive Maintenance
        self.mu=0.001      # reliability degradation rate
        self.ProcTime=[ #(machine_id, process_time) 
                [ [(0,  8), (1, 18)], [(1, 16), (0, 13)], [(3, 12), (0, 18)] ],	#Job0
                [ [(0, 20)         ], [(2, 10)         ], [(1, 18), (0, 14)] ],	#Job1
                [ [(2, 12), (0, 17)], [(3,  8), (0, 18)], [(0, 15), (1, 17)] ],	#Job2
                [ [(3, 14), (0, 15)], [(1, 18), (0, 12)]                     ],	#Job3
                [ [(2, 10)         ], [(0, 15), (1, 19)]                     ]	#Job4
            ]
        self.PM_time=2
        self.CM_time=5
    
    def procTime(self, ProcTime):
        self.ProcTime = ProcTime

    def print(self):
        print(f"lambdaC: {self.lambdaC}")
        print(f"lambdaQ: {self.lambdaQ}")
        print(f"lambdaQ: {self.lambdaQ}")
        print(f"lambdaPM: {self.lambdaPM}")
        print(f"ProcTime: {self.ProcTime}")
        print(f"PM time: {self.PM_time}")
        print(f"CM time: {self.CM_time}")
        