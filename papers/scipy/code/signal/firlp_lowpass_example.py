from __future__ import division, print_function

import warnings
import numpy as np
from scipy.optimize import linprog
from scipy.signal import remez, freqz
import matplotlib.pyplot as plt


def solve_linprog(c, A_ub=None, b_ub=None, A_eq=None, b_eq=None, tol=None):
    """
    Solve the linear programming problem:

        minimize
            c.dot(x)
        subject
            A_ub.dot(x) <= b_ub
            A_eq.dot(x) == b_eq

    and convert the solution `x` to the FIR filter coefficients.

    Warnings generated by `scipy.optimize.linprog` are converted to errors.
    """
    if tol is None:
        tol = 1e-6

    options_ip = dict(maxiter=5000, tol=tol)

    with warnings.catch_warnings():
        warnings.simplefilter('error')
        linprog_warning = None
        try:
            # Note: the interior point method was added in scipy 1.0.0.
            result = linprog(c, A_ub, b_ub, A_eq=A_eq, b_eq=b_eq,
                             bounds=(None, None),
                             method='interior-point',
                             options=options_ip)
        except RuntimeWarning as wrn:
            linprog_warning = wrn

    if linprog_warning is not None:
        raise RuntimeWarning('linprog warning converted to error: %s' %
                             (linprog_warning.args,))

    if not result.success:
        raise RuntimeError('linprog failed: %s' % (result.message,))

    # Convert the solution to the linear programming problem to
    # the FIR filter coefficients.  If p is, for example, [a, b, c, d],
    # then taps = 0.5*[d, c, b, 2*a, b, c, d].
    p = result.x[:-1]
    taps = 0.5*np.concatenate((p[:0:-1], [2*p[0]], p[1:]))
    return taps


def firlp_lowpass1(numtaps, deltap, deltas, cutoff, width, fs, tol=None):
    # Edges of the transition band, expressed as radians per sample.
    wp = np.pi*(cutoff - 0.5*width)/(0.5*fs)
    ws = np.pi*(cutoff + 0.5*width)/(0.5*fs)
    # Grid density.
    density = 16*numtaps/np.pi
    # Number of grid points in the pass band.
    numfreqs_pass = int(np.ceil(wp*density))
    # Number of grid points in the stop band.
    numfreqs_stop = int(np.ceil((np.pi - ws)*density))

    # Grid of frequencies in the pass band.
    wpgrid = np.linspace(0, wp, numfreqs_pass)
    # Remove the first; the inequality associated with this frequency
    # will be replaced by an equality constraint.
    wpgrid = wpgrid[1:]
    # Grid of frequencies in the pass band.
    wsgrid = np.linspace(ws, np.pi, numfreqs_stop)

    # wgrid is the combined array of frequencies.
    wgrid = np.concatenate((wpgrid, wsgrid))

    # The array of weights in the linear programming problem.
    weights = np.concatenate((np.full_like(wpgrid, fill_value=1/deltap),
                              np.full_like(wsgrid, fill_value=1/deltas)))
    # The array of desired frequency responses.
    desired = np.concatenate((np.ones_like(wpgrid),
                              np.zeros_like(wsgrid)))

    R = (numtaps - 1)//2
    C = np.cos(wgrid[:, np.newaxis] * np.arange(R+1))
    V = 1/weights[:, np.newaxis]

    A = np.block([[C, -V], [-C, -V]])
    b = np.block([[desired, -desired]]).T
    c = np.zeros(R+2)
    c[-1] = 1

    # The equality constraint corresponding to H(0) = 1.
    A_eq = np.ones((1, R+2))
    A_eq[:, -1] = 0
    b_eq = np.array([1])

    print("numfreqs_pass =", numfreqs_pass, "  numfreqs_stop =", numfreqs_stop)

    print("R =", R)
    print("c.shape =", c.shape)
    print("A.shape =", A.shape)
    print("b.shape =", b.shape)
    print("A_eq.shape =", A_eq.shape)
    print("b_eq.shape =", b_eq.shape)

    taps_lp = solve_linprog(c, A, b, A_eq=A_eq, b_eq=b_eq, tol=tol)
    return taps_lp


fs = 2*np.pi
cutoff = 0.2*np.pi
width = 0.08*np.pi

deltap = 0.001
deltas = 0.002

numtaps = 81
print("numtaps =", numtaps)

taps_lp1 = firlp_lowpass1(numtaps, deltap, deltas, cutoff, width, fs, tol=1e-6)

#----------------------------------------------------------------------

plt.figure(figsize=(4.0, 2.5))

nfreqs = max(4000, 96*numtaps)

wlp1, hlp1 = freqz(taps_lp1, worN=nfreqs)
wlp1 *= 0.5*fs/np.pi
label = 'linear programming, H(0)=1'
plt.plot(wlp1, np.abs(hlp1), label=label)

bands = np.array([0, cutoff - 0.5*width,
                  cutoff + 0.5*width, 0.5*fs])
desired = np.array([1, 0])
weight = np.array([1/deltap, 1/deltas])
taps_remez = remez(numtaps, bands, desired, weight=weight, Hz=fs, maxiter=1000)

w, h = freqz(taps_remez, worN=nfreqs)
w *= 0.5*fs/np.pi
plt.plot(w, np.abs(h), label='remez', ls=(0, (4, 1)))

plt.axvline(cutoff - 0.5*width, color='k', alpha=0.2)
plt.axvline(cutoff + 0.5*width, color='k', alpha=0.2)
plt.legend(framealpha=1, shadow=True)
plt.grid(alpha=0.25)

ax = plt.gca()
ax.set_xticks([0, 0.16*np.pi])
ax.set_xticklabels(['0', '0.16$\pi$'])
plt.xlim(0, 1.05*(cutoff - 0.5*width))
plt.ylim(0.9985, 1.0025)
plt.xlabel('Frequency (radians/sample)')
plt.ylabel('Gain')
plt.title('Pass band detail', fontsize=10)
plt.tight_layout()

plt.savefig('firlp_lowpass_example.pdf')
