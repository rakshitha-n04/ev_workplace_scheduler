import json
import os
import hashlib
from typing import Dict, List, Optional
from core.models import User, Vehicle, VEHICLE_PRESETS
import uuid

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "users_db.json")

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

class Storage:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_init()

    def _ensure_init(self):
        if not os.path.exists(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._seed_default_users()

    def _seed_default_users(self):
        # Admin user
        admin = {
            "id": "admin_01",
            "username": "admin",
            "password_hash": hash_pw("admin123"),
            "full_name": "Site Facilities Manager",
            "role": "admin",
            "vehicles": []
        }

        # User 1: Priya Sharma (has 2 different vehicles: EV Car and EV Bike)
        priya = {
            "id": "usr_priya",
            "username": "priya",
            "password_hash": hash_pw("user123"),
            "full_name": "Priya Sharma",
            "role": "user",
            "vehicles": [
                {
                    "id": "veh_priya_car",
                    "user_id": "usr_priya",
                    "user_name": "Priya Sharma",
                    "name": "Tesla Model 3 Long Range",
                    "vehicle_type": "EV Car",
                    "battery_capacity_kwh": 60.0,
                    "max_rate_kw": 7.2,
                    "current_charge_pct": 20.0,
                    "target_charge_pct": 100.0,
                    "is_plugged_in": True,
                    "current_session_id": "live_session_priya_car",
                    "priority_tier": "urgent",
                    "departure_time": "17:00",
                    "priority_fleet_rank": 1
                },
                {
                    "id": "veh_priya_bike",
                    "user_id": "usr_priya",
                    "user_name": "Priya Sharma",
                    "name": "Ather 450X EV Commuter",
                    "vehicle_type": "EV Bike",
                    "battery_capacity_kwh": 3.7,
                    "max_rate_kw": 1.2,
                    "current_charge_pct": 70.0,
                    "target_charge_pct": 95.0,
                    "is_plugged_in": True,
                    "current_session_id": "live_session_priya_bike",
                    "priority_tier": "flexible",
                    "departure_time": "18:00",
                    "priority_fleet_rank": 2
                }
            ]
        }

        # User 2: Rahul Verma (has EV Scooter)
        rahul = {
            "id": "usr_rahul",
            "username": "rahul",
            "password_hash": hash_pw("user123"),
            "full_name": "Rahul Verma",
            "role": "user",
            "vehicles": [
                {
                    "id": "veh_rahul_scooter",
                    "user_id": "usr_rahul",
                    "user_name": "Rahul Verma",
                    "name": "Ola S1 Pro EV Scooter",
                    "vehicle_type": "EV Scooter",
                    "battery_capacity_kwh": 4.0,
                    "max_rate_kw": 1.0,
                    "current_charge_pct": 45.0,
                    "target_charge_pct": 90.0,
                    "is_plugged_in": True,
                    "current_session_id": "live_session_rahul_scooter",
                    "priority_tier": "standard",
                    "departure_time": "17:30",
                    "priority_fleet_rank": 1
                }
            ]
        }

        # User 3: Alex Chen (has EV SUV)
        alex = {
            "id": "usr_alex",
            "username": "alex",
            "password_hash": hash_pw("user123"),
            "full_name": "Alex Chen",
            "role": "user",
            "vehicles": [
                {
                    "id": "veh_alex_suv",
                    "user_id": "usr_alex",
                    "user_name": "Alex Chen",
                    "name": "Hyundai Ioniq 5 AWD",
                    "vehicle_type": "EV SUV / Van",
                    "battery_capacity_kwh": 77.4,
                    "max_rate_kw": 10.5,
                    "current_charge_pct": 60.0,
                    "target_charge_pct": 90.0,
                    "is_plugged_in": False,
                    "current_session_id": None,
                    "priority_tier": "standard",
                    "departure_time": "18:00",
                    "priority_fleet_rank": 1
                }
            ]
        }

        data = {"users": [admin, priya, rahul, alex]}
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _read_data(self) -> Dict:
        self._ensure_init()
        try:
            with open(self.db_path, "r") as f:
                return json.load(f)
        except Exception:
            self._seed_default_users()
            with open(self.db_path, "r") as f:
                return json.load(f)

    def _write_data(self, data: Dict):
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_all_users(self) -> List[User]:
        data = self._read_data()
        users = []
        for u in data.get("users", []):
            vehicles = [
                Vehicle(
                    id=v["id"],
                    user_id=v["user_id"],
                    user_name=v.get("user_name", u["full_name"]),
                    name=v["name"],
                    vehicle_type=v["vehicle_type"],
                    battery_capacity_kwh=float(v["battery_capacity_kwh"]),
                    max_rate_kw=float(v["max_rate_kw"]),
                    current_charge_pct=float(v.get("current_charge_pct", 20.0)),
                    target_charge_pct=float(v.get("target_charge_pct", 100.0)),
                    is_plugged_in=bool(v.get("is_plugged_in", False)),
                    current_session_id=v.get("current_session_id"),
                    priority_tier=v.get("priority_tier", "standard"),
                    departure_time=v.get("departure_time", "17:00"),
                    priority_fleet_rank=int(v.get("priority_fleet_rank", 1))
                )
                for v in u.get("vehicles", [])
            ]
            users.append(User(
                id=u["id"],
                username=u["username"],
                password_hash=u["password_hash"],
                full_name=u["full_name"],
                role=u.get("role", "user"),
                vehicles=vehicles
            ))
        return users

    def get_user_by_username(self, username: str) -> Optional[User]:
        users = self.get_all_users()
        for u in users:
            if u.username.lower() == username.strip().lower():
                return u
        return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        users = self.get_all_users()
        for u in users:
            if u.id == user_id:
                return u
        return None

    def authenticate(self, username: str, password: str, expected_role: Optional[str] = None) -> Optional[User]:
        user = self.get_user_by_username(username)
        if not user:
            return None
        if user.password_hash != hash_pw(password):
            return None
        if expected_role and user.role != expected_role:
            return None
        return user

    def register_user(self, full_name: str, username: str, password: str, vehicles_data: List[Dict]) -> User:
        data = self._read_data()
        existing = [u for u in data.get("users", []) if u["username"].lower() == username.strip().lower()]
        if existing:
            raise ValueError(f"Username '{username}' is already taken. Please choose another username.")

        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        vehicles_list = []
        for v in vehicles_data:
            v_type = v.get("vehicle_type", "EV Car")
            presets = VEHICLE_PRESETS.get(v_type, VEHICLE_PRESETS["EV Car"])
            v_id = f"veh_{uuid.uuid4().hex[:8]}"
            batt = float(v.get("battery_capacity_kwh", presets["default_battery"]))
            max_p = float(v.get("max_rate_kw", presets["default_max_power"]))
            curr_soc = float(v.get("current_charge_pct", 25.0))
            targ_soc = float(v.get("target_charge_pct", 100.0))
            name = v.get("name", f"My {v_type}")
            
            vehicles_list.append({
                "id": v_id,
                "user_id": user_id,
                "user_name": full_name,
                "name": name,
                "vehicle_type": v_type,
                "battery_capacity_kwh": batt,
                "max_rate_kw": max_p,
                "current_charge_pct": curr_soc,
                "target_charge_pct": targ_soc,
                "is_plugged_in": False,
                "current_session_id": None,
                "priority_tier": v.get("priority_tier", "standard"),
                "departure_time": v.get("departure_time", "17:00"),
                "priority_fleet_rank": int(v.get("priority_fleet_rank", 1))
            })

        new_user_dict = {
            "id": user_id,
            "username": username.strip().lower(),
            "password_hash": hash_pw(password),
            "full_name": full_name.strip(),
            "role": "user",
            "vehicles": vehicles_list
        }

        data.setdefault("users", []).append(new_user_dict)
        self._write_data(data)
        return self.get_user_by_id(user_id)

    def update_vehicle_status(self, user_id: str, vehicle_id: str, is_plugged_in: bool, current_charge_pct: Optional[float] = None, session_id: Optional[str] = None, departure_time: Optional[str] = None, priority_tier: Optional[str] = None):
        data = self._read_data()
        for u in data.get("users", []):
            if u["id"] == user_id:
                for v in u.get("vehicles", []):
                    if v["id"] == vehicle_id:
                        v["is_plugged_in"] = is_plugged_in
                        if current_charge_pct is not None:
                            v["current_charge_pct"] = current_charge_pct
                        v["current_session_id"] = session_id if is_plugged_in else None
                        if departure_time is not None:
                            v["departure_time"] = departure_time
                        if priority_tier is not None:
                            v["priority_tier"] = priority_tier
        self._write_data(data)

    def update_vehicle_priority(self, user_id: str, vehicle_id: str, priority_tier: str, departure_time: Optional[str] = None, priority_fleet_rank: Optional[int] = None):
        data = self._read_data()
        for u in data.get("users", []):
            if u["id"] == user_id:
                for v in u.get("vehicles", []):
                    if v["id"] == vehicle_id:
                        v["priority_tier"] = priority_tier
                        if departure_time:
                            v["departure_time"] = departure_time
                        if priority_fleet_rank is not None:
                            v["priority_fleet_rank"] = priority_fleet_rank
        self._write_data(data)
