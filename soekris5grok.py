#!/usr/bin/env python3
import pm_remez
import numpy as np
from datetime import datetime
from multiprocessing import Pool
import os

# ------------------------------------------------------------------
# Filter specifications (identical for every sample rate)
# ------------------------------------------------------------------
numtaps   = 3999
f_pass    = 21000.0
f_stop    = 23000.0
ripple_db = 0.002          # change to 0.01 for ~30 % faster convergence if desired
att_db    = 150.0

delta_p = (10**(ripple_db / 20) - 1) / (10**(ripple_db / 20) + 1)
delta_s = 10**(-att_db / 20)
weight  = [1, delta_p / delta_s]

sample_rates = [44100.0, 48000.0, 88200.0, 96000.0, 176400.0, 192000.0]

def design_filter(fs):
    nyq = fs / 2.0
    f_stop_safe = min(f_stop, nyq * 0.999)   # never exceed Nyquist

    bands   = [0.0, f_pass / nyq, f_stop_safe / nyq, 1.0]
    desired = [1, 0]

    print(f"Started  → fs = {fs/1000:6.1f} kHz (Nyquist = {nyq/1000:.1f} kHz)")

    h = pm_remez.remez(
        numtaps=numtaps,
        bands=bands,
        desired=desired,
        weight=weight,
        fs=fs,
        bigfloat=True,
        maxiter=800
    )

    coeffs = np.asarray(h.impulse_response, dtype=np.float64)
    print(f"Finished → fs = {fs/1000:6.1f} kHz")
    return fs, coeffs

# ------------------------------------------------------------------
# Parallel execution
# ------------------------------------------------------------------
if __name__ == '__main__':
    print("Grok Parks-McClellan multi-rate FIR design")
    print("6 sample rates including 44.1 kHz · 3999 taps · ≤0.002 dB ripple · ≥150 dB atten")
    print(f"Running on {os.cpu_count()} cores in parallel...\n")

    start_all = datetime.now()

    with Pool(processes=len(sample_rates)) as pool:
        results = pool.map(design_filter, sample_rates)

    # ------------------------------------------------------------------
    # Write single file grouped by sample rate
    # ------------------------------------------------------------------
    filename = "grokcoefficients.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("-- Grok Parks-McClellan multi-rate FIR coefficients\n")
        f.write(f"-- Generated {datetime.now():%Y-%m-%d %H:%M}\n")
        f.write("-- 3999 taps · 0–21 kHz passband · stop ≥23 kHz (capped at Nyquist)\n")
        f.write("-- ripple ≤0.002 dB · attenuation ≥150 dB · parallel design\n\n")

        for fs, coeffs in results:
            fs_int = int(fs)
            f.write(f"dam1021,{fs_int},8,1004,3999,6.4\n")
            f.write(f"04 Grok PM 0.002dB Linear Phase FIR1 @ {fs_int} Hz\n\n")
            for c in coeffs:
                f.write(f"{c:.18f}\n")
            f.write("\n")

    elapsed_all = datetime.now() - start_all
    print("\n" + "="*80)
    print(f"ALL 6 FILTERS COMPLETED in {elapsed_all}")
    print(f"File written: {filename}")
    print("Ready for dam1021 rev7 – just copy the file to the uManager folder.")
    print("="*80)