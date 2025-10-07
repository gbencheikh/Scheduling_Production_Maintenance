class Data:
    """
    A class to represent scheduling and maintenance data for a production system.
    
    Attributes:
    -----------
    nbJobs : int
        Number of jobs in the system.
    nbMachines : int
        Number of machines available for processing the jobs.
    nbComposants : list of int
        Number of components involved in each machine.
    seuils_degradation : list of int
        List of degradation thresholds for the components, where maintenance should be triggered.
    dureeMaintenances : list of int
        List of maintenance durations corresponding to each component.
    degradations : list of int
        List of current degradation levels for the components.
    nbOperationsParJob : list of int
        List indicating the number of operations each job requires.
    dureeOperations : list of list of list of int
        Nested list where each sublist contains the durations of each operation for the corresponding job.
    """
    
    def __init__(self, nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes):
        """
        Constructs all the necessary attributes for the Data object.

        Parameters:
        -----------
        nbJobs : int
            Number of jobs in the system.
        nbMachines : int
            Number of machines available for processing.
        nbComposants : int
            Number of components in the system.
        seuils_degradation : list of int
            List of degradation thresholds per component.
        dureeMaintenances : list of int
            Maintenance duration for each component.
        !degradations : list of int
            Current degradation levels for each component.
        !degradations2 : list of int
            Current degradation levels for each component.
        nbOperationsParJob : list of int
            Number of operations required for each job.
        dureeOperations : list of list of int
            Duration of each operation for every job (nested list).
        processingTimes : list of list of tuple (int, int)
            processing time of each operation of each job on each compatible machine 
        """
        self.nbJobs = nbJobs
        self.nbMachines = nbMachines
        self.nbComposants = nbComposants
        self.seuils_degradation = seuils_degradation
        self.dureeMaintenances = dureeMaintenances
        self.degradations = degradations
        self.degradations2 = degradations2
        self.nbOperationsParJob = nbOperationsParJob
        self.dureeOperations = dureeOperations
        self.processingTimes = processingTimes
        self.alpha_kl = [[0.0 for l in range(self.nbComposants[k])] for k in range(self.nbMachines)]
        self.Qjmin = [0.8 for j in range(self.nbJobs)]

    def __repr__(self):
        """
        Provides an official string representation of the Data object.
        
        Returns:
        --------
        str
            A string representing the Data object, including all the attributes.
        """
        machines_repr = ""
        machines_repr += "\n"
        machines_repr += f"{'Machine':<10}{'Number of Components':<25}{'Degradation Thresholds':<25}{'Maintenance duration':<25}\n"
        machines_repr += ("-" * 80)
        machines_repr += "\n" # Blank line between jobs for clarity

        # Print each machine's details
        for i, (composants, seuils, duration) in enumerate(zip(self.nbComposants, self.seuils_degradation, self.dureeMaintenances)):
            machines_repr+= (f"{'M' + str(i+1):<10}{str(composants):<25}{str(seuils):<25}")
            # Affiche seulement les durées correspondant au nombre de composants
            machines_repr += f"{str(duration[:composants]):<25}"
            
            machines_repr+="\n"    

        jobs_repr = ""
        jobs_repr += "\n" # Blank line between jobs for clarity
        jobs_repr += (f"{'Job':<10}{'Operation (Machine, Duration)':<18}{'(Component degradation)':<25}\n")
        jobs_repr += ("-" * 40)
        jobs_repr += "\n"  

        # Print each job's details
        # Iterate over jobs and their operations
        for job_index, job in enumerate(self.processingTimes):
            for operation_index, operation in enumerate(job):
                for machine, duration in operation:
                    jobs_repr += (f"J{job_index+1:<10} Op {operation_index+1:<5} M{machine+1:<8} {duration:<8}")
                
                    # Accéder aux dégradations pour chaque composant
                    for index_machine, degradation in enumerate(self.degradations):
                        if (index_machine == machine):
                            for index_component, deg in enumerate(degradation):
                                jobs_repr += (f"(C{index_component + 1},{deg[job_index][operation_index]}) ")
                        
                    jobs_repr += "\n"

                
        return (f"Data(nbJobs={self.nbJobs}, nbMachines={self.nbMachines}) \n"
                f"{machines_repr}\n"
                f"{jobs_repr} \n"
                f"degradation {self.degradations} \n"
                )
    
    def __str__(self):
        """
        Provides a human-readable string representation of the Data object.

        
        Returns:
        --------
        str
            A more readable string summarizing the main information in the Data object.
        """
        return (f"Data with {self.nbJobs} jobs, {self.nbMachines} machines")

if __name__ == "__main__": 
    from CommonFunctions import parse_degradations_file, parse_operations_file

    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"ComplexSystems/TESTS/k1/k1.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"ComplexSystems/TESTS/k1/instance1/instance.txt")

    data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    print("String representation (__str__):")
    print(data)
    
    print("\nDetailed representation (__repr__):")
    print(repr(data))

    print(f"degration 2: {degradations2}")
    print(f"len degradation2 {len(degradations2)}")
