import unittest
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app import app, storage

class TestWebApp(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_login_page_renders(self):
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Administrator Portal", resp.data)
        self.assertIn(b"EV Driver Portal", resp.data)
        self.assertIn(b"New Driver? Register Fleet", resp.data)

    def test_admin_flow(self):
        # Login as admin
        resp = self.client.post('/login', data={'username': 'admin', 'password': 'admin123', 'role': 'admin'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Core Requirements Proof Panel", resp.data)
        self.assertIn(b"Requirement 1", resp.data)
        self.assertIn(b"Requirement 2", resp.data)
        self.assertIn(b"Requirement 3", resp.data)
        self.assertIn(b"BASELINE COMPARISON", resp.data)

    def test_user_registration_and_multi_vehicle(self):
        import uuid
        username = f"driver_{uuid.uuid4().hex[:6]}"
        # Register new driver with 2 vehicles: EV Car and EV Bike
        reg_data = {
            'full_name': 'Test Multicar Driver',
            'username': username,
            'password': 'password123',
            'vehicle_type[]': ['EV Car', 'EV Bike'],
            'vehicle_name[]': ['My Commuter Sedan', 'My Fast E-Bike'],
            'battery_kwh[]': ['55.0', '3.5'],
            'max_rate[]': ['7.0', '1.2']
        }
        resp = self.client.post('/register', data=reg_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Test Multicar Driver", resp.data)
        self.assertIn(b"My Commuter Sedan", resp.data)
        self.assertIn(b"My Fast E-Bike", resp.data)

        # Verify new user is registered and visible in Storage
        user = storage.get_user_by_username(username)
        self.assertIsNotNone(user)
        self.assertEqual(len(user.vehicles), 2)

    def test_how_it_works_page(self):
        resp = self.client.get('/how-it-works')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"The Problem in 3 Sentences", resp.data)
        self.assertIn(b"Fully Worked Numeric Example", resp.data)
        self.assertIn(b"Vehicle A", resp.data)
        self.assertIn(b"Vehicle B", resp.data)
        self.assertIn(b"Vehicle C", resp.data)

    def test_report_page(self):
        resp = self.client.get('/report?date=2019-03-07&cap=50')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Executive Proof Report", resp.data)
        self.assertIn(b"Power Cap", resp.data)

    def test_tradeoff_api(self):
        resp = self.client.get('/api/tradeoff-curve?date=2019-03-07')
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertIsInstance(json_data, list)
        self.assertGreater(len(json_data), 0)

if __name__ == '__main__':
    unittest.main()
