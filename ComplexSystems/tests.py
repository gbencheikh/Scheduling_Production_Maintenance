import numpy as np
from scipy.linalg import expm
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import expm_multiply

def P_of_t(Q: np.ndarray, t: float) -> np.ndarray:
    """
    Compute P(t) = exp(Q t) for a CTMC generator Q.
    """
    Q = np.asarray(Q, dtype=float)
    return expm(Q * t)

# --- Example ---
Q = np.array([
    [-0.3,  0.3,  0.0],
    [ 0.1, -0.4,  0.3],
    [ 0.0,  0.2, -0.2],
])

t = 2.0
P = P_of_t(Q, t)
print(P)                  # transition probabilities after time t
print(P.sum(axis=1))      # ~1.0 for each row

times = [0.1, 1.0, 5.0]
Ps = {t: P_of_t(Q, t) for t in times}
def stochasticize(P, eps=1e-12):
    P = P.copy()
    P[P < 0] = 0.0
    rowsum = P.sum(axis=1, keepdims=True)
    P /= np.where(rowsum == 0, 1.0, rowsum)
    return P

P = stochasticize(P)
print(P)

# Sparse Q
Q_sparse = csr_matrix(Q)
print(Q)
print(Q_sparse)

# Initial distribution (row vector)
p0 = np.array([1.0, 0.0, 0.0])

# Compute p(t) = p0 * exp(Q t) without forming P(t)
pt = expm_multiply((Q_sparse), p0, start=0.0, stop=t, num=2)[-1]
# (num=2 returns values at start & stop; we take the last one)

print(pt, pt.sum())  # distribution at time t, sums ~ 1