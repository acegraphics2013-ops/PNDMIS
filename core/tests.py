from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from datetime import date
import json
from .models import Unit, Profile, StaffRecord, Deliverable, Task
from .access import permitted_staff, can_review


class AccessTests(TestCase):
    def setUp(self):
        self.a = Unit.objects.create(name='PICU'); self.b = Unit.objects.create(name='NICU')
        self.manager = User.objects.create_user('manager', password='LongExamplePass123!'); Profile.objects.create(user=self.manager, role='manager', unit=self.a)
        self.nurse = User.objects.create_user('nurse', password='LongExamplePass123!'); Profile.objects.create(user=self.nurse, role='staff', unit=self.b)
        self.record = StaffRecord.objects.create(user=self.nurse, unit=self.b)
        self.deliverable = Deliverable.objects.create(staff=self.record, type='DTR', period='2026-10', due_date=date(2026, 10, 31), status='submitted')

    def test_manager_cannot_view_other_unit(self): self.assertFalse(permitted_staff(self.manager).filter(pk=self.record.pk).exists())
    def test_manager_cannot_review_other_unit(self): self.assertFalse(can_review(self.manager, self.record))
    def test_manager_review_denied(self):
        self.client.force_login(self.manager)
        response = self.client.post(f'/deliverables/{self.deliverable.pk}/review/', {'decision': 'verified'})
        self.assertEqual(response.status_code, 403)
    def test_staff_cannot_approve(self):
        self.client.force_login(self.nurse)
        response = self.client.post(f'/deliverables/{self.deliverable.pk}/review/', {'decision': 'approved'})
        self.assertEqual(response.status_code, 403)


class RecordsApiTests(TestCase):
    def setUp(self):
        self.unit = Unit.objects.create(name='PICU')
        self.sup = User.objects.create_user('sup', password='LongExamplePass123!'); Profile.objects.create(user=self.sup, role='supervisor', unit=self.unit)
        self.mgr = User.objects.create_user('mgr', password='LongExamplePass123!'); Profile.objects.create(user=self.mgr, role='manager', unit=self.unit)
        self.stf = User.objects.create_user('stf', password='LongExamplePass123!'); Profile.objects.create(user=self.stf, role='staff', unit=self.unit)

    def _post(self, user, payload):
        self.client.force_login(user)
        return self.client.post('/api/records/', data=json.dumps(payload), content_type='application/json')

    def test_create_and_persist(self):
        r = self._post(self.sup, {'title': 'Checklist A', 'description': 'd', 'unit': self.unit.id, 'due_date': '2026-11-01', 'priority': 'high', 'status': 'pending'})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Task.objects.filter(title='Checklist A').exists())

    def test_validation_rejects_short_title(self):
        r = self._post(self.sup, {'title': 'x', 'due_date': '2026-11-01'})
        self.assertEqual(r.status_code, 400)

    def test_staff_cannot_create(self):
        r = self._post(self.stf, {'title': 'Nope test', 'due_date': '2026-11-01'})
        self.assertEqual(r.status_code, 403)

    def test_search_filter_sort_pagination(self):
        Task.objects.create(title='Alpha', unit=self.unit, due_date=date(2026, 11, 1))
        Task.objects.create(title='Beta', unit=self.unit, due_date=date(2026, 11, 2), status='completed')
        self.client.force_login(self.sup)
        r = self.client.get('/api/records/?search=alpha')
        self.assertEqual(r.status_code, 200); self.assertEqual(r.json()['total'], 1)
        r = self.client.get('/api/records/?status=completed')
        self.assertEqual(r.json()['total'], 1)
        r = self.client.get('/api/records/?sort=name&page=1')
        self.assertEqual(r.json()['results'][0]['name'], 'Alpha')

    def test_update_and_delete(self):
        t = Task.objects.create(title='ToEdit', unit=self.unit, due_date=date(2026, 11, 5))
        self.client.force_login(self.sup)
        r = self.client.put(f'/api/records/{t.pk}/', data=json.dumps({'title': 'Edited', 'description': '', 'unit': self.unit.id, 'due_date': '2026-11-06', 'priority': 'normal', 'status': 'progress'}), content_type='application/json')
        self.assertEqual(r.status_code, 200); self.assertEqual(r.json()['record']['name'], 'Edited')
        r = self.client.delete(f'/api/records/{t.pk}/')
        self.assertEqual(r.status_code, 200); self.assertFalse(Task.objects.filter(pk=t.pk).exists())

    def test_stats_and_analytics_are_real(self):
        Task.objects.create(title='S1', unit=self.unit, due_date=date(2026, 11, 1))
        self.client.force_login(self.sup)
        s = self.client.get('/api/stats/').json()
        a = self.client.get('/api/analytics/').json()
        self.assertTrue(s['ok'] and s['total_records'] >= 1)
        self.assertTrue(a['ok'] and 'by_unit' in a)

    def test_pages_render(self):
        self.client.force_login(self.sup)
        for url in ['/', '/records/', '/categories/', '/reports/', '/users/', '/settings/']:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
