# AWG-PCB — Test Points & Board Bring-Up Guide

> **Purpose:** Minimalist test-point selection (exact KiCad 10 symbols and footprints), step-by-step **pre-FPGA** hardware bring-up checklist, and post-FPGA 100 MSPS signal verification.
>
> **Related Docs:** [Major Architectural Decisions](./ARCHITECTURAL_DECISIONS.md) · *Rule numbers reference Eric Bogatin, Signal and Power Integrity — Simplified, Appendix A.*

---

## 1. Exact KiCad 10 Symbols & Footprints to Add

Only **7 test points** (6 signals + 1 dedicated ground-spring partner pad for `CLK`, plus optional `TP_VOUT_AMP`) are needed. Everything else can be probed directly on existing 0805 / connector pads.

| Ref | Net | KiCad 10 Symbol | KiCad 10 Footprint | Physical Placement & Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`TP_GND1`** | `GND` | `Connector:TestPoint` | `TestPoint:TestPoint_Loop_D2.50mm_Drill1.0mm` *(or `TestPoint:TestPoint_Keystone_5005-5009_Compact`)* | Near `U1` / `J2`–`J3` (digital GND clip point). Works with a Keystone loop **or** a scrap bent resistor lead / 1-pin header. |
| **`TP_GND2`** | `GND` | `Connector:TestPoint` | `TestPoint:TestPoint_Loop_D2.50mm_Drill1.0mm` *(or `TestPoint:TestPoint_Keystone_5005-5009_Compact`)* | Near `U3` / `U6` / `U4` secondary side (analog & power GND clip point). |
| **`TP_+12V`** | `+12V` | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.5mm` | After `FB3`, accessible near `U4` secondary / `U3`. Zero BOM cost. |
| **`TP_-12V`** | `-12V` | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.5mm` | After `FB2`, accessible near `U4` secondary / `U3`. Zero BOM cost. |
| **`TP_+3V3`** | `+3.3V` | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.5mm` | Right near `U5` output / `C12` for DC + AC-coupled LDO stability check. |
| **`TP_CLK`** | `/CLK` | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.0mm` | **Must be flush SMD, placed directly inline on the `/CLK` trace near `U1.28` with ZERO branch stub** (*Rule 7*). |
| **`TP_CLK_GND`** | `GND` | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.0mm` | Place **2.0–2.5 mm** directly beside `TP_CLK` with a short via straight to `In1.Cu` GND — lets you use a **scope ground spring** for 100 MHz clock probing. |
| **`TP_VOUT_AMP`** *(Optional)* | `/VOUT_AMP` | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.0mm` | Inline on `U3` pin 6 output (splits DAC+`U3` from `U6`+`K2`+BNC during debug). |

> **Silkscreen tip:** Put the net name (`+12V`, `-12V`, `+3V3`, `CLK`, `GND`) directly on `F.SilkS` beside each pad so you don't need the schematic open at the lab bench.

### Existing Pads You Can Probe "For Free" (No Extra Test Point Needed)
- **`V_IN` & Primary Isolated `GND`:** `J1` / `J4` banana jacks and `C8` (0805)
- **`REFIO` (+1.20 V DAC reference):** `C3` pad 1 (0805)
- **`DVDD` (+3.3 V after `FB1`):** `C16` pad 1 or `FB1` (0805)
- **`IOUTA` / `IOUTB`:** `R10` pad 2 and `R11` pad 2 (big 0805 pads right next to GND!)
- **`GAIN_SEL` / `FILT_EN`:** `J3` header pins 8 & 10 (or `R6` / `R13`)
- **`VOUT_FILT`:** `C20` pad 2 (0805)
- **Final Output (`VOUT_OUT`):** `J5` BNC connector

### Where NOT to Place Test Points (or Touch a Scope Probe)
- **Never** add test points on `U3`'s `-IN` (`Net-(U3--IN)`) or `+IN` (`Net-(U3-+IN)`) summing nodes, or inside `U6`'s internal Sallen-Key RC nodes (`R15`/`R14`/`C20`/`C22`). Even an unprobed pad adds parasitic capacitance, and a 10× passive probe (10–15 pF) on `U3` pin 2 will make the `AD8065` oscillate.

---

## 2. Pre-FPGA Bring-Up Checklist (Run BEFORE Plugging In the FPGA!)

> **Goal:** Guarantee power rails, galvanic isolation, DAC reference, and op-amp DC bias are 100% healthy **before** exposing your FPGA's 3.3 V I/O pins to the PCB.

### Step 1 — Cold Continuity Checks (Power OFF, Multimeter in Resistance / Continuity Mode)
Check that **no rail is dead-shorted** before applying voltage:
- [ ] `J1` (`V_IN`) ↔ `J4` (`GND_PRI`): **> 10 kΩ** *(charges `C8` briefly, then rises)*
- [ ] `TP_+12V` ↔ `TP_GND2`: **> 1 kΩ**
- [ ] `TP_-12V` ↔ `TP_GND2`: **> 1 kΩ**
- [ ] `TP_+3V3` ↔ `TP_GND1`: **> 500 Ω**
- [ ] **Galvanic Isolation Check:** `J4` (`GND_PRI`) ↔ `TP_GND2` (secondary `GND`): **Open circuit (`OL` / > 10 MΩ)**! If shorted, **STOP** — `U4` footprint/pinout or copper pour has bridged the isolation barrier.
- [ ] Check `J2` & `J3` pins `1–4, 7–10` ↔ `TP_+12V` and `TP_-12V`: **Open circuit** (ensures ±12 V can never back-feed into the 3.3 V FPGA!).

### Step 2 — Current-Limited First Power-On
- Set bench power supply to **12.0 V** (or `U4`'s nominal input voltage) with **current limit = 150–200 mA** (no-load quiescent draw should be ~40–80 mA with relays off).
- Connect to `J1` (`V_IN`) and `J4` (`GND_PRI`).
- [ ] Current draw stays **< 100 mA** and does not hit current limit.
- [ ] Touch-check (or thermal camera) `U4`, `U5`, `U1`, `U3`, `U6`: nothing gets hot immediately. *(Note: `U5` `LM1117-3.3` will warm up slightly over 1–2 minutes under ~0.6 W dissipation — warm is normal, burning-hot > 85 °C is not.)*

### Step 3 — Power Rail Verification (DC + Scope AC Ripple)
Use **`TP_GND2`** as reference for all secondary measurements (and **`J4`** only for primary `V_IN`):

| Signal | Where to Probe | Pass Criteria (DC) | Pass Criteria (Oscilloscope, AC-Coupled, 20 MHz BW) |
| :--- | :--- | :--- | :--- |
| **Primary `V_IN`** | `C8` pad 1 (ref `J4`) | $V_{\text{PSU}} - 0.3\text{ to }0.5\text{ V}$ | Clean DC (confirms `F1` & `D2` OK) |
| **`+12V`** | `TP_+12V` (ref `TP_GND2`) | **$+11.4\text{ V}$ to $+12.6\text{ V}$** | Ripple **< 50 mVpp** (check for `U4` switching spikes) |
| **`-12V`** | `TP_-12V` (ref `TP_GND2`) | **$-12.6\text{ V}$ to $-11.4\text{ V}$** | Ripple **< 50 mVpp** |
| **`+3.3V` (`AVDD`)** | `TP_+3V3` (ref `TP_GND1`) | **$+3.23\text{ V}$ to $+3.37\text{ V}$** | **Flat (< 15 mVpp), NO oscillation!** *(Critical check for `LM1117` + MLCC `C12` stability!)* |
| **`DVDD`** | `C16` pad 1 (ref `TP_GND1`) | **$+3.23\text{ V}$ to $+3.37\text{ V}$** | Matches `+3.3V` within ~10 mV |

### Step 4 — Unclocked DAC & Analog DC Bias Sanity Check (Still No FPGA!)
| Signal | Where to Probe | Expected Value | What a Failure Means |
| :--- | :--- | :--- | :--- |
| **DAC `REFIO`** | `C3` pad 1 | **$+1.20\text{ V} \pm 0.05\text{ V}$** | `U1` unpowered, bad solder joint, or `SLEEP` pin high. |
| **`IOUTA` / `IOUTB`** | `R10` pad 2 & `R11` pad 2 | Both within **$0.0\text{ V}$ to $+0.96\text{ V}$** (sum $\approx 0.96\text{ V}$) | Confirms DAC current mirror (`R8 = 2 kΩ`) and 50 Ω terminations are alive. |
| **`VOUT_AMP` (DC)** | `TP_VOUT_AMP` (or `U3.6`) | Within **$\pm 1.0\text{ V}$** (Low Gain) and **no high-freq oscillation** on scope! | If pinned to $\pm 11.8\text{ V}$ or oscillating at 20–100 MHz, fix `U3`/`K1` before plugging in FPGA. |
| **Relay Dry Test** | Briefly tie `J3.8` (`GAIN_SEL`) or `J3.10` (`FILT_EN`) to `TP_+3V3` via a **1 kΩ resistor** | Audible click from `K1`/`K2`; current rises ~8–10 mA per relay; `Q1`/`Q2` drain drops from `12 V → ~0 V`. | Verifies `Q1`/`Q2`, `D1`/`D3` flyback diodes, and `K1`/`K2` coils work cleanly. |
| **PMOD Idle Voltage** | `J2` & `J3` signal pins | **$\le 3.3\text{ V}$** (never $> 3.6\text{ V}$!) | **FINAL SAFETY GATE before plugging in the FPGA!** |

---

## 3. Post-FPGA Bring-Up: Most Crucial Signals to Check at 100 MSPS

Once every box in **Section 2** passes, power off, connect `J2`/`J3` to your FPGA (with FPGA outputs configured to **LVCMOS33, SLOW slew, 4–8 mA drive**), and verify in this order:

| Priority | Signal | Probe Point | How to Probe | What to Verify |
| :---: | :--- | :--- | :--- | :--- |
| **1 (Most Critical)** | **`CLK` (100 MHz)** | `TP_CLK` + `TP_CLK_GND` | **10× probe with short ground spring** (never alligator clip!), $\ge 200\text{ MHz}$ scope BW | • Clean 100 MHz waveform, **0 V → 3.3 V** swing (if peak is < 2.2 V or triangle-shaped, check if FPGA PMOD has **200 Ω** protection resistors!).<br>• Monotonic rising edge (**no ringing crossing 1.0–2.0 V threshold** that causes double-clocking). |
| **2** | **DAC Raw Output (`IOUTA` / `IOUTB`)** | `R10` pad 2 & `R11` pad 2 | 10× probe, drive a slow **1 MHz full-scale sine** at 100 MSPS | • Complementary $0\text{ to }+0.96\text{ V}$ sines, $180^\circ$ out of phase.<br>• **Zero missing codes / bit-swap jumps** (confirms `D0`–`D11` FPGA pin mapping & setup/hold timing!). |
| **3** | **Diff-Amp Output (`VOUT_AMP`)** | `TP_VOUT_AMP` | 10× probe, Hi-Z, test **Low Gain (1×)** then **High Gain (6.2×)** | • **Low Gain:** $\approx 1.83\text{ V}_{pp}$ centered at 0 V.<br>• **High Gain:** $\approx 11.3\text{ V}_{pp}$ centered at 0 V.<br>• Check a **1 MHz square wave** for clean settling (excessive overshoot/ringing means parasitic C at `U3` `-IN` / `K1`). |
| **4** | **Filter Output (`VOUT_FILT`)** | `C20` pad 2 (or `J5` BNC) | Compare `FILT_EN = 0` (Bypass) vs. `FILT_EN = 1` (3 MHz SK) | • Smooth 1–3 MHz sine with minimal stair-stepping.<br>• Check **FFT on scope at 100 MHz** to see how much 100 MHz clock feedthrough leaks past `U6`. |
| **5** | **Final BNC Output (`J5`)** | Coax cable directly to oscilloscope | Test **1 MΩ** input vs. **50 Ω** scope input | • Voltage drops by exactly **50%** into 50 Ω load (confirms `R9 = 50 Ω` and clean launch).<br>• Sweep sine frequency up to 5 MHz (High Gain) / 20 MHz (Low Gain) to verify slew-rate limit and distortion. |
