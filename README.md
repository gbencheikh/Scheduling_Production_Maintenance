# Scheduling_Production_Maintenance


1. Introduction
The Production and Maintenance Scheduling Program is designed to facilitate the scheduling of production and maintenance activities using two metaheuristic algorithms: Variable Neighborhood Search (VNS) and Simulated Annealing (SA). These algorithms aim to optimize scheduling solutions, considering various constraints (flexible job shop constraints and predictive maintennace planning) and objective of minimizing makespan Cmax.

2. Installation
No specific requirement needed

3. Algorithms
- Variable Neighborhood Search (VNS)
- Simulated Annealing (SA)
- Tabu Search (TS)

5. Input Format
The provided class data contains attributes representing various parameters and data related to production and maintenance scheduling.

5.1. Degradation Thresholds:
lambdaC: Degradation threshold of Corrective Maintenance. It represents the level of degradation at which corrective maintenance should be performed.
lambdaQ: Degradation threshold of Quality Maintenance. It denotes the level of degradation at which maintenance should be initiated for quality insurance.
lambdaPM: Degradation threshold of Preventive Maintenance. It signifies the level of degradation at which preventive maintenance actions should be taken.

5.2. Reliability Degradation Rate:
mu: Reliability degradation rate. It indicates the rate at which the reliability of the system decreases over time.

5.3. Processing Time for Jobs:
ProcTime: A nested list representing processing times for various jobs on different machines. Each job is represented as a list of tasks, where each task is associated with a machine ID and its corresponding processing time. For example:
ProcTime[0]: Represents the processing times for Job 0.
ProcTime[0][0]: Represents the tasks for the first operation of Job 0.
ProcTime[0][0][0]: Represents the machine ID and processing time for the first task of Job 0.

5.4. Maintenance Times:
PM_time: Time required for Preventive Maintenance (PM) activities.
CM_time: Time required for Corrective Maintenance (CM) activities.

6. Output Format
when execusting a certain metaheuristic, the algorithm return the final solution and the corresponding Cmax and digrams are saved into folder results with a unique fileName at which time solution has been generated. 
