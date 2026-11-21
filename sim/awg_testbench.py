"""
AWG Analog Stage SPICE Testbench (uses KiCad 10's built-in ngspice.dll)
Edit the parameters in the CONFIG section below and run:
    .\sim\run_sim.ps1
"""

import ctypes
import os
import numpy as np
from PIL import Image, ImageDraw

# ==============================================================================
# CONFIG — Edit these values to experiment!
# ==============================================================================
HIGH_GAIN   = True      # False = Low Gain (1k / 3.3pF), True = High Gain (10k / 1pF)
FILTER_ON   = True      # False = Bypass 3MHz filter,   True = 3rd-order SK enabled
LOAD_OHMS   = "1Meg"    # "1Meg" for Hi-Z scope, "50" for 50-ohm terminated load
CABLE_PF    = "15p"     # Coax/probe capacitance

DAC_FS_MA   = 19.2      # Full-scale DAC current (mA), R8=2k -> ~19.2 mA
DAC_FS_MSPS = 20.0      # DAC update rate (MS/s) for stepped sine
SIG_FREQ_MHZ = 1.0      # Test waveform frequency (MHz)

# Component values (matching AWG.kicad_sch)
R1_VAL  = "1k"
R3_VAL  = "1k"
R10_VAL = "50"
R11_VAL = "50"
R9_VAL  = "50"

# Low gain & High gain feedback networks
RFB_LO, CFB_LO, RG_LO = "1k",  "3.3p", "1k"
RFB_HI, CFB_HI, RG_HI = "10k", "1p",   "10k"

# 3rd-order Sallen-Key filter (U6)
R16_VAL, C10_VAL = "220", "220p"
R15_VAL, C9_VAL  = "1k",  "100p"
R14_VAL, C11_VAL = "1k",  "22p"
# ==============================================================================

KICAD_BIN = r"C:\Program Files\KiCad\10.0\bin"
os.add_dll_directory(KICAD_BIN)
ng = ctypes.CDLL(os.path.join(KICAD_BIN, "ngspice.dll"))

SendChar = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
SendStat = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
ControlledExit = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)

logs = []
@SendChar
def _cb_char(msg, ident, userdata):
    logs.append(msg.decode(errors="replace"))
    return 0

@SendStat
def _cb_stat(msg, ident, userdata):
    return 0

@ControlledExit
def _cb_exit(status, immediate, quit_exit, ident, userdata):
    return 0

ng.ngSpice_Init(_cb_char, _cb_stat, _cb_exit, None, None, None, None)

class Complex(ctypes.Structure):
    _fields_ = [("real", ctypes.c_double), ("imag", ctypes.c_double)]

class VectorInfo(ctypes.Structure):
    _fields_ = [
        ("v_name", ctypes.c_char_p),
        ("v_type", ctypes.c_int),
        ("v_flags", ctypes.c_short),
        ("v_realdata", ctypes.POINTER(ctypes.c_double)),
        ("v_compdata", ctypes.POINTER(Complex)),
        ("v_length", ctypes.c_int),
    ]

ng.ngGet_Vec_Info.argtypes = [ctypes.c_char_p]
ng.ngGet_Vec_Info.restype = ctypes.POINTER(VectorInfo)
ng.ngSpice_Command.argtypes = [ctypes.c_char_p]
ng.ngSpice_Command.restype = ctypes.c_int
ng.ngSpice_Circ.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
ng.ngSpice_Circ.restype = ctypes.c_int

def run_netlist(lines):
    logs.clear()
    ng.ngSpice_Command(b"destroy all")
    ng.ngSpice_Command(b"remcirc")
    c_lines = (ctypes.c_char_p * (len(lines) + 1))()
    for i, l in enumerate(lines):
        c_lines[i] = l.encode()
    c_lines[len(lines)] = None
    if ng.ngSpice_Circ(c_lines) != 0:
        raise RuntimeError("ngSpice_Circ failed:\n" + "\n".join(logs))
    if ng.ngSpice_Command(b"run") != 0:
        raise RuntimeError("run failed:\n" + "\n".join(logs))

def get_vec(name):
    vi = ng.ngGet_Vec_Info(name.encode()).contents
    n = vi.v_length
    if vi.v_realdata:
        return np.ctypeslib.as_array(vi.v_realdata, shape=(n,)).copy()
    arr = np.ctypeslib.as_array(vi.v_compdata, shape=(n,))
    return np.array([c["real"] + 1j * c["imag"] for c in arr])

# AD8065 behavioural model (145 MHz GBW, 180 V/us slew rate, +/-11.8 V rail clamp)
AD8065_SUBCKT = [
    ".subckt AD8065 inp inn vcc vee out",
    "Cin_p inp 0 4.5p",
    "Cin_n inn 0 4.5p",
    "Cin_d inp inn 2.1p",
    "G_slew 0 n_pole value = { 19.76u * tanh( (V(inp)-V(inn)) * 1e5 / (19.76u * 1e9) ) }",
    "R_pole n_pole 0 1G",
    "C_pole n_pole 0 0.1098p",
    "E_clamp n_out_int 0 value = { 11.8 * tanh(V(n_pole) / 11.8) }",
    "R_out n_out_int out 0.5",
    ".ends AD8065",
]

rfb, cfb, rg = (RFB_HI, CFB_HI, RG_HI) if HIGH_GAIN else (RFB_LO, CFB_LO, RG_LO)
mode_str = f"{'High Gain (10x)' if HIGH_GAIN else 'Low Gain (1x)'} | {'3MHz Filter ON' if FILTER_ON else 'Bypass'} | Load={LOAD_OHMS}"

def stage_netlist(src_a, src_b, analysis_cmd):
    return [
        "* AWG Analog Stage Testbench",
        *AD8065_SUBCKT,
        "V_p vcc 0 DC 12",
        "V_n vee 0 DC -12",
        f"I_a 0 iouta {src_a}",
        f"I_b 0 ioutb {src_b}",
        f"R10 iouta 0 {R10_VAL}",
        f"R11 ioutb 0 {R11_VAL}",
        f"R1 iouta u3_inn {R1_VAL}",
        f"R3 ioutb u3_inp {R3_VAL}",
        f"R_g u3_inp 0 {rg}",
        f"R_fb u3_inn vout_amp {rfb}",
        f"C_fb u3_inn vout_amp {cfb}",
        "X_u3 u3_inp u3_inn vcc vee vout_amp AD8065",
        f"R16 vout_amp sk1 {R16_VAL}",
        f"C10 sk1 0 {C10_VAL}",
        f"R15 sk1 sk2 {R15_VAL}",
        f"C9 sk2 vout_filt {C9_VAL}",
        f"R14 sk2 u6_inp {R14_VAL}",
        f"C11 u6_inp 0 {C11_VAL}",
        "X_u6 u6_inp vout_filt vcc vee vout_filt AD8065",
        f"R9 {'vout_filt' if FILTER_ON else 'vout_amp'} vout_bnc {R9_VAL}",
        f"R_load vout_bnc 0 {LOAD_OHMS}",
        f"C_cable vout_bnc 0 {CABLE_PF}",
        analysis_cmd,
        ".end",
    ]

# 1) AC Sweep
run_netlist(stage_netlist(f"DC {DAC_FS_MA/2}m AC 1", f"DC {DAC_FS_MA/2}m AC -1", ".ac dec 100 10k 100Meg"))
freq = np.real(get_vec("frequency"))
v_ac = get_vec("v(vout_bnc)")
mag_db = 20 * np.log10(np.abs(v_ac) / np.abs(v_ac[0]))
idx_3db = np.where(mag_db <= -3.0)[0]
f3db = freq[idx_3db[0]] if len(idx_3db) > 0 else np.nan
print(f"Mode: {mode_str}")
print(f"AC: f_-3dB = {f3db/1e6:.2f} MHz | Peak = {np.max(mag_db):+.2f} dB")

# 2) Stepped Sine Transient
fs = DAC_FS_MSPS * 1e6
f_sig = SIG_FREQ_MHZ * 1e6
t_end = 2.5 / f_sig
dt = 1.0 / fs
n_steps = int(t_end / dt)
i_half = (DAC_FS_MA * 1e-3) / 2.0
pts_a, pts_b = [], []
for k in range(n_steps):
    t0 = k * dt
    t1 = (k + 1) * dt - 0.5e-9
    s = np.sin(2 * np.pi * f_sig * t0)
    pts_a.append(f"{t0:.4e} {i_half*(1+s):.6e} {t1:.4e} {i_half*(1+s):.6e}")
    pts_b.append(f"{t0:.4e} {i_half*(1-s):.6e} {t1:.4e} {i_half*(1-s):.6e}")

run_netlist(stage_netlist("PWL(" + " ".join(pts_a) + ")", "PWL(" + " ".join(pts_b) + ")", f".tran 1n {t_end:.4e}"))
t_sine = get_vec("time")
v_sine = get_vec("v(vout_bnc)")
mask_s = t_sine >= (1.0 / f_sig)
print(f"Sine ({SIG_FREQ_MHZ} MHz @ {DAC_FS_MSPS} MS/s): Vmin={np.min(v_sine[mask_s]):+.2f} V, Vmax={np.max(v_sine[mask_s]):+.2f} V, Vpp={np.ptp(v_sine[mask_s]):.2f} V")

# 3) Square Wave Step Response (500 kHz, 2 ns edges)
period = 1.0 / f_sig
i_hi = f"{DAC_FS_MA}m"
run_netlist(stage_netlist(
    f"PULSE(0 {i_hi} 100n 2n 2n {period/2 - 2e-9:.4e} {period:.4e})",
    f"PULSE({i_hi} 0 100n 2n 2n {period/2 - 2e-9:.4e} {period:.4e})",
    f".tran 0.5n {2.2*period:.4e}",
))
t_sq = get_vec("time")
v_sq = get_vec("v(vout_bnc)")
print(f"Square ({SIG_FREQ_MHZ} MHz): Vmin={np.min(v_sq):+.2f} V, Vmax={np.max(v_sq):+.2f} V, Vpp={np.ptp(v_sq):.2f} V")

# Plot 3 clean light-mode panels
from PIL import ImageFont

def load_font(size):
    for p in [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

font_title = load_font(18)
font_sub   = load_font(15)
font_tick  = load_font(12)

W, H = 1120, 1020
img = Image.new("RGB", (W, H), (255, 255, 255))
draw = ImageDraw.Draw(img)
draw.text((70, 14), f"AWG Simulation  |  {mode_str}", fill=(17, 24, 39), font=font_title)

def plot_panel(x0, y0, pw, ph, title, x_arr, y_arr, line_col, x_log=False, ylim=None, x_ticks=None, y_ticks=None, x_unit=""):
    draw.rectangle([x0, y0, x0+pw, y0+ph], fill=(250, 251, 252), outline=(180, 188, 200), width=1)
    draw.text((x0, y0 - 24), title, fill=(17, 24, 39), font=font_sub)

    xmin, xmax = float(np.min(x_arr)), float(np.max(x_arr))
    if x_log:
        xmin, xmax = np.log10(xmin), np.log10(xmax)
    ymin, ymax = ylim if ylim else (float(np.min(y_arr))*1.12 - 0.5, float(np.max(y_arr))*1.12 + 0.5)

    # Grid & Y ticks
    if y_ticks is None:
        step = max(1.0, round((ymax - ymin) / 4.0, 1))
        y_ticks = np.arange(np.ceil(ymin / step) * step, ymax + 1e-9, step)
    for yv in y_ticks:
        if ymin <= yv <= ymax:
            gy = y0 + int((ymax - yv) / (ymax - ymin) * ph)
            col = (209, 213, 219) if abs(yv) < 1e-6 else (229, 231, 235)
            draw.line([x0, gy, x0+pw, gy], fill=col, width=1)
            draw.text((x0 - 54, gy - 8), f"{yv:g}", fill=(75, 85, 99), font=font_tick)

    # Grid & X ticks
    if x_ticks is None:
        x_ticks = np.linspace(xmin, xmax, 5)
    for xv, lbl in (x_ticks if isinstance(x_ticks[0], tuple) else [(v, f"{v:g}{x_unit}") for v in x_ticks]):
        xx = np.log10(xv) if x_log else xv
        if xmin <= xx <= xmax:
            gx = x0 + int((xx - xmin) / (xmax - xmin) * pw)
            draw.line([gx, y0, gx, y0+ph], fill=(229, 231, 235), width=1)
            draw.text((gx - 16, y0 + ph + 6), lbl, fill=(75, 85, 99), font=font_tick)

    # Curve
    pts = []
    for xv, yv in zip(x_arr, y_arr):
        xx = np.log10(xv) if x_log else xv
        px = x0 + int((xx - xmin) / (xmax - xmin) * pw)
        yc = max(ymin, min(ymax, float(yv)))
        py = y0 + int((ymax - yc) / (ymax - ymin) * ph)
        pts.append((px, py))
    if len(pts) > 1:
        draw.line(pts, fill=line_col, width=3)

bode_xticks = [(1e4, "10 kHz"), (1e5, "100 kHz"), (1e6, "1 MHz"), (3e6, "3 MHz"), (1e7, "10 MHz"), (1e8, "100 MHz")]
bode_yticks = [0, -3, -20, -40, -60]
plot_panel(70, 75,  990, 240, f"1. Frequency Response (dB)  |  -3 dB cutoff = {f3db/1e6:.2f} MHz",
           freq, mag_db, (37, 99, 235), x_log=True, ylim=(-60.0, 6.0), x_ticks=bode_xticks, y_ticks=bode_yticks)

plot_panel(70, 395, 990, 240, f"2. Sine Wave ({SIG_FREQ_MHZ} MHz @ {DAC_FS_MSPS} MS/s)  |  {np.ptp(v_sine[mask_s]):.2f} Vpp",
           t_sine*1e6, v_sine, (5, 150, 105), x_unit=" us")

plot_panel(70, 715, 990, 240, f"3. Square Wave ({SIG_FREQ_MHZ} MHz, 2 ns edges)  |  {np.ptp(v_sq):.2f} Vpp",
           t_sq*1e6, v_sq, (217, 119, 6), x_unit=" us")

out_png = os.path.join(os.path.dirname(__file__), "awg_sim_results.png")
with open(out_png, "wb") as f:
    img.save(f, "PNG")
print(f"Saved: {out_png}")
