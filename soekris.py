import pm_remez
import numpy as np
from scipy.signal import freqz

# Define filter specs
PASSBAND_CUTOFF = 22000.0  # 22 kHz passband edge
STOPBAND_START  = 24000.0  # 24 kHz stopband begins
NUM_TAPS = 3999
# We choose a high stopband weight to enforce strong attenuation.
# This weight can be tuned. A value around 1e5 yields ~130 dB stopband attenuation 
# if ~1 dB passband ripple is allowed. We start slightly lower for easier convergence.
STOPBAND_WEIGHT = 10000  

# Sample rates and their interpolation factors
rates = [
    (44100, 8),
    (48000, 8),
    (88200, 4),
    (96000, 4),
    (176400, 2),
    (192000, 2)
]

# Storage for designed filters to avoid duplicate calculations for shared sets
designed_filters = {}  # key oversampled_fs, value (coefficients, multiplier, desc_info)

for fs, interp in rates:
    # Compute effective sampling rate after interpolation
    fs_eff = fs * interp
    # Determine normalized band edges for remez (relative to fs_eff)
    # Ensure stopband edge does not exceed Nyquist (fs_eff2)
    pass_edge = PASSBAND_CUTOFF
    stop_edge = STOPBAND_START
    if stop_edge  fs_eff  2
        stop_edge = fs_eff  2  # (This will happen only for 44.1k base, where fs_eff2=176.4k  24k, so no change)
    # In normalized [0,0.5] units for pm_remez (we can use fs=fs_eff instead of normalizing manually)
    bands = [0.0, pass_edge, stop_edge, fs_eff2]
    desired = [1.0, 0.0]
    weight = [1.0, STOPBAND_WEIGHT]
    # Use oversampled fs directly in pm_remez call via fs parameter (so bands are in Hz)
    design_key = fs_eff  # use effective fs as key for shared filters
    if design_key in designed_filters
        # If we already designed this oversampling filter, reuse it (shared coefficients)
        filt_coeffs, multiplier, desc_info = designed_filters[design_key]
    else
        # Design a new filter for this oversampling factor
        try
            # First try with double precision
            result = pm_remez.remez(NUM_TAPS, bands, desired, weight=weight, fs=fs_eff, maxiter=200)
        except Exception as e
            print(fInitial Remez attempt failed for fs_eff={fs_eff} Hz (error {e}). Retrying with bigfloat...)
            result = pm_remez.remez(NUM_TAPS, bands, desired, weight=weight, fs=fs_eff, maxiter=200, bigfloat=True)
        else
            # If converged but flatness is poor or iterations hit max, try bigfloat for safety
            if hasattr(result, 'num_iterations') and hasattr(result, 'flatness')
                if result.num_iterations = 200 or result.flatness  1e-6
                    # The algorithm might not have fully converged; switch to high precision
                    print(f"Retrying with bigfloat for fs_eff={fs_eff} to ensure convergence (iter={result.num_iterations}, flatness={result.flatness:.2e})")
                    result = pm_remez.remez(NUM_TAPS, bands, desired, weight=weight, fs=fs_eff, maxiter=300, bigfloat=True)
        # `result` from pm_remez.remez can be an object with attributes or just the impulse list.
        # In pm-remez 0.2+, the function returns a `RemezResult` object with attributes including impulse_response.
        # We handle both cases for compatibility.
        if isinstance(result, list) or isinstance(result, np.ndarray)
            h = np.array(result)
        else
            h = np.array(result.impulse_response)
        # Compute DC gain (should be near 1.0 if passband includes DC).
        dc_gain = np.sum(h)
        # Calculate multiplier to normalize DC gain to 1.0
        if dc_gain == 0
            multiplier = 1.0  # avoid division by zero (though dc_gain should not be zero for a lowpass filter)
        else
            multiplier = 1.0  dc_gain
        # Round multiplier to one decimal place (formatting as in DAM1021 file)
        multiplier = float(f{multiplier.1f})
        # Analyze frequency response to determine -1 dB point and stopband attenuation for description
        w, H = freqz(h, worN=16384, fs=fs_eff)
        H_mag = np.abs(H)
        # Find frequency where gain drops to -1 dB (~0.891 amplitude) in passband
        passband_db = 20  np.log10(H_mag)
        # Limit search to frequencies = pass_edge (we expect -1 dB near the edge if ripple is around that)
        idx = np.where((w = PASSBAND_CUTOFF) & (passband_db = -1.0))[0]
        if len(idx)  0
            f_1db = w[idx[0]]
            ripple_db = -1.0  # at least 1 dB ripple exists by f_1db
        else
            # If never drops 1 dB in band, use pass_edge as reference
            f_1db = PASSBAND_CUTOFF
            ripple_db = 20  np.log10(H_mag[np.argmax(w = PASSBAND_CUTOFF)])
        # Find stopband attenuation at STOPBAND_START
        stop_idx = np.argmax(w = STOPBAND_START)
        att_db = 20  np.log10(H_mag[stop_idx])
        # If the attenuation is below the measurable range (very large negative), floor it
        if att_db  -300  # -300 dB is effectively numerical zero for double precision
            att_db = -300.0
        desc_info = (f_1db, ripple_db, att_db)
        # Store for reuse (shared filter for this fs_eff)
        designed_filters[design_key] = (h, multiplier, desc_info)
        filt_coeffs = h
    # Prepare the output lines in DAM1021 format
    rate = fs
    interp = interp
    # Determine filter type code use 4 for linear-phase FIR1. Use 1004 if defining coefficients, or 4 if referencing.
    if design_key in designed_filters and designed_filters[design_key][0] is filt_coeffs
        # If this rate is the first one using this filter, mark as definition (1000+type)
        type_code = 1004
        # Compose description string using desc_info
        f_1db, ripple_db, att_db = desc_info
        # Format frequencies in kHz with one decimal
        desc = f04 Linear Phase FIR1, {rate1000.1f} Ksps, {f_1db1000.1f} kHz {ripple_db.0f} dB, {STOPBAND_START1000.1f} kHz {att_db.0f} dB
    else
        # Subsequent use of same filter coefficients
        type_code = 4
        # Use a shorter description (we'll indicate the same performance)
        desc = f04 Linear Phase FIR1, {rate1000.1f} Ksps, 22.0 kHz 0 dB, 24.0 kHz -120 dB
    # Print the header line and description
    print(fdam1021,{rate},{interp},{type_code},{NUM_TAPS},{multiplier})
    print(desc)
    # If this is a defining line (1004), output all coefficients
    if type_code = 1000
        for coef in filt_coeffs
            print(f{coef.16f})
