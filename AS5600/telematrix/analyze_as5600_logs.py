#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze AS5600 + servo CSV logs produced by as5600_servo_dual_test*.py
- Inputs: follow_log.csv, sweep_log.csv (columns: t_s,mode,servo_deg,as5600_deg,multi_deg,MD,ML,MH,i2c_port)
- Outputs: console summary + optional summary CSV

Usage:
  python analyze_as5600_logs.py --follow follow_log.csv --sweep sweep_log.csv --out summary.csv
"""

import csv, argparse, math, statistics as stats
from collections import defaultdict

def read_csv(path):
    rows=[]
    with open(path, newline="") as f:
        r=csv.DictReader(f)
        for d in r:
            # robust cast (empty -> None)
            def f2(x):
                if x is None or x=="":
                    return None
                try: return float(x)
                except: return None
            def i2(x):
                if x is None or x=="":
                    return None
                try: return int(x)
                except: return None
            rows.append({
                "t": f2(d.get("t_s")),
                "mode": d.get("mode",""),
                "servo": f2(d.get("servo_deg")),
                "as5600": f2(d.get("as5600_deg")),
                "multi": f2(d.get("multi_deg")),
                "MD": i2(d.get("MD")),
                "ML": i2(d.get("ML")),
                "MH": i2(d.get("MH")),
                "port": i2(d.get("i2c_port")),
            })
    return rows

def frac_true(vals):
    ok=[v for v in vals if v is not None]
    if not ok: return 0.0
    return sum(1 for v in ok if v==1)/len(ok)

def basic_stats(rows, name):
    n=len(rows)
    tspan=(rows[-1]["t"]-rows[0]["t"]) if n>=2 and rows[0]["t"] is not None and rows[-1]["t"] is not None else None
    md=frac_true([r["MD"] for r in rows])
    ml=frac_true([r["ML"] for r in rows])
    mh=frac_true([r["MH"] for r in rows])
    print(f"\n=== {name}: basic ===")
    print(f"N={n}  duration={tspan:.2f}s" if tspan else f"N={n}")
    print(f"MD=1 ratio={md*100:.2f}%   ML=1={ml*100:.3f}%   MH=1={mh*100:.3f}%")

def linreg(x, y):
    # y ≈ k*x + b
    xs=[v for v in x]
    ys=[v for v in y]
    n=len(xs)
    sx=sum(xs); sy=sum(ys)
    sxx=sum(v*v for v in xs); sxy=sum(xs[i]*ys[i] for i in range(n))
    denom=n*sxx - sx*sx
    if n<2 or abs(denom)<1e-12:
        return None
    k=(n*sxy - sx*sy)/denom
    b=(sy - k*sx)/n
    # R^2
    ybar=sy/n
    ss_tot=sum((v-ybar)*(v-ybar) for v in ys)
    ss_res=sum((ys[i] - (k*xs[i]+b))**2 for i in range(n))
    r2=1.0 - (ss_res/ss_tot if ss_tot>0 else 0.0)
    rmse=math.sqrt(ss_res/n)
    mae =sum(abs(ys[i] - (k*xs[i]+b)) for i in range(n))/n
    return k,b,r2,rmse,mae

def analyze_follow(rows, assume_scale=0.5, assume_bias=0.0):
    # where both servo and as5600 are present
    data=[r for r in rows if r["servo"] is not None and r["as5600"] is not None]
    if not data:
        print("\n[follow] no data rows.")
        return
    # control error: servo_cmd - (as*scale + bias)
    errs=[(r["servo"] - (r["as5600"]*assume_scale + assume_bias)) for r in data]
    mean_err = stats.fmean(errs)
    std_err  = stats.pstdev(errs) if len(errs)>1 else 0.0

    # short-term noise estimate: detrend by moving median on as5600
    asv=[r["as5600"] for r in data]
    win=max(3, min(31, len(asv)//50))  # ~2% of length
    med=[]
    for i in range(len(asv)):
        j0=max(0, i-win//2); j1=min(len(asv), i+win//2+1)
        xs=sorted(asv[j0:j1]); med.append(xs[len(xs)//2])
    resid=[asv[i]-med[i] for i in range(len(asv))]
    resid_rms=math.sqrt(sum(v*v for v in resid)/len(resid))

    print("\n=== follow: controller consistency ===")
    print(f"assume scale={assume_scale:.6f}, bias={assume_bias:.6f}")
    print(f"servo_cmd - (as*scale+bias):  mean={mean_err:.3f}°, std={std_err:.3f}°")
    print(f"AS5600 short-term residual RMS (rough): {resid_rms:.3f}°")

def analyze_sweep(rows):
    # keep rows with both values
    data=[r for r in rows if r["servo"] is not None and r["as5600"] is not None]
    if len(data)<10:
        print("\n[sweep] not enough paired samples.")
        return
    xs=[r["as5600"] for r in data]
    ys=[r["servo"]  for r in data]
    fit=linreg(xs, ys)   # servo ≈ k*as + b
    if fit is None:
        print("\n[sweep] regression failed.")
        return
    k,b,r2,rmse,mae=fit
    print("\n=== sweep: mapping servo ≈ k*as5600 + b ===")
    print(f"k={k:.6f}, b={b:.3f}, R^2={r2:.6f}, RMSE={rmse:.3f}°, MAE={mae:.3f}°")

    # hysteresis: split by sign of d(servo)/dt
    ups=[]; downs=[]
    for i in range(1,len(data)):
        if data[i-1]["t"] is None or data[i]["t"] is None: continue
        if data[i]["servo"] is None or data[i-1]["servo"] is None: continue
        if data[i]["as5600"] is None: continue
        dv=data[i]["servo"] - data[i-1]["servo"]
        if dv>0: ups.append((data[i]["as5600"], data[i]["servo"]))
        elif dv<0: downs.append((data[i]["as5600"], data[i]["servo"]))
    if len(ups)>5 and len(downs)>5:
        k_u,b_u,_,_,_=linreg([x for x,_ in ups],[y for _,y in ups])
        k_d,b_d,_,_,_=linreg([x for x,_ in downs],[y for _,y in downs])
        mid_as=(min(xs)+max(xs))/2.0
        sep=abs((k_u*mid_as+b_u) - (k_d*mid_as+b_d))
        print(f"Hysteresis (up vs down @mid-as): {sep:.3f}°  "
              f"(k_up={k_u:.6f}, b_up={b_u:.3f}; k_dn={k_d:.6f}, b_dn={b_d:.3f})")
    else:
        print("Hysteresis: insufficient ups/downs to estimate.")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--follow", required=False, default="follow_log.csv")
    ap.add_argument("--sweep",  required=False, default="sweep_log.csv")
    ap.add_argument("--scale",  type=float, default=0.5)
    ap.add_argument("--bias",   type=float, default=0.0)
    ap.add_argument("--out",    default="")
    args=ap.parse_args()

    if args.follow:
        fr=read_csv(args.follow)
        basic_stats(fr, "follow")
        analyze_follow(fr, args.scale, args.bias)

    if args.sweep:
        sr=read_csv(args.sweep)
        basic_stats(sr, "sweep")
        analyze_sweep(sr)

    if args.out:
        # very small summary CSV (optional拡張用)
        with open(args.out, "w", newline="") as f:
            w=csv.writer(f); w.writerow(["note","value"])
            w.writerow(["generated","ok"])

if __name__=="__main__":
    main()

