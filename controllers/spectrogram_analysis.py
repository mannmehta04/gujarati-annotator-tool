"""
controllers/spectrogram_analysis.py

Spectrogram and normalized spectrum analysis for a single audio segment.

Adapted from research codebase. Takes a WAV audio file path,
runs the full analysis pipeline, and returns a path to a PNG
image containing the combined plots.

All temp files created internally are cleaned up. The output PNG
temp file is the caller's responsibility to delete after use.
"""

import os
import tempfile
import logging
import numpy as np

_logger = logging.getLogger('natak.spectrogram')


# ── Core DSP Functions ─────────────────────────────────────────────────────────

def _ext_seg(amp, sr, seg_dur=0.1, n_seg=40,
             threshold_r=0.05, max_tries_per_seg=20):
    """
    Randomly extract non-silent segments from an audio array.

    Args:
        amp: 1D numpy array (mono audio)
        sr: sampling rate
        seg_dur: duration of each segment in seconds (default 0.1)
        n_seg: target number of segments (default 40)
        threshold_r: segment max amp must be >= threshold_r * utterance max
        max_tries_per_seg: max attempts per accepted segment

    Returns:
        (segments: ndarray shape (n,seg_len),
         starts: ndarray of int start indices,
         seg_len: int samples per segment)
    """
    seg_len = int(seg_dur * sr)
    if seg_len <= 0 or len(amp) <= seg_len:
        return np.empty((0, max(seg_len, 1))), np.array([], dtype=int), seg_len

    rng = np.random.default_rng(121118)

    A_utt_max = np.max(np.abs(amp))
    if A_utt_max == 0:
        return np.empty((0, seg_len)), np.array([], dtype=int), seg_len

    threshold = threshold_r * A_utt_max
    segments  = []
    starts    = []
    tries     = 0
    max_tries = n_seg * max_tries_per_seg

    while len(segments) < n_seg and tries < max_tries:
        tries += 1
        start   = rng.integers(0, len(amp) - seg_len)
        end     = start + seg_len
        segment = amp[start:end]
        if np.max(np.abs(segment)) >= threshold:
            segments.append(segment)
            starts.append(start)

    if not segments:
        return np.empty((0, seg_len)), np.array([], dtype=int), seg_len

    return np.array(segments), np.array(starts), seg_len


def _norm_spect(segment, sr):
    """
    Computes normalized spectrum for a single segment.

    Returns:
        freqs, mag, mag_db, Fn, An, An_db, Am, Fm
    """
    seg_len  = len(segment)
    spectrum = np.fft.rfft(segment)
    freqs    = np.fft.rfftfreq(seg_len, d=1.0 / sr)
    mag      = np.abs(spectrum)
    mag_db   = 20 * np.log10(mag + 1e-12)

    if len(mag) < 2:
        nan = np.full_like(freqs, np.nan, dtype=float)
        return freqs, mag, mag_db, nan, nan, nan, 0.0, 0.0

    max_i_rel = np.argmax(mag[1:])
    max_i     = max_i_rel + 1
    Am        = mag[max_i]
    Fm        = freqs[max_i]

    if Am <= 0 or Fm <= 0:
        nan = np.full_like(freqs, np.nan, dtype=float)
        return freqs, mag, mag_db, nan, nan, nan, Am, Fm

    Fn    = freqs / Fm
    An    = mag / Am
    An_db = 20 * np.log10(An + 1e-12)

    return freqs, mag, mag_db, Fn, An, An_db, Am, Fm


def _compute_mean_spectrum(amp, sr, seg_dur=0.1, n_seg=40):
    """
    Extracts segments from audio array, computes normalized spectra,
    interpolates onto common Fn grid [1, 8] with 1000 points,
    and returns mean normalized amplitude in dB.

    Returns:
        (Fn_common: ndarray shape (1000,),
         mean_An_db: ndarray shape (1000,),
         stack: ndarray shape (n_valid_segs, 1000))
    """
    Fn_common = np.linspace(1.0, 8.0, 1000)

    segments, starts, seg_len = _ext_seg(
        amp, sr, seg_dur=seg_dur, n_seg=n_seg,
        threshold_r=0.05, max_tries_per_seg=20,
    )

    if len(segments) == 0:
        empty = np.full_like(Fn_common, np.nan)
        return Fn_common, empty, np.full((0, 1000), np.nan)

    interp_list = []

    for segment in segments:
        freqs, mag, mag_db, Fn, An, An_db, Am, Fm = _norm_spect(segment, sr)

        mask = (Fn >= 1.0) & (Fn <= 8.0)
        if np.sum(mask) < 2:
            continue

        Fn_trim    = Fn[mask]
        An_db_trim = An_db[mask]

        An_db_interp = np.interp(
            Fn_common,
            Fn_trim,
            An_db_trim,
            left=np.nan,
            right=np.nan,
        )
        interp_list.append(An_db_interp)

    if not interp_list:
        empty = np.full_like(Fn_common, np.nan)
        return Fn_common, empty, np.full((0, 1000), np.nan)

    stack      = np.stack(interp_list, axis=0)
    mean_An_db = np.nanmean(stack, axis=0)

    return Fn_common, mean_An_db, stack


# ── Main Analysis Function ─────────────────────────────────────────────────────

def analyse_segment_spectrogram(
    audio_file_path: str,
    segment_label: str = '',
    segment_id: str = '',
) -> tuple:
    """
    Runs full spectrogram and normalized spectrum analysis on an audio file.

    Produces a combined matplotlib figure with three panels:
        A. Full waveform of the audio
        B. Mean normalized spectrum (Fn 1–8) with 95% CI shading
        C. Mean normalized spectrum zoomed to octave (Fn 1–2)

    Args:
        audio_file_path: path to a WAV file (temp file from media_extractor)
        segment_label: label/rasa name for plot titles (optional)
        segment_id: segment id for plot titles (optional)

    Returns:
        (png_path: str | None, error: str | None)

        png_path is a path to a temp PNG file.
        The CALLER is responsible for deleting it after Gradio serves it.
        On failure returns (None, error_message).
    """
    try:
        import librosa
        import matplotlib
        matplotlib.use('Agg')   # non-interactive backend — must be set before pyplot
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError as e:
        _logger.error(f"Missing dependency: {e}")
        return None, (
            f"Missing required library: {e}. "
            "Ensure librosa and matplotlib are installed."
        )

    if not audio_file_path or not os.path.isfile(audio_file_path):
        return None, f"Audio file not found: {audio_file_path!r}"

    _logger.info(
        f"analyse_segment_spectrogram: {audio_file_path} "
        f"label={segment_label!r} id={segment_id!r}"
    )

    # ── Load audio ──────────────────────────────────────────────────
    try:
        amp, sr = librosa.load(audio_file_path, sr=22050, mono=True)
    except Exception as e:
        _logger.error(f"librosa.load failed: {e}")
        return None, f"Failed to load audio: {e}"

    if len(amp) == 0:
        return None, "Audio file is empty."

    # ── Compute normalized spectrum ─────────────────────────────────
    try:
        Fn_common, mean_An_db, stack = _compute_mean_spectrum(
            amp, sr, seg_dur=0.1, n_seg=40
        )
    except Exception as e:
        _logger.error(f"_compute_mean_spectrum failed: {e}")
        return None, f"Spectrum computation failed: {e}"

    # ── Compute 95% confidence interval ────────────────────────────
    try:
        if stack.shape[0] >= 2:
            valid_counts = np.sum(~np.isnan(stack), axis=0)
            std_vals     = np.nanstd(stack, axis=0)
            se_vals      = std_vals / np.sqrt(np.maximum(valid_counts, 1))
            ci_low       = mean_An_db - 1.96 * se_vals
            ci_high      = mean_An_db + 1.96 * se_vals
            has_ci       = True
        else:
            ci_low  = mean_An_db
            ci_high = mean_An_db
            has_ci  = False
    except Exception as e:
        _logger.warning(f"CI computation failed: {e}")
        ci_low  = mean_An_db
        ci_high = mean_An_db
        has_ci  = False

    # ── Build title string ──────────────────────────────────────────
    title_parts = []
    if segment_label:
        title_parts.append(segment_label)
    if segment_id:
        short_id = segment_id[:40] + "..." if len(segment_id) > 40 else segment_id
        title_parts.append(short_id)
    title_base = " — ".join(title_parts) if title_parts else "Segment"

    # ── Plot ────────────────────────────────────────────────────────
    try:
        # Dark theme to match the app's dark UI
        plt.style.use('dark_background')

        fig = plt.figure(figsize=(12, 10), facecolor='#1a1a2e')
        gs  = gridspec.GridSpec(
            3, 1,
            figure=fig,
            hspace=0.45,
            top=0.92,
            bottom=0.07,
            left=0.09,
            right=0.97,
        )

        accent   = '#7eb8f7'
        ci_color = '#3b82f6'
        grid_kw  = dict(alpha=0.2, color='#444466')

        # ── Panel A: Full waveform ──────────────────────────────────
        ax_a = fig.add_subplot(gs[0])
        t    = np.linspace(0, len(amp) / sr, len(amp), endpoint=False)

        ax_a.plot(t, amp, color=accent, linewidth=0.6, alpha=0.85)
        ax_a.set_xlabel("Time (s)", fontsize=9, color='#aaaacc')
        ax_a.set_ylabel("Amplitude", fontsize=9, color='#aaaacc')
        ax_a.set_title(
            f"A. Waveform — {title_base}",
            fontsize=10, color='#e0e0ff', pad=6,
        )
        ax_a.tick_params(colors='#888899', labelsize=8)
        ax_a.set_facecolor('#0f0f1a')
        for spine in ax_a.spines.values():
            spine.set_edgecolor('#2d2d4e')
        ax_a.grid(**grid_kw)

        # ── Panel B: Mean normalized spectrum Fn 1–8 with CI ───────
        ax_b    = fig.add_subplot(gs[1])
        valid_b = ~np.isnan(mean_An_db)

        if np.any(valid_b):
            ax_b.plot(
                Fn_common[valid_b], mean_An_db[valid_b],
                color=accent, linewidth=1.8,
                label="Mean normalized amplitude",
            )
            if has_ci:
                ax_b.fill_between(
                    Fn_common[valid_b],
                    ci_low[valid_b],
                    ci_high[valid_b],
                    alpha=0.25,
                    color=ci_color,
                    label="95% CI",
                )
        else:
            ax_b.text(
                0.5, 0.5,
                "Insufficient audio data for spectrum analysis.\n"
                "(Audio may be too short or too quiet.)",
                transform=ax_b.transAxes,
                ha='center', va='center',
                color='#888899', fontsize=9,
            )

        ax_b.set_xlabel("Frequency ratio Fn = F / Fm", fontsize=9, color='#aaaacc')
        ax_b.set_ylabel("Mean normalized amplitude (dB)", fontsize=9, color='#aaaacc')
        ax_b.set_title(
            "B. Normalized Spectrum (Fn 1–8) with 95% CI",
            fontsize=10, color='#e0e0ff', pad=6,
        )
        ax_b.set_xlim(1, 8)
        ax_b.set_ylim(-50, 5)
        ax_b.tick_params(colors='#888899', labelsize=8)
        ax_b.set_facecolor('#0f0f1a')
        for spine in ax_b.spines.values():
            spine.set_edgecolor('#2d2d4e')
        ax_b.grid(**grid_kw)
        if has_ci:
            ax_b.legend(
                fontsize=8,
                facecolor='#1a1a2e',
                edgecolor='#2d2d4e',
                labelcolor='#aaaacc',
            )

        # ── Panel C: Zoomed octave Fn 1–2 ──────────────────────────
        ax_c     = fig.add_subplot(gs[2])
        mask_12  = (Fn_common >= 1.0) & (Fn_common <= 2.0)
        Fn_oct   = Fn_common[mask_12]
        An_oct   = mean_An_db[mask_12]
        valid_c  = ~np.isnan(An_oct)

        if np.any(valid_c):
            ax_c.plot(
                Fn_oct[valid_c], An_oct[valid_c],
                color='#f59e0b', linewidth=1.8,
                label="Mean (Fn 1–2)",
            )
            if has_ci:
                ci_low_oct  = ci_low[mask_12]
                ci_high_oct = ci_high[mask_12]
                ax_c.fill_between(
                    Fn_oct[valid_c],
                    ci_low_oct[valid_c],
                    ci_high_oct[valid_c],
                    alpha=0.25,
                    color='#f59e0b',
                    label="95% CI",
                )
        else:
            ax_c.text(
                0.5, 0.5,
                "No spectrum data in Fn 1–2 range.",
                transform=ax_c.transAxes,
                ha='center', va='center',
                color='#888899', fontsize=9,
            )

        ax_c.set_xlabel("Frequency ratio Fn = F / Fm", fontsize=9, color='#aaaacc')
        ax_c.set_ylabel("Mean normalized amplitude (dB)", fontsize=9, color='#aaaacc')
        ax_c.set_title(
            "C. Normalized Spectrum — Zoomed Octave (Fn 1–2)",
            fontsize=10, color='#e0e0ff', pad=6,
        )
        ax_c.set_xlim(1.0, 2.0)
        ax_c.set_ylim(-35, 5)
        ax_c.tick_params(colors='#888899', labelsize=8)
        ax_c.set_facecolor('#0f0f1a')
        for spine in ax_c.spines.values():
            spine.set_edgecolor('#2d2d4e')
        ax_c.grid(**grid_kw)
        if has_ci:
            ax_c.legend(
                fontsize=8,
                facecolor='#1a1a2e',
                edgecolor='#2d2d4e',
                labelcolor='#aaaacc',
            )

        # ── Super-title ─────────────────────────────────────────────
        fig.suptitle(
            f"Spectral Analysis — {title_base}",
            fontsize=12,
            color='#ffffff',
            y=0.97,
        )

    except Exception as e:
        _logger.error(f"Plot construction failed: {e}", exc_info=True)
        try:
            plt.close('all')
        except Exception:
            pass
        return None, f"Plot construction failed: {e}"

    # ── Save to temp PNG ────────────────────────────────────────────
    png_path = None
    try:
        fd, png_path = tempfile.mkstemp(
            suffix='.png',
            prefix=f'natak_spect_{segment_id[:20] if segment_id else "seg"}_',
        )
        os.close(fd)

        fig.savefig(
            png_path,
            dpi=130,
            bbox_inches='tight',
            facecolor=fig.get_facecolor(),
        )
        _logger.info(f"Spectrogram saved: {png_path}")
        return png_path, None

    except Exception as e:
        _logger.error(f"savefig failed: {e}")
        if png_path and os.path.exists(png_path):
            try:
                os.unlink(png_path)
            except Exception:
                pass
        return None, f"Failed to save spectrogram image: {e}"

    finally:
        try:
            plt.close(fig)
        except Exception:
            pass
