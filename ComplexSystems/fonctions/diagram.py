import numpy
import matplotlib
import matplotlib.pyplot as plt
import math
#from colors import colors
import matplotlib.patches as mpatches
import re

colors = {
    'J1': '#ff9999',   # Light Red
    'J2': '#99ff99',   # Light Green
    'J3': '#9999ff',   # Light Blue
    'J4': '#61620abf', # Dark Blue
    'J5': '#ffcc99',   # Light Orange
    'J6': '#66c2a5',   # Teal
    'J7': '#fc8d62',   # Salmon
    'J8': '#8da0cb',   # Lavender
    'J9': '#e78ac3',   # Pink
    'J10': '#a6d854',  # Lime Green
    'J11': '#ffd92f',  # Yellow
    'J12': '#e5c494',  # Beige
    'J13': '#b3b3b3',  # Grey
    'J14': '#1f78b4',  # Bright Blue
    'J15': '#33a02c',  # Bright Green
    'Maintenances': 'black'  # Dark Slate Grey
}
        
def plotGantt(result, pngfname, plottitle, showgantt):
    """ Display a Gantt chart for a given scheduling solution.

    This function takes a JSON-like object containing scheduling information and generates a Gantt chart 
    to visually represent the allocation of tasks across different machines over time. The chart can be 
    saved as a PNG file and optionally displayed.

    Parameters:
    -----------
    result : dict
        A dictionary containing scheduling information. Expected structure:
        {
            'fig': [
                {
                    'task': str,       # The name of the machine
                    'start': float,    # Start time of the task
                    'end': float,      # End time of the task
                    'rsc': str,        # Resource type or job label
                    'label': str,      # Label to display on the bar
                    'info': str        # Additional information (optional)
                },
                ...
            ]
        }
    
    pngfname : str
        The filename (without extension) for saving the Gantt chart as a PNG image.
    
    showgantt : bool
        If True, the Gantt chart will be displayed after being generated; if False, it will only be saved 
        as a file.

    Returns:
    --------
    None
        This function does not return a value. It generates and saves a Gantt chart based on the provided 
        scheduling data.
    """
    # Initialize plot
    fig, gnt = plt.subplots(figsize=(15, 8))
    
    gnt.minorticks_on()
    gnt.grid(which='major', linestyle='-', linewidth='0.5', color='grey')   # Customize the major grid
    gnt.grid(which='minor', linestyle=':', linewidth='0.5', color='grey')   # Customize the minor grid
    
    gnt.set_xlabel('Time', fontsize=24, weight='bold')                      # Setting labels for x-axis and y-axis
    gnt.set_ylabel('Processors', fontsize=24, weight='bold')
    
    # Extract unique machines
    fig_data = result['fig']

    machines = sorted(set(task["task"] for task in fig_data))
    machine_index = {machine: idx for idx, machine in enumerate(machines)}

     # Liste pour stocker les jobs existantes dans les données
    jobs = set()

    # Plot each task
    for task in fig_data:
        machine = task["task"]
        start = task["start"]
        end = task["end"]
        duration = end - start
        rsc = task["rsc"]
        label = task["label"]
        info = task.get("info", "")

        # Choose color based on resource type
        color = colors.get(rsc, "gray")
        jobs.add(rsc)

        # Plot bar
        gnt.barh(machine_index[machine], duration, left=start, color=color, edgecolor="black")
        
        # Add text label in the middle of each bar
        if rsc != "Maintenances":
            gnt.text(start + duration / 2, machine_index[machine], label, ha='center', va='center', color="black")
        else: 
            composants = re.findall(r"Composant\s*:\s*(\d+)", info)
            i=0
            for composant in composants: 
                label = f"C{composant}"
                font_size = 8                                   # Police plus petite pour les tâches de maintenance
                text_y_pos = machine_index[machine] + i*0.15    # Décalage vertical de l'étiquette
                i+= 1
                gnt.text(start + duration / 2, text_y_pos, label, ha='center', va='center', fontsize=font_size, color="white")

    # Formatting
    gnt.set_yticks(range(len(machines)))
    gnt.set_yticklabels(machines, fontsize=20)
    gnt.set_xlabel("Time")
    gnt.set_title("Gantt Chart")
    plt.title(plottitle,fontsize=25)
    
    # Créer la légende uniquement pour les ressources existantes
    jobs = sorted(set(job for job in jobs))
    legend_handles = [mpatches.Patch(color=colors[rsc], label=rsc) for rsc in jobs]
    gnt.legend(handles=legend_handles, title="Jobs", fontsize=10, bbox_to_anchor=(1.05, 1), loc='upper left')


    plt.tight_layout()
    fig.savefig(f"{pngfname}-GanttDiagram{plottitle}.png", bbox_inches='tight')
    if showgantt == True:
        plt.show()

if __name__ == "__main__": 
    from Save_Read_JSON import lire_fichier_json
    from CommonFunctions import parse_degradations_file, parse_operations_file
    from data import Data 

    nbJobs, nbMachines, nbOperationsParJob, dureeOperations, processingTimes = parse_operations_file(f"ComplexSystems/TESTS/k1/k1.txt")
    _, _, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2 = parse_degradations_file(f"ComplexSystems/TESTS/k1/instance01/instance.txt")

    data = Data(nbJobs, nbMachines, nbComposants, seuils_degradation, dureeMaintenances, degradations, degradations2, nbOperationsParJob, dureeOperations, processingTimes)
    
    result = lire_fichier_json(f"ComplexSystems/TESTS/k1/instance01/meta_heuristic_result.json")
    plotGantt(result, "ComplexSystems/test_figure","k1-instance01", showgantt=True)