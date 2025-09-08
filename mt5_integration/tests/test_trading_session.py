from django.test import TestCase
from mt5_integration.models.trading_session import TradingSession
from django.utils import timezone

class TradingSessionStateMachineTest(TestCase):
    def setUp(self):
        self.session = TradingSession.objects.create(
            session_date=timezone.now().date(),
            session_type='ASIAN',
            current_state='IDLE'
        )

    def test_state_transitions(self):
        self.session.current_state = 'SWEPT'
        self.session.save()
        self.assertEqual(self.session.current_state, 'SWEPT')
        self.session.current_state = 'CONFIRMED'
        self.session.save()
        self.assertEqual(self.session.current_state, 'CONFIRMED')
        self.session.current_state = 'ARMED'
        self.session.save()
        self.assertEqual(self.session.current_state, 'ARMED')
        self.session.current_state = 'IN_TRADE'
        self.session.save()
        self.assertEqual(self.session.current_state, 'IN_TRADE')
        self.session.current_state = 'COOLDOWN'
        self.session.save()
        self.assertEqual(self.session.current_state, 'COOLDOWN')
