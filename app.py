import sys
import os
from datetime import datetime, timedelta
import io
import csv

# Add workspace directory to python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from core.models import User, Vehicle, VEHICLE_PRESETS
from core.storage import Storage
from core.scheduler import SchedulerEngine, EvSessionState

app = Flask(__name__)
app.secret_key = "gridsync_caltech_ev_secret_key_hackathon_track_3_2"

storage = Storage()

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return storage.get_user_by_id(user_id)

@app.context_processor
def inject_user():
    return {
        "current_user": get_current_user(),
        "now": datetime.now()
    }

@app.route("/")
def index():
    user = get_current_user()
    if user:
        if user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("user_dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "user")

        user = storage.authenticate(username, password, expected_role=role)
        if user:
            session["user_id"] = user.id
            session["role"] = user.role
            flash(f"Welcome back, {user.full_name}!", "success")
            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))
        else:
            flash(f"Invalid credentials for {role.capitalize()} portal. Please check your username and password.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/register", methods=["POST"])
def register():
    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "").strip()

    v_types = request.form.getlist("vehicle_type[]")
    v_names = request.form.getlist("vehicle_name[]")
    v_batts = request.form.getlist("battery_kwh[]")
    v_rates = request.form.getlist("max_rate[]")

    if not full_name or not username or not password:
        flash("All profile fields are required for driver registration.", "error")
        return redirect(url_for("login"))

    vehicles_data = []
    for i in range(len(v_types)):
        v_type = v_types[i] if i < len(v_types) else "EV Car"
        v_name = v_names[i] if i < len(v_names) else f"My {v_type}"
        try:
            v_batt = float(v_batts[i]) if i < len(v_batts) else 50.0
        except ValueError:
            v_batt = 50.0
        try:
            v_rate = float(v_rates[i]) if i < len(v_rates) else 7.2
        except ValueError:
            v_rate = 7.2

        vehicles_data.append({
            "name": v_name,
            "vehicle_type": v_type,
            "battery_capacity_kwh": v_batt,
            "max_rate_kw": v_rate,
            "current_charge_pct": 25.0,
            "target_charge_pct": 100.0
        })

    try:
        new_user = storage.register_user(full_name, username, password, vehicles_data)
        session["user_id"] = new_user.id
        session["role"] = new_user.role
        flash(f"Driver account created! Welcome {new_user.full_name}. Your {len(new_user.vehicles)} vehicle(s) are now connected to the site grid.", "success")
        return redirect(url_for("user_dashboard"))
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("login"))

@app.route("/admin")
def admin_dashboard():
    user = get_current_user()
    if not user or user.role != "admin":
        flash("Please log in as an administrator to access the site facility dashboard.", "error")
        return redirect(url_for("login"))

    selected_date = request.args.get("date", "2019-03-07")
    try:
        cap_val = float(request.args.get("cap", 150.0))
    except ValueError:
        cap_val = 150.0

    raw_sessions, meta = SchedulerEngine.load_acn_sessions(date_filter=selected_date)

    # Collect plugged-in Layer B user vehicles
    all_users = storage.get_all_users()
    live_layer_b = []
    for u in all_users:
        if u.role != "admin":
            for v in u.vehicles:
                if v.is_plugged_in:
                    # Synthesize active Layer B session
                    dep_t_str = v.departure_time if ":" in v.departure_time else "17:00"
                    live_layer_b.append({
                        "session_id": f"live_b_{v.id}",
                        "station_id": f"PORT-{v.id[-4:].upper()}",
                        "name": v.name,
                        "vehicle_type": v.vehicle_type,
                        "user_name": u.full_name,
                        "arrival_time": "2019-03-07 08:30:00",
                        "departure_time": f"2019-03-07 {dep_t_str}:00",
                        "battery_capacity_kwh": v.battery_capacity_kwh,
                        "max_power_kw": v.max_rate_kw,
                        "requested_energy_kwh": round(v.battery_capacity_kwh * (1.0 - v.current_charge_pct / 100.0), 2),
                        "initial_charge_pct": v.current_charge_pct,
                        "priority_tier": v.priority_tier,
                        "priority_fleet_rank": v.priority_fleet_rank
                    })

    engine = SchedulerEngine(power_cap_kw=cap_val, timestep_minutes=15)
    sim = engine.run_simulation(raw_sessions, live_layer_b_vehicles=live_layer_b)

    return render_template(
        "admin.html",
        sim=sim,
        selected_date=selected_date,
        registered_users=[u for u in all_users if u.role != "admin"]
    )

@app.route("/user")
def user_dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    # Load baseline sessions to compute relative rank on campus
    raw_sessions, _ = SchedulerEngine.load_acn_sessions(date_filter="2019-03-07")
    engine = SchedulerEngine(power_cap_kw=150.0, timestep_minutes=15)
    
    # Active vehicles on campus (sample of active campus cars at morning peak)
    current_time = datetime(2019, 3, 7, 9, 0)
    active_evs = [EvSessionState(s, is_layer_b=False) for s in raw_sessions[:16]]
    
    # Add this user's plugged-in vehicles
    user_sessions = {}
    for v in user.vehicles:
        if v.is_plugged_in:
            try:
                dep_parts = (v.departure_time if ":" in v.departure_time else "17:00").split(":")
                dep_hour, dep_min = int(dep_parts[0]), int(dep_parts[1])
            except Exception:
                dep_hour, dep_min = 17, 0
                
            dep_dt = datetime(2019, 3, 7, dep_hour, dep_min)
            req_kwh = round(v.battery_capacity_kwh * (1.0 - v.current_charge_pct / 100.0), 2)
            s_obj = EvSessionState({
                "session_id": f"user_v_{v.id}",
                "station_id": f"PORT-{v.id[-4:].upper()}",
                "name": v.name,
                "vehicle_type": v.vehicle_type,
                "user_name": user.full_name,
                "arrival_time": "2019-03-07 08:30:00",
                "departure_time": dep_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "battery_capacity_kwh": v.battery_capacity_kwh,
                "max_power_kw": v.max_rate_kw,
                "requested_energy_kwh": req_kwh,
                "initial_charge_pct": v.current_charge_pct,
                "priority_tier": v.priority_tier,
                "priority_fleet_rank": v.priority_fleet_rank
            }, is_layer_b=True, custom_name=v.name, vehicle_type=v.vehicle_type)
            active_evs.append(s_obj)
            user_sessions[v.id] = s_obj

    allocations, explanations = engine.solve_timestep(active_evs, current_time, site_cap_kw=150.0)
    
    vehicle_analytics = {}
    for v in user.vehicles:
        if v.is_plugged_in and v.id in user_sessions:
            sid = f"user_v_{v.id}"
            exp = explanations.get(sid, {})
            alloc_kw = allocations.get(sid, 0.0)
            
            # Estimate completion time
            time_to_full_hours = 0.0
            needed_kwh = v.battery_capacity_kwh * (1.0 - v.current_charge_pct / 100.0)
            if alloc_kw > 0.05:
                time_to_full_hours = round(needed_kwh / alloc_kw, 1)
            
            comp_dt = current_time + timedelta(hours=time_to_full_hours)
            comp_str = comp_dt.strftime("%H:%M") if alloc_kw > 0.05 else "Queued (Waiting on Cap)"
            
            # Projected charge trajectory (5 intervals)
            proj_labels = ["09:00", "11:00", "13:00", "15:00", f"{v.departure_time}"]
            step_charge = []
            curr_c = v.current_charge_pct
            charge_per_2h = (alloc_kw * 2.0 / max(0.1, v.battery_capacity_kwh)) * 100.0
            for i in range(5):
                curr_level = min(100.0, curr_c + (i * charge_per_2h))
                step_charge.append(round(curr_level, 1))
            
            pb = exp.get("priority_breakdown", {})
            vehicle_analytics[v.id] = {
                "rank": exp.get("rank", 1),
                "total_campus": len(active_evs),
                "allocated_kw": alloc_kw,
                "priority_score": pb.get("total_priority_score", 50.0),
                "urgency_part": pb.get("urgency_part", 0.0),
                "deficit_part": pb.get("charge_deficit_part", 0.0),
                "time_part": pb.get("time_left_part", 0.0),
                "tier_part": pb.get("tier_part", 0.0),
                "completion_time": comp_str,
                "explanation_sentence": exp.get("final_sentence", ""),
                "one_line_reason": exp.get("one_line_reason", ""),
                "proj_labels": proj_labels,
                "proj_data": step_charge
            }

    return render_template("user.html", current_user=user, analytics=vehicle_analytics)

@app.route("/user/update_priority/<vehicle_id>", methods=["POST"])
def update_priority(vehicle_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    priority_tier = request.form.get("priority_tier", "standard")
    dep_time = request.form.get("dep_time", "17:00")
    try:
        fleet_rank = int(request.form.get("fleet_rank", 1))
    except ValueError:
        fleet_rank = 1

    storage.update_vehicle_priority(user.id, vehicle_id, priority_tier, departure_time=dep_time, priority_fleet_rank=fleet_rank)
    flash(f"Priority updated! Set to '{priority_tier.capitalize()}' with departure at {dep_time}.", "success")
    return redirect(url_for("user_dashboard"))

@app.route("/api/user/simulate_priority", methods=["POST"])
def api_simulate_priority():
    data = request.get_json() or {}
    battery_kwh = float(data.get("battery_kwh", 50.0))
    max_rate_kw = float(data.get("max_rate_kw", 7.2))
    curr_pct = float(data.get("current_pct", 20.0))
    dep_time_str = data.get("departure_time", "17:00")
    priority_tier = data.get("priority_tier", "standard")
    fleet_rank = int(data.get("fleet_rank", 1))

    # Current time baseline 09:00
    cur_t = datetime(2019, 3, 7, 9, 0)
    try:
        dep_parts = dep_time_str.split(":")
        dep_dt = datetime(2019, 3, 7, int(dep_parts[0]), int(dep_parts[1]))
    except Exception:
        dep_dt = datetime(2019, 3, 7, 17, 0)

    time_left_h = max(0.2, (dep_dt - cur_t).total_seconds() / 3600.0)
    needed_kwh = battery_kwh * (1.0 - curr_pct / 100.0)
    req_rate = needed_kwh / time_left_h
    laxity = time_left_h - (needed_kwh / max(0.1, max_rate_kw))

    urgency_ratio = req_rate / max(0.1, max_rate_kw)
    urgency_pts = min(50.0, urgency_ratio * 25.0)
    deficit_pts = (1.0 - curr_pct / 100.0) * 30.0
    time_pts = min(20.0, 20.0 / (time_left_h + 0.5))

    tier_pts = 0.0
    if priority_tier == "urgent":
        tier_pts = 25.0
    elif priority_tier == "flexible":
        tier_pts = -15.0

    fleet_bonus = max(0.0, (2 - fleet_rank) * 5.0)
    total_priority = round(max(0.0, urgency_pts + deficit_pts + time_pts + tier_pts + fleet_bonus), 1)

    # Predicted allocation under 150 kW cap
    predicted_kw = min(max_rate_kw, max(0.8, req_rate))
    if priority_tier == "flexible" and req_rate < max_rate_kw * 0.5:
        predicted_kw = round(predicted_kw * 0.7, 1)

    predicted_rank = max(1, min(18, int(20 - (total_priority / 100.0) * 18)))

    return jsonify({
        "total_priority": total_priority,
        "urgency_points": round(urgency_pts, 1),
        "deficit_points": round(deficit_pts, 1),
        "time_points": round(time_pts, 1),
        "tier_points": tier_pts,
        "fleet_bonus": fleet_bonus,
        "predicted_kw": round(predicted_kw, 1),
        "predicted_rank": predicted_rank,
        "required_rate_kw": round(req_rate, 2),
        "laxity_hours": round(laxity, 2)
    })

@app.route("/user/toggle_plug/<vehicle_id>", methods=["POST"])
def toggle_plug(vehicle_id):
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    action = request.form.get("action", "plug_in")
    if action == "plug_in":
        try:
            curr_pct = float(request.form.get("current_pct", 25.0))
        except ValueError:
            curr_pct = 25.0
        dep_time = request.form.get("dep_time", "17:00")
        priority_tier = request.form.get("priority_tier", "standard")
        session_id = f"sess_{datetime.now().strftime('%H%M%S')}_{vehicle_id[-4:]}"
        storage.update_vehicle_status(
            user.id, vehicle_id, 
            is_plugged_in=True, 
            current_charge_pct=curr_pct, 
            session_id=session_id,
            departure_time=dep_time,
            priority_tier=priority_tier
        )
        flash("Vehicle plugged in! It is now connected to the workplace scheduler and prioritized in the site queue.", "success")
    else:
        storage.update_vehicle_status(user.id, vehicle_id, is_plugged_in=False)
        flash("Vehicle unplugged successfully.", "info")

    return redirect(url_for("user_dashboard"))

@app.route("/how-it-works")
def how_it_works():
    worked_example = SchedulerEngine.get_worked_example()
    return render_template("how_it_works.html", worked_example=worked_example)

@app.route("/report")
def report_view():
    date_val = request.args.get("date", "2019-03-07")
    try:
        cap_val = float(request.args.get("cap", 150.0))
    except ValueError:
        cap_val = 150.0

    raw_sessions, _ = SchedulerEngine.load_acn_sessions(date_filter=date_val)
    engine = SchedulerEngine(power_cap_kw=cap_val)
    sim = engine.run_simulation(raw_sessions)

    return render_template(
        "report.html",
        sim=sim,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@app.route("/api/tradeoff-curve")
def api_tradeoff_curve():
    date_val = request.args.get("date", "2019-03-07")
    raw_sessions, _ = SchedulerEngine.load_acn_sessions(date_filter=date_val)
    engine = SchedulerEngine()
    curve = engine.compute_tradeoff_curve(raw_sessions)
    return jsonify(curve)

@app.route("/export-csv")
def export_csv():
    date_val = request.args.get("date", "2019-03-07")
    raw_sessions, _ = SchedulerEngine.load_acn_sessions(date_filter=date_val)
    engine = SchedulerEngine(power_cap_kw=150.0)
    sim = engine.run_simulation(raw_sessions)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id", "station_id", "vehicle_name", "user_name", "layer",
        "arrival_time", "departure_time", "requested_kwh", "delivered_kwh",
        "completion_pct", "outcome", "status"
    ])

    for s in sim["sessions"]:
        writer.writerow([
            s["session_id"], s["station_id"], s["vehicle_name"], s["user_name"],
            "Layer B (User)" if s["is_layer_b"] else "Layer A (ACN)",
            s["arrival_time"], s["departure_time"], s["requested_kwh"],
            s["delivered_kwh"], s["completion_pct"], s["outcome"], s["final_status"]
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=ev_sessions_{date_val}.csv"}
    )

if __name__ == "__main__":
    print("Starting GridSync EV Scheduler Web Application on http://127.0.0.1:5000 ...")
    app.run(host="0.0.0.0", port=5000, debug=True)
