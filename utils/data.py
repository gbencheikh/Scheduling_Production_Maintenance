class data:
    def __init__(self, lambdaPM, mu, PM_time, ProcTime):
        self.lambdaC=0.99 # Degradtion threshold of Corrective Maintenance  
        self.lambdaQ=0.8  # Degradation threshold of Quality maintenance
        self.lambdaPM=lambdaPM # Degradation threshold of Preventive Maintenance
        self.mu=mu      # reliability degradation rate
        self.ProcTime=ProcTime        
        self.PM_time=PM_time
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
        