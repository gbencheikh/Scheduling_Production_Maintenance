def completionTime(data, solution, weights, debug=True):

    nb_ops_total = sum(data.nbOperationsParJob)

    # Reconstruire i_s (index local de l'op dans son job)
    j_iter = [0] * data.nbJobs
    i_s = [0] * nb_ops_total
    for ind in range(nb_ops_total):
        j = solution[0][ind]
        i_s[ind] = j_iter[j]
        j_iter[j] += 1

    tij = solution[3]  # matrice start times du solveur

    # Reconstruire assign : (j,i) -> (k, start_time)
    assign = {}
    for ind in range(nb_ops_total):
        j = solution[0][ind]
        i = i_s[ind]
        k = solution[1][ind]
        assign[(j, i)] = (k, float(tij[j][i]))

    # Trier les opérations par machine, puis par temps de début
    ops_per_machine = {k: [] for k in range(data.nbMachines)}
    for (j, i), (k, t) in assign.items():
        ops_per_machine[k].append((t, j, i))
    for k in range(data.nbMachines):
        ops_per_machine[k].sort(key=lambda x: x[0])

    # Structures de résultat
    c_ij = [[0.0] * data.nbOperationsParJob[j] for j in range(data.nbJobs)]
    t_ij = [[0.0] * data.nbOperationsParJob[j] for j in range(data.nbJobs)]
    D_kl = [[[0.0] for _ in range(data.nbComposants[k])] for k in range(data.nbMachines)]
    Qj   = [[float(data.Qinitj[j])] for j in range(data.nbJobs)]
    y    = solution[2]  # utiliser directement la solution du solveur, ne pas recalculer

    dispo_machines = [0.0] * data.nbMachines
    nbMaintenance  = 0
    feasible       = True

    # Simuler machine par machine dans l'ordre des slots
    for k in range(data.nbMachines):
        for (t_start, j, i) in ops_per_machine[k]:
            p = data.dureeOperations[k][j][i]
            if p <= 0:
                feasible = False
                continue

            # Respecter le temps du solveur ET la disponibilité machine
            t_ij[j][i] = max(float(t_start), dispo_machines[k])
            end_op = t_ij[j][i] + p
            c_ij[j][i] = end_op

            if debug:
                print(f"O_{j}_{i} on M{k} | start={t_ij[j][i]:.2f} end={end_op:.2f}")

            maint_end = end_op

            for l in range(data.nbComposants[k]):
                last_deg = D_kl[k][l][-1]
                inc = p * data.degradations[k][l][j][i]
                new_deg = last_deg + inc
                D_kl[k][l].append(new_deg)

                # Qualité
                Qj[j].append(max(0.0, Qj[j][-1] - inc * data.alpha_kl[k][l]))

                if debug:
                    print(f"  comp {l}: {last_deg:.4f}+{inc:.4f}={new_deg:.4f} "
                          f"theta={data.seuils_degradation[k][l]} "
                          f"y={y[l][j][i]}")

                # Utiliser UNIQUEMENT la décision y du solveur
                if y[l][j][i]:
                    nbMaintenance += 1
                    D_kl[k][l].append(0.0)
                    m = data.dureeMaintenances[k][l]
                    maint_end = max(maint_end, end_op + m)
                    if debug:
                        print(f"    MAINT: comp{l} dur={m} -> maint_end={maint_end:.2f}")

            dispo_machines[k] = maint_end

    # Makespan : fin de la dernière opération de chaque job
    Cmax = max(c_ij[j][data.nbOperationsParJob[j] - 1] for j in range(data.nbJobs))

    # Pénalité qualité
    penality = sum(1 for j in range(data.nbJobs) if Qj[j][-1] < data.Qjmin[j])
    AOQ = sum(Qj[j][-1] for j in range(data.nbJobs)) / data.nbJobs
    cout = weights[0] * Cmax + weights[1] * nbMaintenance + weights[2] * penality

    return t_ij, c_ij, Cmax, D_kl, y, i_s, Qj, cout, nbMaintenance, AOQ, penality, feasible