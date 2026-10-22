import unittest
import os
import sys
from datetime import datetime

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from core.scheduler import SchedulerEngine, EvSessionState
from core.storage import Storage

class TestEvScheduler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions, cls.meta = SchedulerEngine.load_acn_sessions("2019-03-07")
        cls.engine = SchedulerEngine(power_cap_kw=50.0, timestep_minutes=15)
        cls.sim_result = cls.engine.run_simulation(cls.sessions)

    def test_r1_real_acn_data_loaded(self):
        """Requirement 1: Real session data loaded with all mandatory fields."""
        self.assertTrue(self.meta["is_real_data"])
        self.assertGreater(len(self.sessions), 20)
        self.assertEqual(self.meta["source"], "Real ACN-Data, Caltech")
        
        # Verify first session schema
        sample = self.sessions[0]
        self.assertIn("arrival_time", sample)
        self.assertIn("departure_time", sample)
        self.assertIn("requested_energy_kwh", sample)
        self.assertIn("max_power_kw", sample)
        self.assertGreater(sample["requested_energy_kwh"], 0)

    def test_r2_hard_power_cap_constraint(self):
        """Requirement 2: Power cap <= 50 kW at EVERY timestep (zero violations)."""
        power_curve = self.sim_result["charts"]["scheduled_power"]
        cap = self.sim_result["metadata"]["site_cap_kw"]
        
        # Hard constraint check: every single timestep must be <= cap
        for step, p in enumerate(power_curve):
            self.assertLessEqual(p, cap + 1e-4, f"Cap violated at timestep {step}: {p} kW > {cap} kW")
            
        self.assertEqual(self.sim_result["metrics"]["scheduled_violations"], 0)

    def test_baseline_uncontrolled_breaches_cap(self):
        """Baseline comparison: Uncontrolled policy breaches the cap."""
        uncon_violations = self.sim_result["metrics"]["uncontrolled_violations"]
        uncon_peak = self.sim_result["metrics"]["uncontrolled_peak_kw"]
        cap = self.sim_result["metadata"]["site_cap_kw"]
        
        self.assertGreater(uncon_violations, 0, "Uncontrolled must breach the 50 kW cap")
        self.assertGreater(uncon_peak, cap, "Uncontrolled peak must exceed site cap")
        self.assertGreater(self.sim_result["metrics"]["peak_reduction_pct"], 20.0)

    def test_r3_energy_needs_met(self):
        """Requirement 3: Energy needs met before departure and categorized."""
        metrics = self.sim_result["metrics"]
        self.assertGreater(metrics["delivered_pct"], 80.0)
        self.assertGreater(metrics["fully_satisfied"], 0)
        
        # Total counts match total sessions
        total_categorized = metrics["fully_satisfied"] + metrics["short"] + metrics["stranded"]
        self.assertEqual(total_categorized, len(self.sessions))

    def test_e7_worked_example_calculation(self):
        """E7: Worked numeric example matches prompt specs live."""
        ex = SchedulerEngine.get_worked_example()
        
        self.assertAlmostEqual(ex["total_allocated_kw"], 10.0, places=1)
        self.assertAlmostEqual(ex["guarantee_phase_total"], 9.58, places=1)
        self.assertAlmostEqual(ex["sharing_phase_total"], 0.42, places=1)
        
        # Vehicle A: gets max 7.0 kW, flagged At Risk
        veh_a = ex["vehicles"][0]
        self.assertEqual(veh_a["letter"], "A")
        self.assertAlmostEqual(veh_a["allocated_kw"], 7.0, places=1)
        self.assertEqual(veh_a["explanation"]["status"], "At risk")
        
        # Vehicle C: EV Bike gets 1.0 kW (0.7 guarantee + 0.3 sharing)
        veh_c = ex["vehicles"][2]
        self.assertEqual(veh_c["letter"], "C")
        self.assertAlmostEqual(veh_c["allocated_kw"], 1.0, places=1)

    def test_e3_decision_explainer_completeness(self):
        """E3: Decision explainer outputs all 5 required parts without missing keys."""
        sample_session = self.sim_result["sessions"][0]
        exp = sample_session["explanation"]
        if exp:
            self.assertIn("vehicle_facts", exp)
            self.assertIn("calculated_values", exp)
            self.assertIn("priority_breakdown", exp)
            self.assertIn("allocation_phases", exp)
            self.assertIn("final_sentence", exp)
            self.assertIn("one_line_reason", exp)
            
            # Check numerical fields
            self.assertIn("required_rate_kw", exp["calculated_values"])
            self.assertIn("laxity_hours", exp["calculated_values"])
            self.assertIn("total_priority_score", exp["priority_breakdown"])

    def test_user_storage_and_varieties(self):
        """User management and multiple vehicle varieties."""
        storage = Storage()
        users = storage.get_all_users()
        self.assertGreater(len(users), 1)
        
        # Check Priya has two different vehicle varieties
        priya = storage.get_user_by_username("priya")
        self.assertIsNotNone(priya)
        v_types = [v.vehicle_type for v in priya.vehicles]
        self.assertIn("EV Car", v_types)
        self.assertIn("EV Bike", v_types)

if __name__ == "__main__":
    unittest.main()
